from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings, validate_security_settings
from app.core.database import init_db
from app.api import api_router
from app.api.terminal import websocket_terminal
from app.api.auth import router as auth_router, create_default_users
from app.api.approval import router as approval_router
from app.agents.knowledge import KnowledgeExpertAgent
from app.utils.logger import setup_logger

_knowledge_agent_instance: KnowledgeExpertAgent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _knowledge_agent_instance
    setup_logger("aiops", level=logging.DEBUG if settings.DEBUG else logging.INFO)
    init_db()
    create_default_users()
    validate_security_settings()
    _knowledge_agent_instance = KnowledgeExpertAgent()
    yield
    if _knowledge_agent_instance is not None:
        _knowledge_agent_instance.close()

app = FastAPI(
    title=settings.APP_NAME,
    description="AIOps智能运维平台 - Multi-Agent故障诊断系统",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(auth_router)
app.include_router(approval_router)

app.add_api_websocket_route("/ws/terminal", websocket_terminal)

@app.get("/")
async def root():
    return {
        "message": "AIOps Platform API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
