from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NEREntity(BaseModel):
    type: str = Field(..., description="实体类型，如 SERVICE, SERVER, IP, SYMPTOM 等")
    value: str = Field(..., description="原始值")
    normalized: Optional[str] = Field(None, description="标准化后的值")


class IntentResult(BaseModel):
    intent: str = Field("GENERAL_QA", description="意图类型: DIAGNOSE, QUERY_STATUS, EXECUTE_FIX, GENERAL_QA")
    confidence: str = Field("LOW", description="置信度: HIGH, MEDIUM, LOW")
    entities: Dict[str, Any] = Field(default_factory=dict, description="结构化实体")
    normalized_query: str = Field("", description="标准化查询")
    ner_entities: List[NEREntity] = Field(default_factory=list, description="NER 提取的实体列表")
    keywords: List[str] = Field(default_factory=list, description="关键词列表")
    clarification_needed: bool = Field(False, description="是否需要用户澄清")


class EntitiesResult(BaseModel):
    entities_by_type: Dict[str, List[NEREntity]] = Field(default_factory=dict)
    keywords: List[str] = Field(default_factory=list)
    services: List[NEREntity] = Field(default_factory=list)
    servers: List[NEREntity] = Field(default_factory=list)
    symptoms: List[NEREntity] = Field(default_factory=list)
    databases: List[NEREntity] = Field(default_factory=list)
    metrics: List[NEREntity] = Field(default_factory=list)
    actions: List[NEREntity] = Field(default_factory=list)
    ssh_users: List[NEREntity] = Field(default_factory=list)
    intent: Optional[str] = None
    confidence: Optional[str] = None


class TopologyInfo(BaseModel):
    service: str = ""
    dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    runs_on: List[Dict[str, Any]] = Field(default_factory=list)
    connections: List[Dict[str, Any]] = Field(default_factory=list)
    upstream: List[str] = Field(default_factory=list)
    downstream: List[str] = Field(default_factory=list)
    critical_deps: List[str] = Field(default_factory=list)
    source: str = Field("unknown", description="数据来源: neo4j_kg, neo4j_kg_fuzzy, mock_data, error")


class KnowledgeResult(BaseModel):
    service: str = ""
    symptom: str = ""
    knowledge_report: str = ""
    topology_info: TopologyInfo = Field(default_factory=TopologyInfo)
    rag_context: str = ""


class ServerAnalysis(BaseModel):
    server: str = ""
    health_status: str = Field("UNKNOWN", description="CRITICAL, WARNING, NORMAL, UNKNOWN")
    anomalies: List[str] = Field(default_factory=list)
    root_cause_hypothesis: str = ""
    recommendations: List[str] = Field(default_factory=list)
    confidence: str = Field("LOW", description="HIGH, MEDIUM, LOW")


class ObservabilityResult(BaseModel):
    service: str = ""
    servers_checked: List[str] = Field(default_factory=list)
    metrics_data: Dict[str, Any] = Field(default_factory=dict)
    logs_data: Dict[str, Any] = Field(default_factory=dict)
    analysis_reports: List[ServerAnalysis] = Field(default_factory=list)
    summary: str = ""


class DiagnosisDecision(BaseModel):
    is_final: bool = Field(False)
    problem_type: str = Field("unknown")
    root_cause: str = ""
    root_cause_summary: str = ""
    impact: str = ""
    recommendation: str = ""
    action_plan: str = ""
    risk_level: str = Field("MEDIUM", description="LOW, MEDIUM, HIGH")
    confidence: str = Field("MEDIUM", description="HIGH, MEDIUM, LOW")
    decision: str = Field("MANUAL_INTERVENTION", description="EXECUTE_FIX, NEED_MORE_INFO, MANUAL_INTERVENTION, RESOLVED")
    reasoning: str = ""
    analysis_summary: str = ""
    evidence_chain: List[str] = Field(default_factory=list)
    propagation_path: List[str] = Field(default_factory=list)
    affected_services: List[str] = Field(default_factory=list)
    log_evidence: Dict[str, Any] = Field(default_factory=dict)


class ExecutionHistoryItem(BaseModel):
    iteration: int = 0
    tool: str = ""
    args: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)


class DynamicExecutionResult(BaseModel):
    status: str = Field("incomplete", description="completed, needs_confirmation, incomplete")
    iterations: int = 0
    execution_history: List[ExecutionHistoryItem] = Field(default_factory=list)
    final_decision: Optional[DiagnosisDecision] = None
    raw_response: str = ""


class ActionResult(BaseModel):
    tool_name: str = ""
    template_name: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    risk_assessment: str = Field("HIGH", description="LOW, MEDIUM, HIGH")
    requires_approval: bool = False
    execution_note: str = ""
    redline_triggered: bool = False
