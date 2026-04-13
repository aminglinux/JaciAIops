from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
from neo4j import GraphDatabase
import re
import json

from app.core.config import settings
from app.services import llm_config_manager

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

class KGQueryRequest(BaseModel):
    query: str
    service: Optional[str] = None

class KGQueryResponse(BaseModel):
    query: str
    cypher: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None

class RAGQueryRequest(BaseModel):
    query: str
    top_k: int = 5

class RAGQueryResponse(BaseModel):
    query: str
    answer: str
    documents: List[dict]
    source: str
    best_score: float = 0.0
    use_context: bool = False
    mode: str = "RAG"

def get_neo4j_driver():
    return GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )

@router.get("/query")
async def query_knowledge_graph(service: str = None, query: str = None):
    try:
        driver = get_neo4j_driver()
        
        with driver.session() as session:
            if service:
                result = _query_service_info(session, service)
            elif query:
                result = _query_by_natural_language(session, query)
            else:
                return {"error": "请提供 service 或 query 参数"}
        
        driver.close()
        
        return {
            "query": query or f"查询 {service} 的详细信息",
            "result": result,
            "source": "neo4j_kg"
        }
        
    except Exception as e:
        return {
            "query": query or service,
            "error": str(e),
            "fallback": _get_mock_kg_data(service)
        }

def _query_service_info(session, service_name: str) -> Dict:
    result = session.run("""
        MATCH (s {name: $name})
        OPTIONAL MATCH (s)-[r:DEPENDS_ON]->(dep)
        OPTIONAL MATCH (s)-[r2:RUNS_ON]->(run)
        OPTIONAL MATCH (s)-[r3:CONNECTED_TO]->(conn)
        RETURN s, 
               collect(DISTINCT {name: dep.name, type: labels(dep)[0]}) as dependencies,
               collect(DISTINCT {name: run.name, type: labels(run)[0]}) as runs_on,
               collect(DISTINCT {name: conn.name, type: labels(conn)[0]}) as connections
    """, name=service_name)
    
    record = result.single()
    if not record:
        return {"error": f"未找到服务: {service_name}"}
    
    node = dict(record["s"]) if record["s"] else {}
    
    return {
        "service": service_name,
        "properties": node,
        "dependencies": [d for d in record["dependencies"] if d["name"]],
        "runs_on": [r for r in record["runs_on"] if r["name"]],
        "connections": [c for c in record["connections"] if c["name"]]
    }

