from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
from neo4j import GraphDatabase
import re
import json
from sqlalchemy.orm import Session

from app.api.auth import User, get_current_user, require_admin
from app.core.config import settings
from app.core.database import get_db
from app.observability import runtime_topology_service
from app.services import llm_config_manager, runtime_graph_config_manager

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

DEFAULT_TOPOLOGY_NODE_LIMIT = 40
DEFAULT_TOPOLOGY_EDGE_LIMIT = 120

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


class RuntimeGraphConfigPayload(BaseModel):
    trace_backend: str = "jaeger"
    jaeger_query_url: str
    tempo_query_url: str = ""
    trace_query_timeout: int = 15
    trace_default_lookback_minutes: int = 15
    runtime_graph_enabled: bool = True
    service_list: List[str] = []


class ManualGraphRelationPayload(BaseModel):
    target_type: str
    target_name: str
    relation_type: str
    target_properties: Dict[str, Any] = {}


class ManualGraphEntryPayload(BaseModel):
    source_type: str
    source_name: str
    source_properties: Dict[str, Any] = {}
    relation: Optional[ManualGraphRelationPayload] = None


class GraphNodeUpdatePayload(BaseModel):
    name: str
    properties: Dict[str, Any] = {}


class GraphRelationUpdatePayload(BaseModel):
    relation_type: str
    properties: Dict[str, Any] = {}


ALLOWED_NODE_TYPES = {
    "Service",
    "Server",
    "Database",
    "Cache",
    "MQ",
    "Gateway",
    "Cluster",
    "Namespace",
    "Application",
    "Middleware",
}

ALLOWED_RELATION_TYPES = {
    "DEPENDS_ON",
    "RUNS_ON",
    "CONNECTED_TO",
    "CALLS",
    "BELONGS_TO",
    "USES_DB",
    "USES_CACHE",
    "USES_MQ",
}


def _sanitize_label(value: str, allowed_values: Optional[set[str]] = None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError("标签不能为空")
    if allowed_values is not None and normalized not in allowed_values:
        raise ValueError(f"不支持的类型: {normalized}")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", normalized):
        raise ValueError(f"非法标签: {normalized}")
    return normalized


def _sanitize_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = {}
    for key, value in (properties or {}).items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(key)):
            continue
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) for item in value):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized


def _node_label_expression(labels: List[str]) -> str:
    valid_labels = [_sanitize_label(label) for label in labels if str(label).strip()]
    if not valid_labels:
        raise ValueError("节点缺少 labels")
    return ":" + ":".join(valid_labels)


