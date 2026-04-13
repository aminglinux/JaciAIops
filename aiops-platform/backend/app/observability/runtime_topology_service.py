from .trace_provider import get_trace_provider


class RuntimeTopologyService:
    async def get_snapshot(self, service: str, minutes: int = 15):
        provider = get_trace_provider()
        return await provider.get_runtime_topology(service, minutes)

    async def get_dependencies(self, service: str, minutes: int = 15):
        provider = get_trace_provider()
        return await provider.get_service_dependencies(service, minutes)

    async def get_anomalies(self, service: str, minutes: int = 15):
        provider = get_trace_provider()
        return await provider.get_recent_trace_anomalies(service, minutes)


runtime_topology_service = RuntimeTopologyService()
