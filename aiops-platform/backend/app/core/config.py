import os
import warnings
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "AIOps Platform"
    DEBUG: bool = True
    
    SECRET_KEY: str = ""
    
    DATABASE_URL: str = "sqlite:///./data/aiops.db"
    
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    
    RAG_SERVICE_URL: str = "http://localhost:8001"
    
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    OPENAI_MODEL: str = "qwen-plus"
    
    SSH_USER: str = ""
    SSH_KEY_PATH: str = os.path.expanduser("~/.ssh/id_rsa")
    SSH_STRICT_HOST_KEY_CHECK: bool = False
    SSH_CONNECT_TIMEOUT: int = 10
    
    ALIYUN_ACCESS_KEY_ID: str = ""
    ALIYUN_ACCESS_KEY_SECRET: str = ""
    ALIYUN_REGION_ID: str = "cn-hangzhou"

    RDS_HOST: str = ""
    RDS_PORT: int = 3306
    RDS_USER: str = ""
    RDS_PASSWORD: str = ""
    RDS_DB_NAME: str = "aiops_platform"
    RDS_SSL_MODE: str = "REQUIRED"
    RDS_CONNECTION_TIMEOUT: int = 10
    RDS_MAX_CONNECTIONS: int = 20
    RDS_POOL_RECYCLE: int = 3600

    POLARDB_CLUSTER_ID: str = ""
    POLARDB_ENDPOINT_TYPE: str = "cluster"
    
    SMTP_HOST: str = "smtp.163.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    
    OPS_RAG_PATH: str = str(Path.home() / "ops_rag")
    KNOWLEDGE_GRAPH_PATH: str = str(Path(__file__).parent.parent.parent.parent.parent / "knowledge_graph")
    
    CMDB_SERVICE_LIST: list = [
        "order-service",
        "payment-service", 
        "user-service",
        "inventory-service",
        "notification-service",
        "api-gateway",
        "redis-cluster",
        "mysql-master",
        "mysql-slave",
        "kafka-cluster",
        "elasticsearch-cluster"
    ]
    
    DATA_SOURCES: dict = {
        "local": {
            "type": "filesystem",
            "base_path": str(Path.home() / "AIops" / "GNN"),
            "description": "本地文件系统数据源"
        },
        "prometheus": {
            "type": "monitoring",
            "url": "http://localhost:9090",
            "description": "Prometheus 监控系统"
        },
        "elasticsearch": {
            "type": "logging",
            "url": "http://localhost:9200",
            "index_pattern": "logstash-*",
            "description": "Elasticsearch 日志平台"
        },
        "loki": {
            "type": "logging",
            "url": "http://localhost:3100",
            "description": "Grafana Loki 日志系统"
        },
        "aliyun_monitor": {
            "type": "cloud_monitoring",
            "enabled": True,
            "description": "阿里云云监控"
        },
        "jaeger": {
            "type": "tracing",
            "url": "http://localhost:16686",
            "description": "Jaeger 链路追踪"
        }
    }
    
    DEFAULT_DATA_SOURCE: str = "local"
    
    DANGEROUS_COMMANDS: list = [
        "rm -rf",
        "dd if=",
        "mkfs",
        "fdisk",
        "shutdown",
        "reboot",
        "init 0",
        "init 6",
        ":(){ :|:& };:",
        "chown -R",
        "> /dev/sda",
        "systemctl stop",
        "systemctl disable",
        "service.*stop",
        "kill -9 -1",
        "pkill -9",
        "drop database",
        "truncate table",
        "delete from"
    ]
    
    SAFE_COMMANDS: list = [
        "ls", "cat", "head", "tail", "grep", "awk", "sed", "cut",
        "df", "du", "free", "top", "htop", "ps", "uptime",
        "netstat", "ss", "lsof", "iostat", "vmstat", "sar",
        "ping", "traceroute", "nslookup", "dig", "curl", "wget --spider",
        "journalctl", "dmesg", "last", "w", "who",
        "systemctl status", "service.*status",
        "docker ps", "docker logs", "docker inspect", "docker stats",
        "kubectl get", "kubectl describe", "kubectl logs"
    ]
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

def validate_security_settings():
    warnings_list = []
    if not settings.SECRET_KEY:
        warnings_list.append("SECRET_KEY 未设置，请在 .env 中配置")
    if not settings.NEO4J_PASSWORD:
        warnings_list.append("NEO4J_PASSWORD 未设置，请在 .env 中配置")
    if not settings.SSH_USER:
        warnings_list.append("SSH_USER 未设置，远程命令执行将不可用，请在 .env 中配置")
    if not settings.SSH_STRICT_HOST_KEY_CHECK:
        warnings_list.append("SSH_STRICT_HOST_KEY_CHECK=False，生产环境建议启用主机密钥验证")
    for w in warnings_list:
        warnings.warn(w, UserWarning, stacklevel=2)
    return warnings_list