def _merge_node(session, node_data: Dict[str, Any], updated_by: str) -> Dict[str, Any]:
    labels = node_data.get("labels", [])
    if not labels:
        raise ValueError("节点缺少 labels")
    label_expression = _node_label_expression(labels)
    primary_label = _sanitize_label(labels[-1])
    properties = _sanitize_properties(dict(node_data.get("properties", {}) or {}))
    name = str(properties.get("name", "")).strip()
    if not name:
        raise ValueError("节点缺少 name 属性")
    properties["updated_by"] = updated_by
    session.run(
        f"""
        MERGE (node{label_expression} {{name: $name}})
        SET node += $properties
        """,
        name=name,
        properties=properties,
    )
    return {"label": primary_label, "labelExpression": label_expression, "name": name, "properties": properties}

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
                    UNWIND relationships(path) as r
                    RETURN startNode(r) as a,
                           endNode(r) as b,
                           type(r) as rel_type,
                           elementId(r) as rel_id,
                           properties(r) as rel_props,
                           elementId(startNode(r)) as source_id,
                           elementId(endNode(r)) as target_id
                    LIMIT 200
                """, name=service)
                sampled_nodes = []
            else:
                sampled_node_records = session.run(
                    """
                    MATCH (n)
                    RETURN n
                    ORDER BY coalesce(n.name, '')
                    LIMIT $node_limit
                    """,
                    node_limit=DEFAULT_TOPOLOGY_NODE_LIMIT,
                )
                sampled_nodes = [record.get("n") for record in sampled_node_records if record.get("n")]
                sampled_node_ids = [node.element_id for node in sampled_nodes]

                if sampled_node_ids:
                    result = session.run(
                        """
                        UNWIND $node_ids AS node_id
                        MATCH (a)
                        WHERE elementId(a) = node_id
                        MATCH (a)-[r]->(b)
                        WHERE elementId(b) IN $node_ids
                        RETURN a,
                               b,
                               type(r) as rel_type,
                               elementId(r) as rel_id,
                               properties(r) as rel_props,
                               elementId(startNode(r)) as source_id,
                               elementId(endNode(r)) as target_id
                        LIMIT $edge_limit
                        """,
                        node_ids=sampled_node_ids,
                        edge_limit=DEFAULT_TOPOLOGY_EDGE_LIMIT,
                    )
                else:
                    result = []
            
            nodes = {}
            edges = []

            for node in sampled_nodes:
                node_id = node.element_id
                nodes[node_id] = {
                    "id": node_id,
                    "label": dict(node).get("name", "unknown"),
                    "type": list(node.labels)[0] if node.labels else "Node",
                    "properties": dict(node),
                }
            
            for record in result:
                source = record.get("a")
                target = record.get("b")
                
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
                
                if record.get("source_id") and record.get("target_id"):
                    edges.append({
                        "id": record.get("rel_id") if record.get("rel_id") else None,
                        "source": record.get("source_id"),
                        "target": record.get("target_id"),
                        "type": record.get("rel_type"),
                        "properties": dict(record.get("rel_props") or {}),
                    })
        
        driver.close()
        
        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "source": "neo4j_kg",
            "mode": "service_scope" if service else "sampled_overview",
            "message": None if service else "未指定服务时返回抽样拓扑，避免对 Neo4j 执行高开销全图扫描。",
        }
        
    except Exception as e:
        return {
            "nodes": [],
            "edges": [],
            "error": str(e),
            "source": "error"
        }


@router.get("/runtime-config", response_model=dict)
def get_runtime_graph_config(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "code": 200,
        "message": "success",
        "data": runtime_graph_config_manager.get_config(db),
    }


@router.put("/runtime-config", response_model=dict)
def update_runtime_graph_config(
    payload: RuntimeGraphConfigPayload,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        result = runtime_graph_config_manager.update_config(db, payload.model_dump(), current_user.username)
        return {"code": 200, "message": "更新成功", "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/manual-entry", response_model=dict)
def create_manual_graph_entry(
    payload: ManualGraphEntryPayload,
    current_user: User = Depends(require_admin),
):
    source_type = payload.source_type.strip()
    if source_type not in ALLOWED_NODE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的源节点类型")

    relation = payload.relation
    if relation:
        if relation.target_type.strip() not in ALLOWED_NODE_TYPES:
            raise HTTPException(status_code=400, detail="不支持的目标节点类型")
        if relation.relation_type.strip() not in ALLOWED_RELATION_TYPES:
            raise HTTPException(status_code=400, detail="不支持的关系类型")

    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            session.run(
                f"""
                MERGE (source:{source_type} {{name: $source_name}})
                SET source += $source_properties
                SET source.updated_by = $updated_by
                RETURN source
                """,
                source_name=payload.source_name.strip(),
                source_properties=payload.source_properties,
                updated_by=current_user.username,
            )

            if relation:
                target_type = relation.target_type.strip()
                relation_type = relation.relation_type.strip()
                session.run(
                    f"""
                    MERGE (source:{source_type} {{name: $source_name}})
                    SET source += $source_properties
                    MERGE (target:{target_type} {{name: $target_name}})
                    SET target += $target_properties
                    MERGE (source)-[rel:{relation_type}]->(target)
                    SET rel.updated_by = $updated_by
                    RETURN source, rel, target
                    """,
                    source_name=payload.source_name.strip(),
                    source_properties=payload.source_properties,
                    target_name=relation.target_name.strip(),
                    target_properties=relation.target_properties,
                    updated_by=current_user.username,
                )
        driver.close()
        return {
            "code": 200,
            "message": "录入成功",
            "data": {
                "source": payload.source_name.strip(),
                "sourceType": source_type,
                "relationCreated": bool(relation),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"写入知识图谱失败: {exc}") from exc


@router.put("/nodes/{node_id}", response_model=dict)
def update_graph_node(
    node_id: str,
    payload: GraphNodeUpdatePayload,
    current_user: User = Depends(require_admin),
):
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            properties = _sanitize_properties(payload.properties)
            properties["name"] = payload.name.strip()
            properties["updated_by"] = current_user.username
            record = session.run(
                """
                MATCH (n)
                WHERE elementId(n) = $node_id
                SET n += $properties
                RETURN elementId(n) as id, labels(n) as labels, properties(n) as props
                """,
                node_id=node_id,
                properties=properties,
            ).single()
        driver.close()
        if not record:
            raise HTTPException(status_code=404, detail="节点不存在")
        return {
            "code": 200,
            "message": "更新成功",
            "data": {
                "id": record["id"],
                "type": record["labels"][-1] if record["labels"] else "Node",
                "properties": record["props"],
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新节点失败: {exc}") from exc


@router.delete("/nodes/{node_id}", response_model=dict)
def delete_graph_node(
    node_id: str,
    _: User = Depends(require_admin),
):
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            record = session.run(
                """
                MATCH (n)
                WHERE elementId(n) = $node_id
                WITH n, properties(n) as props
                DETACH DELETE n
                RETURN props.name as name
                """,
                node_id=node_id,
            ).single()
        driver.close()
        if not record:
            raise HTTPException(status_code=404, detail="节点不存在")
        return {"code": 200, "message": "删除成功", "data": {"name": record["name"]}}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除节点失败: {exc}") from exc


@router.put("/relations/{relation_id}", response_model=dict)
def update_graph_relation(
    relation_id: str,
    payload: GraphRelationUpdatePayload,
    current_user: User = Depends(require_admin),
):
    try:
        relation_type = _sanitize_label(payload.relation_type)
        properties = _sanitize_properties(payload.properties)
        properties["updated_by"] = current_user.username
        driver = get_neo4j_driver()
        with driver.session() as session:
            record = session.run(
                """
                MATCH (source)-[r]->(target)
                WHERE elementId(r) = $relation_id
                RETURN source, target, properties(r) as props
                """,
                relation_id=relation_id,
            ).single()
            if not record:
                driver.close()
                raise HTTPException(status_code=404, detail="关系不存在")

            source = record["source"]
            target = record["target"]
            source_id = source.element_id
            target_id = target.element_id
            source_name = dict(source).get("name")
            target_name = dict(target).get("name")
            created = session.run(
                f"""
                MATCH (source), (target)
                WHERE elementId(source) = $source_id AND elementId(target) = $target_id
                MATCH (source)-[old]->(target)
                WHERE elementId(old) = $relation_id
                DELETE old
                CREATE (source)-[new_rel:{relation_type}]->(target)
                SET new_rel += $properties
                RETURN elementId(new_rel) as id, type(new_rel) as rel_type, properties(new_rel) as rel_props
                """,
                relation_id=relation_id,
                source_id=source_id,
                target_id=target_id,
                properties=properties,
            ).single()
        driver.close()
        return {
            "code": 200,
            "message": "更新成功",
            "data": {
                "id": created["id"],
                "type": created["rel_type"],
                "properties": created["rel_props"],
                "sourceName": source_name,
                "targetName": target_name,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新关系失败: {exc}") from exc


@router.delete("/relations/{relation_id}", response_model=dict)
def delete_graph_relation(
    relation_id: str,
    _: User = Depends(require_admin),
):
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            record = session.run(
                """
                MATCH (source)-[r]->(target)
                WHERE elementId(r) = $relation_id
                WITH source, target, type(r) as rel_type, r
                DELETE r
                RETURN properties(source).name as source_name,
                       properties(target).name as target_name,
                       rel_type
                """,
                relation_id=relation_id,
            ).single()
        driver.close()
        if not record:
            raise HTTPException(status_code=404, detail="关系不存在")
        return {
            "code": 200,
            "message": "删除成功",
            "data": {
                "sourceName": record["source_name"],
                "targetName": record["target_name"],
                "type": record["rel_type"],
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除关系失败: {exc}") from exc


@router.post("/import-data", response_model=dict)
async def import_graph_data(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
):
    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="仅支持导入 JSON 文件")

    try:
        content = await file.read()
        payload = json.loads(content.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"解析 JSON 失败: {exc}") from exc

    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="导入内容必须是数组")

    imported_nodes: set[tuple[str, str]] = set()
    imported_relations = 0
    failed_records = []

    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            for index, item in enumerate(payload, start=1):
                if not isinstance(item, dict):
                    failed_records.append({"index": index, "error": "记录不是对象"})
                    continue
                source_data = item.get("n")
                relation_data = item.get("r")
                target_data = item.get("m")
                if not source_data or not relation_data or not target_data:
                    failed_records.append({"index": index, "error": "记录缺少 n/r/m"})
                    continue

                try:
                    source_node = _merge_node(session, source_data, current_user.username)
                    target_node = _merge_node(session, target_data, current_user.username)
                    imported_nodes.add((source_node["label"], source_node["name"]))
                    imported_nodes.add((target_node["label"], target_node["name"]))

                    relation_type = _sanitize_label(str(relation_data.get("type", "")))
                    relation_properties = _sanitize_properties(dict(relation_data.get("properties", {}) or {}))
                    relation_properties["updated_by"] = current_user.username
                    session.run(
                        f"""
                        MATCH (source{source_node['labelExpression']} {{name: $source_name}})
                        MATCH (target{target_node['labelExpression']} {{name: $target_name}})
                        MERGE (source)-[rel:{relation_type}]->(target)
                        SET rel += $relation_properties
                        """,
                        source_name=source_node["name"],
                        target_name=target_node["name"],
                        relation_properties=relation_properties,
                    )
                    imported_relations += 1
                except Exception as record_exc:
                    failed_records.append({"index": index, "error": str(record_exc)})
        driver.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"导入知识图谱失败: {exc}") from exc

    if imported_relations == 0 and failed_records:
        raise HTTPException(
            status_code=400,
            detail=f"未导入任何关系，首个错误: 第 {failed_records[0]['index']} 条 - {failed_records[0]['error']}",
        )

    return {
        "code": 200,
        "message": "导入成功" if not failed_records else "部分导入成功",
        "data": {
            "fileName": file.filename,
            "records": len(payload),
            "nodes": len(imported_nodes),
            "relations": imported_relations,
            "failed": len(failed_records),
            "errors": failed_records[:10],
        },
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
            "runtime_topology": result.get("runtime_topology"),
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
        runtime_topology = await _maybe_get_runtime_topology_from_question(question)
        runtime_topology_payload = runtime_topology.model_dump() if runtime_topology else None
        answer, rag_context = await _general_chat(question, runtime_topology_payload)
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
            "runtime_topology": runtime_topology_payload,
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
            "runtime_topology": None,
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
            "runtime_topology": None,
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
            "runtime_topology": None,
            "rag_context": "",
            "answer": answer,
        }

    runtime_topology = None
    runtime_config = runtime_graph_config_manager.get_effective_config()
    if service and service != "unknown":
        try:
            runtime_topology = await runtime_topology_service.get_snapshot(
                service,
                runtime_config["traceDefaultLookbackMinutes"],
            )
        except Exception:
            runtime_topology = None

    knowledge = await knowledge_agent.query(service, symptom)
    rag_answer = await _query_rag_for_context(question)
    answer = _compose_qa_answer(
        knowledge.knowledge_report,
        rag_answer,
        intent.intent,
        runtime_topology=runtime_topology.model_dump() if runtime_topology else None,
    )

    return {
        "question": question,
        "mode": "analysis",
        "intent": intent.model_dump(),
        "knowledge": knowledge.model_dump(),
        "runtime_topology": runtime_topology.model_dump() if runtime_topology else None,
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


async def _general_chat(question: str, runtime_topology: Optional[Dict[str, Any]] = None) -> tuple[str, str]:
    if _is_simple_chat_text(question):
        return _build_simple_chat_response(question), ""

    rag_context = await _query_rag_for_context(question)
    prompt = _build_general_chat_prompt(question, rag_context, runtime_topology)

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


def _build_general_chat_prompt(question: str, rag_context: str, runtime_topology: Optional[Dict[str, Any]] = None) -> str:
    context_block = f"\n参考知识：{rag_context}\n" if rag_context else "\n当前没有检索到额外知识上下文。\n"
    runtime_block = (
        f"\n最近运行时拓扑：{json.dumps(runtime_topology, ensure_ascii=False, indent=2)}\n"
        if runtime_topology else
        "\n当前没有匹配到明确的运行时拓扑信息。\n"
    )
    return (
        "你是 AIOps 平台里的通用问答助手。"
        "请优先用自然、简洁、友好的方式回答。"
        "如果用户问题明显是运维分析类，但当前不是分析模式，也要先正常回答，"
        "并在合适时提醒用户可以打开“分析问题”开关获取更深入的定位建议。"
        f"{context_block}{runtime_block}\n"
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


async def _maybe_get_runtime_topology_from_question(question: str):
    runtime_config = runtime_graph_config_manager.get_effective_config()
    if not runtime_config["runtimeGraphEnabled"]:
        return None
    lowered = question.lower()
    candidate_services = [service for service in runtime_config["serviceList"] if service.lower() in lowered]
    if not candidate_services:
        return None
    try:
        return await runtime_topology_service.get_snapshot(
            candidate_services[0],
            runtime_config["traceDefaultLookbackMinutes"],
        )
    except Exception:
        return None


def _format_runtime_topology(runtime_topology: Dict[str, Any]) -> str:
    downstream = runtime_topology.get("downstream", [])[:3]
    anomalies = runtime_topology.get("anomalies", [])[:3]
    parts = []
    if downstream:
        deps = [f"{item['target_service']}({item['avg_latency_ms']:.0f}ms)" for item in downstream if item.get("target_service")]
        if deps:
            parts.append(f"最近调用依赖：{', '.join(deps)}")
    if anomalies:
        spans = [f"{item['span_name']}({item['duration_ms']:.0f}ms)" for item in anomalies if item.get("span_name")]
        if spans:
            parts.append(f"异常 Span：{', '.join(spans)}")
    return "\n运行时观测： " + "；".join(parts) if parts else ""


def _compose_qa_answer(
    knowledge_report: str,
    rag_context: str,
    intent_name: str,
    runtime_topology: Optional[Dict[str, Any]] = None,
) -> str:
    report = (knowledge_report or "").strip()
    rag = (rag_context or "").strip()
    runtime_suffix = _format_runtime_topology(runtime_topology) if runtime_topology else ""

    if report and rag:
        if rag in report:
            return f"{report}{runtime_suffix}"
        return f"{report}\n\n补充参考：{rag}{runtime_suffix}"

    if report:
        return f"{report}{runtime_suffix}"

    if rag:
        return f"{rag}{runtime_suffix}"

    if intent_name == "GENERAL_QA":
        return f"我暂时没有检索到直接答案。你可以补充服务名、故障现象、日志关键词或依赖组件，我再帮你分析。{runtime_suffix}"

    return f"未找到相关知识，请补充更多上下文后重试。{runtime_suffix}"

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
