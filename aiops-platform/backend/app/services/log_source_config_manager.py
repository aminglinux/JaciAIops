import json
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import AuditLog, LogSourceConfig, SessionLocal


class LogSourceConfigManager:
    def _get_or_create(self, db: Session) -> LogSourceConfig:
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
            "lokiEnabled": config.loki_enabled,
            "lokiUrl": config.loki_url,
            "updatedBy": config.updated_by,
            "updatedAt": config.updated_at.isoformat() if config.updated_at else None,
        }

    def get_config(self, db: Session) -> Dict[str, Any]:
        return self._serialize(self._get_or_create(db))

    def get_effective_config(self) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            return self.get_config(db)
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
                detail_json=json.dumps(payload, ensure_ascii=False),
            )
        )
        db.commit()
        db.refresh(config)
        return self._serialize(config)


log_source_config_manager = LogSourceConfigManager()
