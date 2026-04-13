import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import AuditLog, RuntimeGraphConfig, SessionLocal


class RuntimeGraphConfigManager:
    def _default_services(self) -> List[str]:
        return list(settings.CMDB_SERVICE_LIST or [])

    def _get_or_create(self, db: Session) -> RuntimeGraphConfig:
        config = db.query(RuntimeGraphConfig).order_by(RuntimeGraphConfig.id.asc()).first()
        if config:
            return config

        config = RuntimeGraphConfig(
            trace_backend=settings.TRACE_BACKEND,
            jaeger_query_url=settings.JAEGER_QUERY_URL,
            tempo_query_url=settings.TEMPO_QUERY_URL,
            trace_query_timeout=settings.TRACE_QUERY_TIMEOUT,
            trace_default_lookback_minutes=settings.TRACE_DEFAULT_LOOKBACK_MINUTES,
            runtime_graph_enabled=settings.RUNTIME_GRAPH_ENABLED,
            cmdb_service_list_json=json.dumps(self._default_services(), ensure_ascii=False),
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        return config

    def _serialize(self, config: RuntimeGraphConfig) -> Dict[str, Any]:
        try:
            service_list = json.loads(config.cmdb_service_list_json or "[]")
        except json.JSONDecodeError:
            service_list = []

        return {
            "traceBackend": config.trace_backend,
            "jaegerQueryUrl": config.jaeger_query_url,
            "tempoQueryUrl": config.tempo_query_url,
            "traceQueryTimeout": config.trace_query_timeout,
            "traceDefaultLookbackMinutes": config.trace_default_lookback_minutes,
            "runtimeGraphEnabled": config.runtime_graph_enabled,
            "serviceList": service_list,
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
        service_list = payload.get("service_list")
        if service_list is not None and not isinstance(service_list, list):
            raise ValueError("service_list 必须为数组")

        if payload.get("trace_backend") is not None:
            config.trace_backend = str(payload["trace_backend"]).strip() or "jaeger"
        if payload.get("jaeger_query_url") is not None:
            config.jaeger_query_url = str(payload["jaeger_query_url"]).strip()
        if payload.get("tempo_query_url") is not None:
            config.tempo_query_url = str(payload["tempo_query_url"]).strip()
        if payload.get("trace_query_timeout") is not None:
            config.trace_query_timeout = max(1, int(payload["trace_query_timeout"]))
        if payload.get("trace_default_lookback_minutes") is not None:
            config.trace_default_lookback_minutes = max(1, int(payload["trace_default_lookback_minutes"]))
        if payload.get("runtime_graph_enabled") is not None:
            config.runtime_graph_enabled = bool(payload["runtime_graph_enabled"])
        if service_list is not None:
            normalized = [str(item).strip() for item in service_list if str(item).strip()]
            config.cmdb_service_list_json = json.dumps(normalized, ensure_ascii=False)

        config.updated_by = operator
        db.add(config)
        db.add(
            AuditLog(
                operator=operator,
                action="update_runtime_graph_config",
                target_type="runtime_graph_config",
                target_id=str(config.id or "singleton"),
                detail_json=json.dumps(payload, ensure_ascii=False),
            )
        )
        db.commit()
        db.refresh(config)
        return self._serialize(config)


runtime_graph_config_manager = RuntimeGraphConfigManager()
