from fastapi import APIRouter
from app.api import agent, alerts, logs, knowledge, multi_agent, llm, observability_runtime

api_router = APIRouter()

api_router.include_router(agent.router)
api_router.include_router(alerts.router)
api_router.include_router(logs.router)
api_router.include_router(knowledge.router)
api_router.include_router(multi_agent.router)
api_router.include_router(llm.router)
api_router.include_router(observability_runtime.router)