def _extract_service_name(query: str) -> Optional[str]:
    import re
    patterns = [
        r'([a-zA-Z][a-zA-Z0-9\-]+)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, query)
        for match in matches:
            if len(match) > 3 and '-' in match:
                return match
    return None

def _query_by_natural_language(session, query: str) -> Dict:
    query_lower = query.lower()
    service_name = _extract_service_name(query)
    
    if "运行" in query and "服务器" in query:
        if service_name:
            result = session.run("""
                MATCH (s {name: $name})-[r:RUNS_ON]->(server)
                RETURN s.name as service, collect({name: server.name, ip: server.ip, type: labels(server)[0]}) as servers
            """, name=service_name)
            record = result.single()
            if record and record["servers"]:
                return {
                    "service": record["service"],
                    "servers": [s for s in record["servers"] if s["name"]],
                    "query_type": "runs_on_server"
                }
    
    if "依赖" in query or "depend" in query_lower:
        if service_name:
            result = session.run("""
                MATCH (s {name: $name})-[r:DEPENDS_ON]->(dep)
                RETURN s.name as service, collect({name: dep.name, type: labels(dep)[0]}) as deps
            """, name=service_name)
            record = result.single()
            if record:
                return {
                    "service": record["service"],
                    "dependencies": record["deps"]
                }
    
    if ("服务器" in query or "server" in query_lower) and not service_name:
        result = session.run("MATCH (s:Server) RETURN s.name as name, s.ip as ip LIMIT 10")
        servers = [{"name": r["name"], "ip": r["ip"]} for r in result]
        return {"servers": servers}
    
    if ("数据库" in query or "database" in query_lower) and not service_name:
        result = session.run("MATCH (d:Database) RETURN d.name as name, d.type as type LIMIT 10")
        databases = [{"name": r["name"], "type": r["type"]} for r in result]
        return {"databases": databases}
    
    if service_name:
        result = session.run("""
            MATCH (s {name: $name})
            OPTIONAL MATCH (s)-[r:DEPENDS_ON]->(dep)
            OPTIONAL MATCH (s)-[r2:RUNS_ON]->(run)
            OPTIONAL MATCH (s)-[r3:CONNECTED_TO]->(conn)
            RETURN s, 
                   collect(DISTINCT {name: dep.name, type: labels(dep)[0]}) as dependencies,
                   collect(DISTINCT {name: run.name, type: labels(run)[0]}) as runs_on,
                   collect(DISTINCT {name: conn.name, type: labels(conn)[0]}) as connections
        """, name=service_name)
        record = result.single()
        if record and record["s"]:
            node = dict(record["s"])
            return {
                "service": service_name,
                "properties": node,
                "dependencies": [d for d in record["dependencies"] if d["name"]],
                "runs_on": [r for r in record["runs_on"] if r["name"]],
                "connections": [c for c in record["connections"] if c["name"]]
            }
    
    result = session.run("""
        CALL db.index.fulltext.queryNodes('entityIndex', $query) 
        YIELD node 
        RETURN labels(node)[0] as type, node.name as name, node as properties 
        LIMIT 5
    """, query=query)
    
    nodes = [{"type": r["type"], "name": r["name"], "properties": dict(r["properties"])} for r in result]
    
    if not nodes:
        result = session.run("""
            MATCH (n) 
            WHERE n.name CONTAINS $keyword OR n.ip CONTAINS $keyword
            RETURN labels(n)[0] as type, n.name as name, n as properties 
            LIMIT 5
        """, keyword=query.split()[0] if query.split() else query)
        nodes = [{"type": r["type"], "name": r["name"], "properties": dict(r["properties"])} for r in result]
    
    return {"matched_nodes": nodes}

@router.post("/rag/query", response_model=RAGQueryResponse)
async def query_rag(request: RAGQueryRequest):
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.RAG_SERVICE_URL}/api/chat",
                json={"query": request.query}
            )
            
            if response.status_code == 200:
                data = response.json()
                return RAGQueryResponse(
                    query=request.query,
                    answer=data.get("answer", ""),
                    documents=data.get("documents", []),
                    source="ops_rag_service",
                    best_score=data.get("best_score", 0.0),
                    use_context=data.get("use_context", False),
                    mode=data.get("mode", "RAG")
                )
            else:
                return RAGQueryResponse(
                    query=request.query,
                    answer="RAG 服务暂时不可用",
                    documents=_get_mock_rag_docs(request.query),
                    source="mock_data"
                )
                
    except Exception as e:
        return RAGQueryResponse(
            query=request.query,
            answer=f"查询出错: {str(e)}",
            documents=_get_mock_rag_docs(request.query),
            source="mock_data"
        )

@router.get("/topology")
async def get_topology(service: str = None, depth: int = 2):
    try:
        driver = get_neo4j_driver()
        
        with driver.session() as session:
            if service:
                result = session.run(f"""
                    MATCH path = (s {{name: $name}})-[*1..{depth}]-(related)
                    RETURN s, related, relationships(path) as rels
                """, name=service)
            else:
                result = session.run(f"""
                    MATCH path = (a)-[r:DEPENDS_ON|RUNS_ON|CONNECTED_TO*1..{depth}]-(b)
                    RETURN a, b, relationships(path) as rels
                    LIMIT 50
                """)
            
            nodes = {}
            edges = []
            
            for record in result:
                source = record.get("s") or record.get("a")
                target = record.get("related") or record.get("b")
                
                if source:
                    source_id = source.element_id
                    if source_id not in nodes:
                        nodes[source_id] = {
                            "id": source_id,
                            "label": dict(source).get("name", "unknown"),
                            "type": list(source.labels)[0] if source.labels else "Node",
                            "properties": dict(source)
                        }
                
                if target:
                    target_id = target.element_id
                    if target_id not in nodes:
                        nodes[target_id] = {
                            "id": target_id,
                            "label": dict(target).get("name", "unknown"),
                            "type": list(target.labels)[0] if target.labels else "Node",
                            "properties": dict(target)
                        }
                
                rels = record.get("rels", [])
                for rel in rels:
                    edges.append({
                        "source": rel.start_node.element_id if hasattr(rel, 'start_node') else None,
                        "target": rel.end_node.element_id if hasattr(rel, 'end_node') else None,
                        "type": rel.type
                    })
        
        driver.close()
        
        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "source": "neo4j_kg"
        }
        
    except Exception as e:
        return {
            "nodes": [],
            "edges": [],
            "error": str(e),
            "source": "error"
        }

