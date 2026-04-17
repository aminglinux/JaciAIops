import json
import asyncio
from collections import Counter
from datetime import timedelta
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents import MultiAgentOrchestrator
from app.api.auth import User, get_current_user, require_admin
from app.core.database import AlertEvent, Log, get_db
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


class LogAnomalyAnalyzePayload(BaseModel):
    lookback_minutes: int = 30
    max_logs: int = 200
    alert_name: Optional[str] = None
    severity: str = "warning"
    service: Optional[str] = None


ALERT_ANALYZE_TIMEOUT_SECONDS = 50


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


def _extract_log_context(content: str) -> Dict[str, str]:
    try:
        payload = json.loads(content)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}

    service = payload.get("service") or payload.get("app")
    instance = payload.get("instance") or payload.get("host") or payload.get("pod")
    metric_name = payload.get("metric_name")
    return {
        "service": str(service) if service else "",
        "instance": str(instance) if instance else "",
        "metric_name": str(metric_name) if metric_name else "",
    }


def _build_log_analyze_request(logs: List[Log], payload: LogAnomalyAnalyzePayload) -> AlertAnalyzeRequest:
    service_counter: Counter[str] = Counter()
    instance_counter: Counter[str] = Counter()
    metric_counter: Counter[str] = Counter()
    sample_errors: List[str] = []

    for item in logs:
        context = _extract_log_context(item.content or "")
        if context.get("service"):
            service_counter[context["service"]] += 1
        if context.get("instance"):
            instance_counter[context["instance"]] += 1
        if context.get("metric_name"):
            metric_counter[context["metric_name"]] += 1
        if item.level in {"ERROR", "WARN"} and len(sample_errors) < 5:
            sample_errors.append((item.content or "")[:180])

    detected_service = payload.service or (service_counter.most_common(1)[0][0] if service_counter else None)
    detected_instance = instance_counter.most_common(1)[0][0] if instance_counter else None
    detected_metric = metric_counter.most_common(1)[0][0] if metric_counter else "anomaly_logs.count"

    starts_at = min(item.timestamp for item in logs).isoformat() if logs else None
    ends_at = max(item.timestamp for item in logs).isoformat() if logs else None
    total_anomalies = len(logs)

    labels: Dict[str, Any] = {
        "source_type": "uploaded_logs",
        "anomaly_count": total_anomalies,
        "top_services": [name for name, _ in service_counter.most_common(3)],
        "top_instances": [name for name, _ in instance_counter.most_common(3)],
    }
    annotations: Dict[str, Any] = {
        "summary": f"检测到 {total_anomalies} 条异常日志，触发根因分析",
        "sample_errors": sample_errors,
    }

    return AlertAnalyzeRequest(
        alert_name=payload.alert_name or "UploadedLogAnomalyBurst",
        severity=payload.severity or "warning",
        service=detected_service,
        instance=detected_instance,
        metric_name=detected_metric,
        metric_value=float(total_anomalies),
        threshold=max(1.0, float(total_anomalies // 2)),
        starts_at=starts_at,
        ends_at=ends_at,
        description=f"日志上传后发现异常日志激增，共 {total_anomalies} 条，需执行 RCA 工作流",
        labels=labels,
        annotations=annotations,
        source="log_upload",
        lookback_minutes=max(1, int(payload.lookback_minutes or 30)),
    )


def _build_response(alert: NormalizedAlert, query: str, result: Dict[str, Any], event_id: Optional[int] = None) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "alert": alert.model_dump(),
        "query": query,
        "rca": result,
        "final_decision": result.get("final_decision"),
        "warnings": result.get("warnings", []),
        "mode": "alert_rca",
    }


async def _run_rca_with_timeout(query: str, timeout_seconds: int = ALERT_ANALYZE_TIMEOUT_SECONDS) -> Dict[str, Any]:
    try:
        return await asyncio.wait_for(orchestrator.process_query(query), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return {
            "error": f"RCA workflow timeout after {timeout_seconds}s",
            "warnings": [
                {
                    "code": "RCA_TIMEOUT",
                    "message": f"RCA 分析超过 {timeout_seconds}s，已超时终止。",
                    "impact": "请检查 LLM/RAG/可观测数据源连通性，或缩小分析范围后重试",
                }
            ],
            "final_decision": {
                "decision": "TIMEOUT",
                "root_cause_summary": "分析超时，未生成完整根因结论",
                "action_plan": "建议先校验大模型配置可用性，再缩小回看窗口重试",
            },
            "mode": "alert_rca_timeout",
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
    result = await _run_rca_with_timeout(query)
    event = _save_alert_event(db, alert, query, result)
    return _build_response(alert, query, result, event.id)


@router.post("/analyze-from-logs")
async def analyze_from_uploaded_logs(
    payload: LogAnomalyAnalyzePayload,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    safe_lookback = max(1, min(payload.lookback_minutes, 24 * 60))
    safe_max_logs = max(20, min(payload.max_logs, 500))
    start_time = datetime.utcnow() - timedelta(minutes=safe_lookback)

    uploaded_log_exists = db.query(Log.id).filter(Log.source == "file").first()
    if not uploaded_log_exists:
        raise HTTPException(status_code=400, detail="请先上传日志")

    anomaly_logs = (
        db.query(Log)
        .filter(Log.source == "file")
        .filter(Log.is_anomaly == True)
        .filter(Log.timestamp >= start_time)
        .order_by(Log.timestamp.desc())
        .limit(safe_max_logs)
        .all()
    )
    if not anomaly_logs:
        raise HTTPException(status_code=400, detail="上传日志中未发现异常日志，无法触发根因分析")

    analyze_request = _build_log_analyze_request(anomaly_logs, payload)
    alert = alert_normalizer.normalize_custom(analyze_request)
    query = alert_normalizer.build_rca_query(alert)
    result = await _run_rca_with_timeout(query)
    event = _save_alert_event(db, alert, query, result)

    response = _build_response(alert, query, result, event.id)
    response["anomaly_logs"] = len(anomaly_logs)
    response["lookback_minutes"] = safe_lookback
    return response


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
        result = await _run_rca_with_timeout(query)
        fingerprint = str(alert.annotations.get("fingerprint") or alert.labels.get("fingerprint") or payload.get("groupKey") or "")
        event = _save_alert_event(db, alert, query, result, fingerprint=fingerprint or None)
        results.append(_build_response(alert, query, result, event.id))
    return {
        "count": len(results),
        "results": results,
        "mode": "alertmanager_rca",
    }
