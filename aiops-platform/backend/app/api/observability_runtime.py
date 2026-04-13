from fastapi import APIRouter, HTTPException

from app.observability import runtime_topology_service
from app.services import runtime_graph_config_manager

router = APIRouter(prefix="/api/observability-runtime", tags=["observability-runtime"])


@router.get("/dependencies")
async def get_runtime_dependencies(service: str, minutes: int = 15):
    if not runtime_graph_config_manager.get_effective_config()["runtimeGraphEnabled"]:
        raise HTTPException(status_code=404, detail="运行时拓扑能力未启用")
    try:
        dependencies = await runtime_topology_service.get_dependencies(service, minutes)
        return {
            "service": service,
            "minutes": minutes,
            "dependencies": [item.model_dump() for item in dependencies],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查询运行时依赖失败: {exc}") from exc


@router.get("/anomalies")
async def get_runtime_anomalies(service: str, minutes: int = 15):
    if not runtime_graph_config_manager.get_effective_config()["runtimeGraphEnabled"]:
        raise HTTPException(status_code=404, detail="运行时拓扑能力未启用")
    try:
        anomalies = await runtime_topology_service.get_anomalies(service, minutes)
        return {
            "service": service,
            "minutes": minutes,
            "anomalies": [item.model_dump() for item in anomalies],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查询运行时异常失败: {exc}") from exc


@router.get("/topology")
async def get_runtime_topology(service: str, minutes: int = 15):
    if not runtime_graph_config_manager.get_effective_config()["runtimeGraphEnabled"]:
        raise HTTPException(status_code=404, detail="运行时拓扑能力未启用")
    try:
        snapshot = await runtime_topology_service.get_snapshot(service, minutes)
        return snapshot.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查询运行时拓扑失败: {exc}") from exc
