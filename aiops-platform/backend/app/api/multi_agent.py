import uuid
import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.database import get_db, AgentTask
from app.agents import MultiAgentOrchestrator

router = APIRouter(prefix="/api/multi-agent", tags=["multi-agent"])

class MultiAgentRequest(BaseModel):
    query: str
    stream: Optional[bool] = False
    session_id: Optional[str] = None

class MultiAgentResponse(BaseModel):
    query: str
    start_time: str
    stages: Dict[str, Any]
    final_decision: Optional[Dict[str, Any]]
    execution_result: Optional[Dict[str, Any]]
    duration_seconds: float

orchestrator = MultiAgentOrchestrator()
MULTI_AGENT_TIMEOUT_SECONDS = 180


def _run_multi_agent_query_sync(query: str) -> Dict[str, Any]:
    local_orchestrator = MultiAgentOrchestrator()
    return asyncio.run(local_orchestrator.process_query(query))

@router.post("/process", response_model=MultiAgentResponse)
async def process_multi_agent_query(request: MultiAgentRequest):
    """
    处理 multi-agent 查询的完整流程
    
    流程:
    1. IntentParseAgent: NER 实体识别和意图解析
    2. KnowledgeExpertAgent: 查询知识图谱和 RAG
    3. ObservabilityAnalystAgent: 查询节点状态和日志
    4. MasterAgent: 整合信息并决策
    5. ActionExecuteAgent: 执行修复操作（如果需要）
    """
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_multi_agent_query_sync, request.query),
            timeout=MULTI_AGENT_TIMEOUT_SECONDS,
        )
        return MultiAgentResponse(**result)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"多Agent诊断超时（>{MULTI_AGENT_TIMEOUT_SECONDS}s）")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理查询时发生错误: {str(e)}")

@router.post("/process/stream")
async def process_multi_agent_stream(request: MultiAgentRequest):
    """
    流式处理 multi-agent 查询，实时返回各阶段结果
    """
    async def event_generator():
        async for event in orchestrator.process_query_stream(request.query):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

@router.post("/ner")
async def extract_ner_entities(request: MultiAgentRequest):
    """
    仅执行 NER 实体识别
    """
    from app.agents import IntentParseAgent
    
    intent_agent = IntentParseAgent()
    entities = await intent_agent.extract_entities(request.query)
    
    return {
        "query": request.query,
        "entities": entities
    }

@router.post("/knowledge")
async def query_knowledge(request: MultiAgentRequest):
    """
    仅查询知识图谱和 RAG
    """
    from app.agents import KnowledgeExpertAgent, IntentParseAgent
    
    intent_agent = IntentParseAgent()
    knowledge_agent = KnowledgeExpertAgent()
    
    entities = await intent_agent.extract_entities(request.query)
    service = entities.get("services", [{}])[0].get("normalized", "unknown") if entities.get("services") else "unknown"
    symptoms = entities.get("symptoms", [])
    symptom_str = ", ".join([s.get("value", "") if isinstance(s, dict) else s for s in symptoms])
    
    knowledge_result = await knowledge_agent.query(service=service, symptom=symptom_str)
    
    return {
        "query": request.query,
        "service": service,
        "symptoms": symptoms,
        "knowledge_result": knowledge_result
    }

@router.post("/observability")
async def query_observability(request: MultiAgentRequest):
    """
    仅查询节点状态和日志
    """
    from app.agents import ObservabilityAnalystAgent, IntentParseAgent, KnowledgeExpertAgent
    
    intent_agent = IntentParseAgent()
    observability_agent = ObservabilityAnalystAgent()
    knowledge_agent = KnowledgeExpertAgent()
    
    entities = await intent_agent.extract_entities(request.query)
    service = entities.get("services", [{}])[0].get("normalized", "unknown") if entities.get("services") else "unknown"
    symptoms = entities.get("symptoms", [])
    symptom_str = ", ".join([s.get("value", "") if isinstance(s, dict) else s for s in symptoms])
    
    knowledge_result = await knowledge_agent.query(service=service, symptom=symptom_str)
    
    observability_result = await observability_agent.analyze_with_skills(
        service=service,
        entities=entities,
        knowledge_context=knowledge_result
    )
    
    return {
        "query": request.query,
        "service": service,
        "entities": entities,
        "observability_result": observability_result
    }

@router.get("/health")
async def health_check():
    """
    健康检查
    """
    return {
        "status": "healthy",
        "service": "multi-agent-orchestrator",
        "agents": [
            "IntentParseAgent",
            "KnowledgeExpertAgent",
            "ObservabilityAnalystAgent",
            "MasterAgent",
            "ActionExecuteAgent"
        ]
    }