@router.get("/qa/chat")
async def chat_with_knowledge(question: str, analyze_problem: bool = False):
    return await _build_chat_response(question, analyze_problem)


@router.get("/qa/chat/stream")
async def chat_with_knowledge_stream(question: str, analyze_problem: bool = False):
    async def event_generator():
        result = await _build_chat_response(question, analyze_problem)
        meta_payload = {
            "type": "meta",
            "mode": result.get("mode"),
            "intent": result.get("intent"),
            "knowledge": result.get("knowledge"),
            "rag_context": result.get("rag_context"),
        }
        yield f"data: {json.dumps(meta_payload, ensure_ascii=False)}\n\n"

        answer = result.get("answer", "") or ""
        chunk_size = 24
        for index in range(0, len(answer), chunk_size):
            delta_payload = {
                "type": "delta",
                "content": answer[index:index + chunk_size],
            }
            yield f"data: {json.dumps(delta_payload, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def _build_chat_response(question: str, analyze_problem: bool = False) -> Dict[str, Any]:
    from app.agents import IntentParseAgent, KnowledgeExpertAgent

    if not analyze_problem:
        answer, rag_context = await _general_chat(question)
        return {
            "question": question,
            "mode": "general_chat",
            "intent": {
                "intent": "GENERAL_QA",
                "confidence": "MEDIUM",
                "entities": {},
                "normalized_query": question,
                "ner_entities": [],
                "keywords": [],
                "clarification_needed": False,
            },
            "knowledge": None,
            "rag_context": rag_context,
            "answer": answer,
        }

    if _is_simple_chat_text(question):
        return {
            "question": question,
            "mode": "general_chat",
            "intent": {
                "intent": "GENERAL_QA",
                "confidence": "HIGH",
                "entities": {},
                "normalized_query": question,
                "ner_entities": [],
                "keywords": [],
                "clarification_needed": False,
            },
            "knowledge": None,
            "rag_context": "",
            "answer": _build_simple_chat_response(question),
        }

    intent_agent = IntentParseAgent()
    knowledge_agent = KnowledgeExpertAgent()

    try:
        intent = await intent_agent.parse(question)
    except Exception:
        return {
            "question": question,
            "mode": "analysis",
            "intent": {
                "intent": "GENERAL_QA",
                "confidence": "LOW",
                "entities": {},
                "normalized_query": question,
                "ner_entities": [],
                "keywords": [],
                "clarification_needed": False,
            },
            "knowledge": None,
            "rag_context": "",
            "answer": "我暂时无法完成深度检索，但可以先陪你做简单交流。若你要排查问题，请补充服务名、异常现象或日志关键词。",
        }

    service = intent.entities.get("service", "unknown")
    symptom = intent.entities.get("symptom", "unknown")

    if _is_simple_chat(question, intent):
        answer = _build_simple_chat_response(question)
        return {
            "question": question,
            "mode": "general_chat",
            "intent": intent.model_dump(),
            "knowledge": None,
            "rag_context": "",
            "answer": answer,
        }

    knowledge = await knowledge_agent.query(service, symptom)
    rag_answer = await _query_rag_for_context(question)
    answer = _compose_qa_answer(knowledge.knowledge_report, rag_answer, intent.intent)

    return {
        "question": question,
        "mode": "analysis",
        "intent": intent.model_dump(),
        "knowledge": knowledge.model_dump(),
        "rag_context": rag_answer,
        "answer": answer,
    }

async def _query_rag_for_context(question: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.RAG_SERVICE_URL}/api/chat",
                json={"query": question}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("answer", "")
    except:
        pass
    return ""


