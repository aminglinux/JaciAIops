from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    roles = Column(String(255), default="user")
    permissions = Column(Text, default="")
    scope = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Log(Base):
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(10))
    content = Column(Text)
    source = Column(String(50))
    is_anomaly = Column(Boolean, default=False)
    anomaly_score = Column(Float, nullable=True)
    user_feedback = Column(Boolean, nullable=True)

class Feedback(Base):
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(Integer)
    feedback_type = Column(Boolean)
    created_at = Column(DateTime, default=datetime.utcnow)

class AgentTask(Base):
    __tablename__ = "agent_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(36), unique=True, index=True)
    user_input = Column(Text)
    intent_data = Column(Text, nullable=True)
    analysis_report = Column(Text, nullable=True)
    knowledge_context = Column(Text, nullable=True)
    decision = Column(Text, nullable=True)
    action_result = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LLMProvider(Base):
    __tablename__ = "llm_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    provider_code = Column(String(100), unique=True, index=True, nullable=False)
    provider_type = Column(String(50), default="openai_compatible", nullable=False)
    base_url = Column(String(255), nullable=False)
    api_key_encrypted = Column(Text, nullable=False)
    api_key_masked = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True)
    is_builtin = Column(Boolean, default=False)
    extra_config_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    models = relationship("LLMModel", back_populates="provider", cascade="all, delete-orphan")


class LLMModel(Base):
    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("llm_providers.id"), nullable=False, index=True)
    model_id = Column(String(100), nullable=False)
    display_name = Column(String(100), nullable=False)
    model_type = Column(String(50), default="chat", nullable=False)
    supports_function_calling = Column(Boolean, default=False)
    supports_streaming = Column(Boolean, default=True)
    supports_json_mode = Column(Boolean, default=False)
    context_window = Column(Integer, nullable=True)
    max_output_tokens = Column(Integer, nullable=True)
    enabled = Column(Boolean, default=True)
    is_default_candidate = Column(Boolean, default=True)
    meta_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    provider = relationship("LLMProvider", back_populates="models")
    bindings = relationship("LLMSceneBinding", back_populates="model")


class LLMSceneBinding(Base):
    __tablename__ = "llm_scene_bindings"

    id = Column(Integer, primary_key=True, index=True)
    scene_key = Column(String(100), unique=True, index=True, nullable=False)
    model_id = Column(Integer, ForeignKey("llm_models.id"), nullable=False, index=True)
    temperature = Column(Float, default=0.2)
    max_tokens = Column(Integer, nullable=True)
    top_p = Column(Float, nullable=True)
    enabled = Column(Boolean, default=True)
    updated_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    model = relationship("LLMModel", back_populates="bindings")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    operator = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(100), nullable=False)
    detail_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
