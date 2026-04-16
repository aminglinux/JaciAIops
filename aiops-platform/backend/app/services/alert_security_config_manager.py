import json
from ipaddress import ip_address, ip_network
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import AlertWebhookSecurityConfig, AuditLog, SessionLocal


class AlertSecurityConfigManager:
    def _normalize_whitelist_items(self, raw_whitelist: Any) -> str:
        if isinstance(raw_whitelist, list):
            items = [str(item).strip() for item in raw_whitelist if str(item).strip()]
        else:
            items = [item.strip() for item in str(raw_whitelist or "").split(",") if item.strip()]

        invalid_items = []
        for item in items:
            try:
                if "/" in item:
                    ip_network(item, strict=False)
                else:
                    ip_address(item)
            except ValueError:
                invalid_items.append(item)

        if invalid_items:
            raise HTTPException(
                status_code=400,
                detail=f"白名单格式不正确: {', '.join(invalid_items)}",
            )

        return ",".join(items)

    def _get_or_create(self, db: Session) -> AlertWebhookSecurityConfig:
        config = db.query(AlertWebhookSecurityConfig).order_by(AlertWebhookSecurityConfig.id.asc()).first()
        if config:
            return config

        config = AlertWebhookSecurityConfig(
            ip_whitelist=str(settings.ALERT_WEBHOOK_IP_WHITELIST or "").strip(),
            trust_proxy_headers=bool(settings.ALERT_WEBHOOK_TRUST_PROXY_HEADERS),
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        return config

    def _serialize(self, config: AlertWebhookSecurityConfig) -> Dict[str, Any]:
        whitelist_items = [item.strip() for item in (config.ip_whitelist or "").split(",") if item.strip()]
        return {
            "ipWhitelist": whitelist_items,
            "ipWhitelistText": ", ".join(whitelist_items),
            "trustProxyHeaders": config.trust_proxy_headers,
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

        if payload.get("ip_whitelist") is not None:
            config.ip_whitelist = self._normalize_whitelist_items(payload.get("ip_whitelist"))

        if payload.get("trust_proxy_headers") is not None:
            config.trust_proxy_headers = bool(payload["trust_proxy_headers"])

        config.updated_by = operator
        db.add(config)
        db.add(
            AuditLog(
                operator=operator,
                action="update_alert_webhook_security_config",
                target_type="alert_webhook_security_config",
                target_id=str(config.id or "singleton"),
                detail_json=json.dumps(payload, ensure_ascii=False),
            )
        )
        db.commit()
        db.refresh(config)
        return self._serialize(config)


alert_security_config_manager = AlertSecurityConfigManager()