async def _general_chat(question: str) -> tuple[str, str]:
    if _is_simple_chat_text(question):
        return _build_simple_chat_response(question), ""

    rag_context = await _query_rag_for_context(question)
    prompt = _build_general_chat_prompt(question, rag_context)

    try:
        client, llm_config = llm_config_manager.get_client_for_scene("general_chat")
        response = client.chat.completions.create(
            model=llm_config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=llm_config.temperature,
        )
        answer = (response.choices[0].message.content or "").strip()
        if answer:
            return answer, rag_context
    except Exception:
        pass

    if rag_context:
        return rag_context, rag_context

    return _build_simple_chat_response(question), ""


def _build_general_chat_prompt(question: str, rag_context: str) -> str:
    context_block = f"\n参考知识：{rag_context}\n" if rag_context else "\n当前没有检索到额外知识上下文。\n"
    return (
        "你是 AIOps 平台里的通用问答助手。"
        "请优先用自然、简洁、友好的方式回答。"
        "如果用户问题明显是运维分析类，但当前不是分析模式，也要先正常回答，"
        "并在合适时提醒用户可以打开“分析问题”开关获取更深入的定位建议。"
        f"{context_block}\n"
        f"用户问题：{question}"
    )


def _is_simple_chat_text(question: str) -> bool:
    normalized = question.strip().lower()
    if not normalized:
        return True

    greeting_patterns = [
        r"^(hi|hello|hey)\b",
        r"^(你好|您好|嗨|哈喽)",
        r"^(在吗|在不在)$",
        r"(你是谁|你能做什么|帮助|help)$",
        r"^(早上好|中午好|下午好|晚上好)$",
    ]
    return any(re.search(pattern, normalized) for pattern in greeting_patterns)


def _is_simple_chat(question: str, intent) -> bool:
    normalized = question.strip().lower()
    if _is_simple_chat_text(question):
        return True

    has_entities = bool(intent.entities)
    if intent.intent == "GENERAL_QA" and not has_entities and len(normalized) <= 30:
        return True

    return False


def _build_simple_chat_response(question: str) -> str:
    normalized = question.strip().lower()
    if any(token in normalized for token in ["你是谁", "你能做什么", "help", "帮助"]):
        return (
            "你好，我是 AIOps 智能问答助手。"
            "我更擅长回答运维相关问题，比如服务依赖、故障排查、数据库连接、日志分析和常见 SOP。"
            "你可以直接问我：`order-service 依赖哪些组件？` 或 `数据库连接池耗尽怎么排查？`"
        )

    if any(token in normalized for token in ["你好", "您好", "hi", "hello", "hey", "嗨", "哈喽"]):
        return (
            "你好，很高兴为你服务。"
            "你可以直接描述一个运维问题、服务名或故障现象，我会尽量给出排查建议。"
        )

    if any(token in normalized for token in ["早上好", "中午好", "下午好", "晚上好"]):
        return "你好，已在线。你可以告诉我具体的运维问题，我来帮你分析。"

    return "我已收到你的消息。若你想让我更准确回答，请尽量提供服务名、异常现象或具体问题。"


def _compose_qa_answer(knowledge_report: str, rag_context: str, intent_name: str) -> str:
    report = (knowledge_report or "").strip()
    rag = (rag_context or "").strip()

    if report and rag:
        if rag in report:
            return report
        return f"{report}\n\n补充参考：{rag}"

    if report:
        return report

    if rag:
        return rag

    if intent_name == "GENERAL_QA":
        return "我暂时没有检索到直接答案。你可以补充服务名、故障现象、日志关键词或依赖组件，我再帮你分析。"

    return "未找到相关知识，请补充更多上下文后重试。"

def _get_mock_kg_data(service: str) -> dict:
    return {
        "service": service,
        "dependencies": {
            "upstream": ["api-gateway"],
            "downstream": ["mysql-master", "redis-cluster"]
        },
        "status": "running",
        "owner": "ops-team"
    }

def _get_mock_rag_docs(query: str) -> List[dict]:
    return [
        {
            "file": "sop-database.md",
            "snippet": "数据库连接池应急扩容步骤：1. 检查当前连接池状态 2. 临时调大连接池上限..."
        },
        {
            "file": "incident-2023-011.md",
            "snippet": "order-service连接池耗尽故障复盘：根因是连接池配置不足，解决方案是..."
        }
    ]
