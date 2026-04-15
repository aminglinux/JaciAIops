from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings, validate_security_settings
from app.core.database import init_db
from app.api import api_router
from app.api.auth import router as auth_router, create_default_users
from app.api.approval import router as approval_router
from app.api.knowledge import close_neo4j_driver, init_neo4j_schema
from app.agents.knowledge import KnowledgeExpertAgent
from app.services import llm_config_manager
from app.utils.logger import setup_logger

_knowledge_agent_instance: KnowledgeExpertAgent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _knowledge_agent_instance
    setup_logger("aiops", level=logging.DEBUG if settings.DEBUG else logging.INFO)
    init_db()
    create_default_users()
    llm_config_manager.bootstrap_defaults()
    validate_security_settings()
    init_neo4j_schema()
    _knowledge_agent_instance = KnowledgeExpertAgent()
    yield
    if _knowledge_agent_instance is not None:
        _knowledge_agent_instance.close()
    close_neo4j_driver()

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
