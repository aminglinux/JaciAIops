from typing import List

from .schemas import RuntimeTopologySnapshot, ServiceDependency, TraceAnomaly


class TraceProvider:
    async def get_service_dependencies(self, service: str, minutes: int = 15) -> List[ServiceDependency]:
        raise NotImplementedError

    async def get_recent_trace_anomalies(self, service: str, minutes: int = 15) -> List[TraceAnomaly]:
        raise NotImplementedError

    async def get_runtime_topology(self, service: str, minutes: int = 15) -> RuntimeTopologySnapshot:
        raise NotImplementedError
