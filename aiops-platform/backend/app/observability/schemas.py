from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ServiceDependency(BaseModel):
    source_service: str
    target_service: str
    dependency_type: str = "CALLS"
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    call_count: int = 0
    last_seen: Optional[datetime] = None
    source: str = "jaeger"
    details: Dict[str, Any] = Field(default_factory=dict)


class TraceAnomaly(BaseModel):
    service: str
    trace_id: str
    span_name: str
    duration_ms: float
    suspected_dependency: Optional[str] = None
    anomaly_type: str = "slow_span"
    details: Dict[str, Any] = Field(default_factory=dict)


class RuntimeTopologySnapshot(BaseModel):
    service: str
    window_minutes: int
    upstream: List[ServiceDependency] = Field(default_factory=list)
    downstream: List[ServiceDependency] = Field(default_factory=list)
    anomalies: List[TraceAnomaly] = Field(default_factory=list)
    source: str = "jaeger"
