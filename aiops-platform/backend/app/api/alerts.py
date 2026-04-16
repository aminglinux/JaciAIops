import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents import MultiAgentOrchestrator
from app.api.auth import User, get_current_user, require_admin
from app.core.database import AlertEvent, get_db
from app.services import alert_security_config_manager, ip_access_controller
from app.services.alert_normalizer import AlertAnalyzeRequest, NormalizedAlert, alert_normalizer

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
orchestrator = MultiAgentOrchestrator()


class AlertEventSummary(BaseModel):
    id: int
    source: str
    alert_name: str
    severity: str
    service: Optional[str] = None
    instance: Optional[str] = None
    status: str
    fingerprint: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    description: str = ""
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AlertEventDetail(AlertEventSummary):
    labels: Dict[str, Any]
    annotations: Dict[str, Any]
    alert: Dict[str, Any]
    query: str
    rca: Dict[str, Any]
    final_decision: Optional[Dict[str, Any]] = None


class AlertWebhookSecurityConfigPayload(BaseModel):
    ip_whitelist: str = ""
    trust_proxy_headers: bool = False


def _safe_json_loads(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    normalized = normalized.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _build_response(alert: NormalizedAlert, query: str, result: Dict[str, Any], event_id: Optional[int] = None) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "alert": alert.model_dump(),
        "query": query,
        "rca": result,
        "final_decision": result.get("final_decision"),
        "mode": "alert_rca",
    }


def _serialize_event(event: AlertEvent) -> AlertEventDetail:
    return AlertEventDetail(
        id=event.id,
        source=event.source,
        alert_name=event.alert_name,
        severity=event.severity,
        service=event.service,
        instance=event.instance,
        status=event.status,
        fingerprint=event.fingerprint,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        description=event.description,
        error_message=event.error_message,
        created_at=event.created_at,
        updated_at=event.updated_at,
        labels=_safe_json_loads(event.labels_json, {}),
        annotations=_safe_json_loads(event.annotations_json, {}),
        alert=_safe_json_loads(event.normalized_alert_json, {}),
        query=event.query_text,
        rca=_safe_json_loads(event.rca_json, {}),
        final_decision=_safe_json_loads(event.final_decision_json, None),
    )


def _save_alert_event(
    db: Session,
    alert: NormalizedAlert,
    query: str,
    result: Dict[str, Any],
    fingerprint: Optional[str] = None,
) -> AlertEvent:
    final_decision = result.get("final_decision")
    error_message = result.get("error")
    status = "failed" if error_message else "completed"
    event = AlertEvent(
        source=alert.source,
        alert_name=alert.alert_name,
        severity=alert.severity,
        service=alert.service,
        instance=alert.instance,
        status=status,
        fingerprint=fingerprint,
        starts_at=_parse_iso_datetime(alert.starts_at),
        ends_at=_parse_iso_datetime(alert.ends_at),
        query_text=query,
        description=alert.description or "",
        labels_json=json.dumps(alert.labels, ensure_ascii=False, default=str),
        annotations_json=json.dumps(alert.annotations, ensure_ascii=False, default=str),
        normalized_alert_json=json.dumps(alert.model_dump(), ensure_ascii=False, default=str),
        rca_json=json.dumps(result, ensure_ascii=False, default=str),
        final_decision_json=json.dumps(final_decision, ensure_ascii=False, default=str) if final_decision is not None else None,
        error_message=str(error_message) if error_message else None,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/events")
async def list_alert_events(
    limit: int = 20,
    source: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    safe_limit = max(1, min(limit, 100))
    query = db.query(AlertEvent)
    if source:
        query = query.filter(AlertEvent.source == source)
    if status:
        query = query.filter(AlertEvent.status == status)
    events = query.order_by(AlertEvent.created_at.desc()).limit(safe_limit).all()
    return {
        "events": [
            AlertEventSummary(
                id=event.id,
                source=event.source,
                alert_name=event.alert_name,
                severity=event.severity,
                service=event.service,
                instance=event.instance,
                status=event.status,
                fingerprint=event.fingerprint,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                description=event.description,
                error_message=event.error_message,
                created_at=event.created_at,
                updated_at=event.updated_at,
            ).model_dump()
            for event in events
        ]
    }


@router.get("/events/{event_id}")
async def get_alert_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    event = db.query(AlertEvent).filter(AlertEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="告警事件不存在")
    return _serialize_event(event).model_dump()


@router.get("/security-config")
async def get_alert_security_config(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return {
        "code": 200,
        "message": "success",
        "data": alert_security_config_manager.get_config(db),
    }


@router.put("/security-config")
async def update_alert_security_config(
    payload: AlertWebhookSecurityConfigPayload,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return {
        "code": 200,
        "message": "success",
        "data": alert_security_config_manager.update_config(db, payload.model_dump(), current_user.username),
    }


@router.post("/analyze")
async def analyze_alert(
    request: AlertAnalyzeRequest,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = alert_normalizer.normalize_custom(request)
    query = alert_normalizer.build_rca_query(alert)
    result = await orchestrator.process_query(query)
    event = _save_alert_event(db, alert, query, result)
    return _build_response(alert, query, result, event.id)


@router.post("/webhook/alertmanager")
async def analyze_alertmanager_webhook(
    request: Request,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    ip_access_controller.enforce_alert_webhook_whitelist(request)
    alerts = alert_normalizer.normalize_alertmanager(payload)
    results: List[Dict[str, Any]] = []
    for alert in alerts:
        query = alert_normalizer.build_rca_query(alert)
        result = await orchestrator.process_query(query)
        fingerprint = str(alert.annotations.get("fingerprint") or alert.labels.get("fingerprint") or payload.get("groupKey") or "")
        event = _save_alert_event(db, alert, query, result, fingerprint=fingerprint or None)
        results.append(_build_response(alert, query, result, event.id))
    return {
        "count": len(results),
        "results": results,
        "mode": "alertmanager_rca",
    }
