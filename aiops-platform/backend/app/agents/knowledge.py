import json
import re
import os
from typing import Dict, Any, Optional
import httpx
from neo4j import GraphDatabase
from openai import OpenAI
from app.core.config import settings
from .schemas import KnowledgeResult, TopologyInfo
from ..utils.logger import get_logger

logger = get_logger("knowledge")

class KnowledgeExpertAgent:
    """
    Knowledge Expert Agent (记忆层)
    核心职责：结合 KG 拓扑与 RAG 知识，提供决策依据。
    同时集成 debug_skill.md 中的常规排查方法。
    """
    
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )
        self.neo4j_driver = None
        self.debug_skill_content = self._load_debug_skill()
    
    def _load_debug_skill(self) -> str:
        """
        加载 debug_skill.md 的内容
        """
        try:
            debug_skill_path = os.path.join(os.path.dirname(__file__), "..", "debug_skill.md")
            if os.path.exists(debug_skill_path):
                with open(debug_skill_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"Could not load debug_skill.md: {e}")
        return ""
    
    def _get_neo4j_driver(self):
        if self.neo4j_driver is None:
            self.neo4j_driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
        return self.neo4j_driver
    
    def close(self):
        if self.neo4j_driver is not None:
            self.neo4j_driver.close()
            self.neo4j_driver = None
    
    def _build_prompt(self, service: str, symptom: str, topology_info: Dict, rag_context: str) -> str:
        debug_skill_section = ""
        if self.debug_skill_content:
            symptom_lower = symptom.lower()
            
            relevant_sections = []
            if any(keyword in symptom_lower for keyword in ["disk", "磁盘", "空间", "full", "no space"]):
                relevant_sections.append("1. Disk Full (磁盘空间不足)")
            if any(keyword in symptom_lower for keyword in ["network", "网络", "连接", "timeout", "dns"]):
                relevant_sections.append("2. Network Broken (网络连接异常)")
            if any(keyword in symptom_lower for keyword in ["memory", "内存", "oom", "out of memory"]):
                relevant_sections.append("3. Out of Memory (内存溢出/不足)")
            
            if relevant_sections:
                debug_skill_section = f"""

## 常规排查方法参考 (来自 debug_skill.md)
以下是针对当前问题的常规排查步骤：

{self.debug_skill_content[:2000]}

请参考以上排查方法，结合实际情况给出建议。
"""
        
        return f"""你是一个运维知识库专家。你连接着企业的 SOP 文档库、历史故障复盘报告 和 CMDB 知识图谱。

系统为你检索了以下上下文：

拓扑关系 (KG): {json.dumps(topology_info, ensure_ascii=False, indent=2)}
RAG 知识库参考: {rag_context}
{debug_skill_section}
Task
针对服务 {service} 的现象 {symptom}：

拓扑洞察：检查 KG 中的依赖关系。是否依赖了近期有变更或故障的组件（如 Redis, DB）？
经验复用：对比历史案例，寻找最相似的解决方案。
SOP 推荐：匹配最标准的应急处置步骤。
常规排查：参考 debug_skill.md 中的常规排查方法。

Output Format
结构化建议：

拓扑风险点: [例如：该服务强依赖 Redis 集群 A，该集群 5 分钟前有主从切换]
推荐方案: 重启服务以释放连接池资源（参考案例 #INC-2023-011）。
执行 SOP: [SOP-DB-002] 数据库连接池应急扩容步骤。
排查建议: [参考 debug_skill.md 中的具体排查步骤]"""

    async def query(self, service: str, symptom: str, topology_info: Dict = None, rag_context: str = None) -> KnowledgeResult:
        if topology_info is None:
            topology_info = await self._query_knowledge_graph(service)
        if rag_context is None:
            rag_context = await self._query_rag(f"{service} {symptom} 故障处理")
        
        prompt = self._build_prompt(service, symptom, topology_info, rag_context)
        
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            content = response.choices[0].message.content.strip()
        except Exception as e:
            content = f"知识分析暂时不可用: {str(e)}"
        
        return KnowledgeResult(
            service=service,
            symptom=symptom,
            knowledge_report=content,
            topology_info=TopologyInfo(**topology_info) if isinstance(topology_info, dict) else TopologyInfo(),
            rag_context=rag_context or "",
        )
    
    async def _query_knowledge_graph(self, service: str) -> Dict:
        try:
            driver = self._get_neo4j_driver()
            
            with driver.session() as session:
                result = session.run("""
                    MATCH (s {name: $name})
                    OPTIONAL MATCH (s)-[r:DEPENDS_ON]->(dep)
                    OPTIONAL MATCH (s)-[r2:RUNS_ON]->(run)
                    OPTIONAL MATCH (s)-[r3:CONNECTED_TO]->(conn)
                    RETURN s, 
                           collect(DISTINCT {name: dep.name, type: labels(dep)[0]}) as dependencies,
                           collect(DISTINCT {name: run.name, type: labels(run)[0]}) as runs_on,
                           collect(DISTINCT {name: conn.name, type: labels(conn)[0]}) as connections
                """, name=service)
                
                record = result.single()
                
                if record and record["s"]:
                    node = dict(record["s"])
                    return {
                        "service": service,
                        "properties": node,
                        "dependencies": [d for d in record["dependencies"] if d["name"]],
                        "runs_on": [r for r in record["runs_on"] if r["name"]],
                        "connections": [c for c in record["connections"] if c["name"]],
                        "source": "neo4j_kg"
                    }
                
                result = session.run("""
                    MATCH (s)
                    WHERE s.name CONTAINS $keyword OR s.name = $keyword
                    OPTIONAL MATCH (s)-[r:DEPENDS_ON]->(dep)
                    RETURN s.name as name, labels(s)[0] as type,
                           collect(DISTINCT {name: dep.name, type: labels(dep)[0]}) as dependencies
                    LIMIT 1
                """, keyword=service.replace("-service", ""))
                
                record = result.single()
                if record:
                    return {
                        "service": record["name"],
                        "type": record["type"],
                        "dependencies": [d for d in record["dependencies"] if d["name"]],
                        "source": "neo4j_kg_fuzzy"
                    }
                
                return self._get_mock_topology(service)
                
        except Exception as e:
            logger.error(f"[MOCK DATA] Neo4j 查询失败: {str(e)}，fallback 到模拟数据")
            return {
                "service": service,
                "error": str(e),
                **self._get_mock_topology(service)
            }
    
    async def _query_rag(self, query: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.RAG_SERVICE_URL}/api/chat",
                    json={"query": query}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("answer", "")
        except Exception as e:
            logger.warning(f"[MOCK DATA] RAG 服务 ({settings.RAG_SERVICE_URL}) 不可用: {str(e)}，将使用空上下文")
        return ""
    
    def _get_mock_topology(self, service: str) -> Dict:
        logger.warning(f"[MOCK DATA] Neo4j 不可用或未找到服务 '{service}'，返回模拟拓扑数据。此数据仅供参考，不应用于生产诊断决策。")
        
        topology_map = {
            "order-service": {
                "upstream": ["api-gateway", "user-service"],
                "downstream": ["payment-service", "inventory-service", "mysql-master", "redis-cluster"],
                "critical_deps": ["mysql-master", "redis-cluster"]
            },
            "payment-service": {
                "upstream": ["order-service"],
                "downstream": ["mysql-master", "kafka-cluster"],
                "critical_deps": ["mysql-master"]
            },
            "user-service": {
                "upstream": ["api-gateway"],
                "downstream": ["mysql-master", "redis-cluster"],
                "critical_deps": ["mysql-master", "redis-cluster"]
            },
            "prod-server-01": {
                "type": "Server",
                "ip": "192.168.1.10",
                "dependencies": ["session-cache-redis", "user-mysql-master"]
            },
            "prod-server-02": {
                "type": "Server",
                "ip": "192.168.1.12",
                "dependencies": ["order-postgres", "session-cache-redis"]
            }
        }
        
        return {
            "service": service,
            "dependencies": topology_map.get(service, {"upstream": [], "downstream": [], "critical_deps": []}),
            "recent_changes": [
                {"component": "redis-cluster", "change": "主从切换", "time": "5分钟前"}
            ],
            "_is_mock": True,
            "source": "mock_data",
            "disclaimer": "⚠️ 此为模拟数据，Neo4j 知识图谱不可用。请检查 NEO4J_URI/NEO4J_PASSWORD 配置。"
        }
    
    async def get_topology_graph(self, service: str = None, depth: int = 2) -> Dict:
        try:
            driver = self._get_neo4j_driver()
            
            with driver.session() as session:
                if service:
                    result = session.run(f"""
                        MATCH path = (s {{name: $name}})-[*1..{depth}]-(related)
                        RETURN s, related, relationships(path) as rels
                    """, name=service)
                else:
                    result = session.run(f"""
                        MATCH path = (a)-[r:DEPENDS_ON|RUNS_ON|CONNECTED_TO]-(b)
                        RETURN a, b, relationships(path) as rels
                        LIMIT 100
                    """)
                
                nodes = {}
                edges = []
                
                for record in result:
                    for node_key in ["s", "a", "related", "b"]:
                        node = record.get(node_key)
                        if node:
                            node_id = node.element_id
                            if node_id not in nodes:
                                nodes[node_id] = {
                                    "id": node_id,
                                    "label": dict(node).get("name", "unknown"),
                                    "type": list(node.labels)[0] if node.labels else "Node",
                                    "properties": dict(node)
                                }
                    
                    rels = record.get("rels", [])
                    for rel in rels:
                        try:
                            edges.append({
                                "source": rel.start_node.element_id,
                                "target": rel.end_node.element_id,
                                "type": rel.type
                            })
                        except:
                            pass
                
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
