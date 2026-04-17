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
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")

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
    upload_batch_id = Column(String(64), nullable=True, index=True)
    upload_file_name = Column(String(255), nullable=True)

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


class RuntimeGraphConfig(Base):
    __tablename__ = "runtime_graph_configs"

    id = Column(Integer, primary_key=True, index=True)
    trace_backend = Column(String(50), default="jaeger", nullable=False)
    jaeger_query_url = Column(String(255), default="http://localhost:16686", nullable=False)
    tempo_query_url = Column(String(255), default="", nullable=False)
    trace_query_timeout = Column(Integer, default=15, nullable=False)
    trace_default_lookback_minutes = Column(Integer, default=15, nullable=False)
    runtime_graph_enabled = Column(Boolean, default=True, nullable=False)
    cmdb_service_list_json = Column(Text, default="[]", nullable=False)
    updated_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LogSourceConfig(Base):
    __tablename__ = "log_source_configs"

    id = Column(Integer, primary_key=True, index=True)
    elasticsearch_enabled = Column(Boolean, default=True, nullable=False)
    elasticsearch_url = Column(String(255), default="http://localhost:9200", nullable=False)
    elasticsearch_index_pattern = Column(String(255), default="logstash-*", nullable=False)
    elasticsearch_auth_type = Column(String(30), default="none", nullable=False)
    elasticsearch_username = Column(String(255), default="", nullable=False)
    elasticsearch_password_encrypted = Column(Text, default="", nullable=False)
    elasticsearch_password_masked = Column(String(100), default="", nullable=False)
    elasticsearch_api_key_encrypted = Column(Text, default="", nullable=False)
    elasticsearch_api_key_masked = Column(String(100), default="", nullable=False)
    elasticsearch_tls_verify = Column(Boolean, default=True, nullable=False)
    loki_enabled = Column(Boolean, default=True, nullable=False)
    loki_url = Column(String(255), default="http://localhost:3100", nullable=False)
    updated_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), default="新会话", nullable=False)
    analyze_problem = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, default="", nullable=False)
    mode = Column(String(50), nullable=True)
    intent_json = Column(Text, nullable=True)
    knowledge_json = Column(Text, nullable=True)
    runtime_topology_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), default="custom", nullable=False, index=True)
    alert_name = Column(String(255), nullable=False, index=True)
    severity = Column(String(50), default="warning", nullable=False, index=True)
    service = Column(String(255), nullable=True, index=True)
    instance = Column(String(255), nullable=True, index=True)
    status = Column(String(20), default="completed", nullable=False, index=True)
    fingerprint = Column(String(255), nullable=True, index=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    query_text = Column(Text, nullable=False)
    description = Column(Text, default="", nullable=False)
    labels_json = Column(Text, default="{}")
    annotations_json = Column(Text, default="{}")
    normalized_alert_json = Column(Text, default="{}")
    rca_json = Column(Text, default="{}")
    final_decision_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AlertWebhookSecurityConfig(Base):
    __tablename__ = "alert_webhook_security_configs"

    id = Column(Integer, primary_key=True, index=True)
    ip_whitelist = Column(Text, default="", nullable=False)
    trust_proxy_headers = Column(Boolean, default=False, nullable=False)
    updated_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
