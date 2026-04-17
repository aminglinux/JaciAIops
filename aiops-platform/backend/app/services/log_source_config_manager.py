import json
import base64
import hashlib
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import AuditLog, LogSourceConfig, SessionLocal


class LogSourceConfigManager:
    def _get_fernet(self) -> Fernet:
        seed = settings.SECRET_KEY or "aiops-platform-dev-secret"
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def _encrypt_secret(self, raw_value: str) -> str:
        if not raw_value:
            return ""
        return self._get_fernet().encrypt(raw_value.encode("utf-8")).decode("utf-8")

    def decrypt_secret(self, encrypted_value: str) -> str:
        if not encrypted_value:
            return ""
        try:
            return self._get_fernet().decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError):
            return encrypted_value

    def _mask_secret(self, value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}****{value[-4:]}"

    def _ensure_schema(self, db: Session) -> None:
        columns = {
            "elasticsearch_auth_type": "VARCHAR(30) DEFAULT 'none' NOT NULL",
            "elasticsearch_username": "VARCHAR(255) DEFAULT '' NOT NULL",
            "elasticsearch_password_encrypted": "TEXT DEFAULT '' NOT NULL",
            "elasticsearch_password_masked": "VARCHAR(100) DEFAULT '' NOT NULL",
            "elasticsearch_api_key_encrypted": "TEXT DEFAULT '' NOT NULL",
            "elasticsearch_api_key_masked": "VARCHAR(100) DEFAULT '' NOT NULL",
            "elasticsearch_tls_verify": "BOOLEAN DEFAULT 1 NOT NULL",
        }
        try:
            existing_columns = {row[1] for row in db.execute(text("PRAGMA table_info(log_source_configs)")).fetchall()}
            for column_name, column_definition in columns.items():
                if column_name not in existing_columns:
                    db.execute(text(f"ALTER TABLE log_source_configs ADD COLUMN {column_name} {column_definition}"))
            db.commit()
        except Exception:
            db.rollback()

    def _get_or_create(self, db: Session) -> LogSourceConfig:
        self._ensure_schema(db)
        config = db.query(LogSourceConfig).order_by(LogSourceConfig.id.asc()).first()
        if config:
            return config

        elasticsearch_config = settings.DATA_SOURCES.get("elasticsearch", {})
        loki_config = settings.DATA_SOURCES.get("loki", {})
        config = LogSourceConfig(
            elasticsearch_enabled=True,
            elasticsearch_url=str(elasticsearch_config.get("url", "http://localhost:9200")),
            elasticsearch_index_pattern=str(elasticsearch_config.get("index_pattern", "logstash-*")),
            loki_enabled=True,
            loki_url=str(loki_config.get("url", "http://localhost:3100")),
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        return config

    def _serialize(self, config: LogSourceConfig) -> Dict[str, Any]:
        return {
            "elasticsearchEnabled": config.elasticsearch_enabled,
            "elasticsearchUrl": config.elasticsearch_url,
            "elasticsearchIndexPattern": config.elasticsearch_index_pattern,
            "elasticsearchAuthType": config.elasticsearch_auth_type,
            "elasticsearchUsername": config.elasticsearch_username,
            "elasticsearchPasswordMasked": config.elasticsearch_password_masked,
            "elasticsearchApiKeyMasked": config.elasticsearch_api_key_masked,
            "elasticsearchTlsVerify": config.elasticsearch_tls_verify,
            "lokiEnabled": config.loki_enabled,
            "lokiUrl": config.loki_url,
            "updatedBy": config.updated_by,
            "updatedAt": config.updated_at.isoformat() if config.updated_at else None,
        }

    def _serialize_effective(self, config: LogSourceConfig) -> Dict[str, Any]:
        return {
            **self._serialize(config),
            "elasticsearchPassword": self.decrypt_secret(config.elasticsearch_password_encrypted),
            "elasticsearchApiKey": self.decrypt_secret(config.elasticsearch_api_key_encrypted),
        }

    def _build_audit_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        audit_payload = dict(payload)
        if audit_payload.get("elasticsearch_password"):
            audit_payload["elasticsearch_password"] = "***"
        if audit_payload.get("elasticsearch_api_key"):
            audit_payload["elasticsearch_api_key"] = "***"
        return audit_payload

    def get_config(self, db: Session) -> Dict[str, Any]:
        return self._serialize(self._get_or_create(db))

    def get_effective_config(self) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            return self._serialize_effective(self._get_or_create(db))
        finally:
            db.close()

    def update_config(self, db: Session, payload: Dict[str, Any], operator: str) -> Dict[str, Any]:
        config = self._get_or_create(db)

        if payload.get("elasticsearch_enabled") is not None:
            config.elasticsearch_enabled = bool(payload["elasticsearch_enabled"])
        if payload.get("elasticsearch_url") is not None:
            config.elasticsearch_url = str(payload["elasticsearch_url"]).strip()
        if payload.get("elasticsearch_index_pattern") is not None:
            config.elasticsearch_index_pattern = str(payload["elasticsearch_index_pattern"]).strip() or "logstash-*"
        if payload.get("elasticsearch_auth_type") is not None:
            auth_type = str(payload["elasticsearch_auth_type"]).strip() or "none"
            if auth_type not in {"none", "basic", "api_key"}:
                raise ValueError("不支持的 Elasticsearch 认证方式")
            config.elasticsearch_auth_type = auth_type
            if auth_type == "none":
                config.elasticsearch_username = ""
                config.elasticsearch_password_encrypted = ""
                config.elasticsearch_password_masked = ""
                config.elasticsearch_api_key_encrypted = ""
                config.elasticsearch_api_key_masked = ""
            elif auth_type == "basic":
                config.elasticsearch_api_key_encrypted = ""
                config.elasticsearch_api_key_masked = ""
            elif auth_type == "api_key":
                config.elasticsearch_username = ""
                config.elasticsearch_password_encrypted = ""
                config.elasticsearch_password_masked = ""
        if config.elasticsearch_auth_type == "basic" and payload.get("elasticsearch_username") is not None:
            config.elasticsearch_username = str(payload["elasticsearch_username"]).strip()
        if config.elasticsearch_auth_type == "basic" and payload.get("elasticsearch_password"):
            password = str(payload["elasticsearch_password"])
            config.elasticsearch_password_encrypted = self._encrypt_secret(password)
            config.elasticsearch_password_masked = self._mask_secret(password)
        if config.elasticsearch_auth_type == "api_key" and payload.get("elasticsearch_api_key"):
            api_key = str(payload["elasticsearch_api_key"])
            config.elasticsearch_api_key_encrypted = self._encrypt_secret(api_key)
            config.elasticsearch_api_key_masked = self._mask_secret(api_key)
        if payload.get("elasticsearch_tls_verify") is not None:
            config.elasticsearch_tls_verify = bool(payload["elasticsearch_tls_verify"])
        if payload.get("loki_enabled") is not None:
            config.loki_enabled = bool(payload["loki_enabled"])
        if payload.get("loki_url") is not None:
            config.loki_url = str(payload["loki_url"]).strip()

        config.updated_by = operator
        db.add(config)
        db.add(
            AuditLog(
                operator=operator,
                action="update_log_source_config",
                target_type="log_source_config",
                target_id=str(config.id or "singleton"),
                detail_json=json.dumps(self._build_audit_payload(payload), ensure_ascii=False),
            )
        )
        db.commit()
        db.refresh(config)
        return self._serialize(config)


log_source_config_manager = LogSourceConfigManager()
