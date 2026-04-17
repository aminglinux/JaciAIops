import json
import asyncio
import uuid
from copy import deepcopy
from collections import Counter
from datetime import timedelta
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents import MultiAgentOrchestrator
from app.api.auth import User, get_current_user, require_admin
from app.core.config import settings
from app.core.database import AlertEvent, Log, SessionLocal, get_db
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


ALERT_ANALYZE_TIMEOUT_SECONDS = max(30, int(settings.ALERT_RCA_TIMEOUT_SECONDS))
LOG_ANALYZE_TASK_KEEP = 50
LOG_ANALYZE_HISTORY_LIMIT = 30
_log_analyze_tasks: Dict[str, Dict[str, Any]] = {}
_log_analyze_task_lock = asyncio.Lock()


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


def _safe_content_preview(content: str, max_len: int = 220) -> str:
    normalized = (content or "").replace("\n", " ").strip()
    return normalized[:max_len]


def _build_anomaly_log_samples(logs: List[Log], max_samples: int = 5) -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []
    for item in logs[:max_samples]:
        samples.append(
            {
                "id": item.id,
                "timestamp": item.timestamp.isoformat() if item.timestamp else "",
                "level": item.level,
                "content_preview": _safe_content_preview(item.content or ""),
                "upload_batch_id": item.upload_batch_id,
                "anomaly_score": item.anomaly_score,
            }
        )
    return samples


async def _append_log_task_event(task_id: str, event: Dict[str, Any]) -> None:
    async with _log_analyze_task_lock:
        task = _log_analyze_tasks.get(task_id)
        if not task:
            return
        events = task.setdefault("events", [])
        events.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "node": event.get("node", "unknown"),
                "status": event.get("status", "info"),
                "description": event.get("description", ""),
                "detail": event.get("detail"),
            }
        )
        task["updated_at"] = datetime.utcnow().isoformat()


async def _update_log_task(task_id: str, **kwargs: Any) -> None:
    async with _log_analyze_task_lock:
        task = _log_analyze_tasks.get(task_id)
        if not task:
            return
        for key, value in kwargs.items():
            task[key] = value
        task["updated_at"] = datetime.utcnow().isoformat()


async def _create_log_task_record(task_id: str, payload: LogAnomalyAnalyzePayload) -> None:
    async with _log_analyze_task_lock:
        _log_analyze_tasks[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "params": payload.model_dump(),
            "events": [],
            "result": None,
            "error": None,
            "event_id": None,
        }
        if len(_log_analyze_tasks) > LOG_ANALYZE_TASK_KEEP:
            ordered = sorted(
                _log_analyze_tasks.items(),
                key=lambda item: item[1].get("updated_at", ""),
            )
            for old_task_id, _ in ordered[:-LOG_ANALYZE_TASK_KEEP]:
                _log_analyze_tasks.pop(old_task_id, None)


async def _run_log_analyze_task(task_id: str, payload: LogAnomalyAnalyzePayload) -> None:
    db = SessionLocal()
    try:
        await _update_log_task(task_id, status="running")
        await _append_log_task_event(
            task_id,
            {
                "node": "init",
                "status": "running",
                "description": "开始分析异常日志任务",
                "detail": payload.model_dump(),
            },
        )

        safe_lookback = max(1, min(payload.lookback_minutes, 24 * 60))
        safe_max_logs = max(20, min(payload.max_logs, 500))
        start_time = datetime.utcnow() - timedelta(minutes=safe_lookback)
        await _append_log_task_event(
            task_id,
            {
                "node": "filter_anomaly_logs",
                "status": "running",
                "description": "过滤异常日志",
                "detail": {"lookback_minutes": safe_lookback, "max_logs": safe_max_logs},
            },
        )

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

        await _append_log_task_event(
            task_id,
            {
                "node": "filter_anomaly_logs",
                "status": "completed",
                "description": "异常日志过滤完成",
                "detail": {
                    "anomaly_logs": len(anomaly_logs),
                    "samples": _build_anomaly_log_samples(anomaly_logs),
                },
            },
        )

        await _append_log_task_event(
            task_id,
            {
                "node": "build_alert_context",
                "status": "running",
                "description": "构建告警上下文",
            },
        )
        analyze_request = _build_log_analyze_request(anomaly_logs, payload)
        alert = alert_normalizer.normalize_custom(analyze_request)
        query = alert_normalizer.build_rca_query(alert)
        await _append_log_task_event(
            task_id,
            {
                "node": "build_alert_context",
                "status": "completed",
                "description": "告警上下文构建完成",
                "detail": {
                    "alert_name": alert.alert_name,
                    "service": alert.service,
                    "instance": alert.instance,
                },
            },
        )

        current_loop = asyncio.get_running_loop()
        def _progress_callback(event: Dict[str, Any]) -> None:
            current_loop.call_soon_threadsafe(
                asyncio.create_task,
                _append_log_task_event(task_id, event),
            )

        await _append_log_task_event(
            task_id,
            {
                "node": "rca_workflow",
                "status": "running",
                "description": "开始执行 RCA 工作流",
            },
        )
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_alert_rca_with_progress_sync, query, _progress_callback),
            timeout=ALERT_ANALYZE_TIMEOUT_SECONDS,
        )

        async with _log_analyze_task_lock:
            task_snapshot = deepcopy(_log_analyze_tasks.get(task_id, {}))
        result["process_events"] = task_snapshot.get("events", [])
        event = _save_alert_event(db, alert, query, result)
        response = _build_response(alert, query, result, event.id)
        response["anomaly_logs"] = len(anomaly_logs)
        response["lookback_minutes"] = safe_lookback
        response["task_id"] = task_id

        await _append_log_task_event(
            task_id,
            {
                "node": "rca_workflow",
                "status": "completed",
                "description": "RCA 工作流执行完成",
                "detail": {"event_id": event.id},
            },
        )
        await _update_log_task(
            task_id,
            status="completed",
            result=response,
            event_id=event.id,
        )
    except HTTPException as exc:
        await _append_log_task_event(
            task_id,
            {
                "node": "finalize",
                "status": "failed",
                "description": "分析任务失败",
                "detail": {"error": exc.detail},
            },
        )
        await _update_log_task(task_id, status="failed", error=str(exc.detail))
    except asyncio.TimeoutError:
        await _append_log_task_event(
            task_id,
            {
                "node": "finalize",
                "status": "failed",
                "description": "分析任务超时",
                "detail": {"timeout_seconds": ALERT_ANALYZE_TIMEOUT_SECONDS},
            },
        )
        await _update_log_task(task_id, status="failed", error=f"RCA workflow timeout after {ALERT_ANALYZE_TIMEOUT_SECONDS}s")
    except Exception as exc:
        await _append_log_task_event(
            task_id,
            {
                "node": "finalize",
                "status": "failed",
                "description": "分析任务异常",
                "detail": {"error": str(exc)},
            },
        )
        await _update_log_task(task_id, status="failed", error=str(exc))
    finally:
        db.close()


def _run_alert_rca_with_progress_sync(
    query: str,
    progress_callback,
) -> Dict[str, Any]:
    local_orchestrator = MultiAgentOrchestrator()
    return asyncio.run(local_orchestrator.process_query_with_progress(query, progress_callback=progress_callback))


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


@router.post("/analyze-from-logs/start")
async def start_analyze_from_uploaded_logs(
    payload: LogAnomalyAnalyzePayload,
    _: User = Depends(get_current_user),
):
    task_id = uuid.uuid4().hex
    await _create_log_task_record(task_id, payload)
    asyncio.create_task(_run_log_analyze_task(task_id, payload))
    return {
        "task_id": task_id,
        "status": "queued",
        "message": "已启动异常日志分析任务",
    }


@router.get("/analyze-from-logs/tasks/{task_id}")
async def get_analyze_from_logs_task(
    task_id: str,
    _: User = Depends(get_current_user),
):
    async with _log_analyze_task_lock:
        task = _log_analyze_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="分析任务不存在或已过期")
        return deepcopy(task)


@router.get("/analyze-from-logs/tasks/{task_id}/stream")
async def stream_analyze_from_logs_task(
    task_id: str,
    _: User = Depends(get_current_user),
):
    async def event_generator():
        last_event_index = 0
        while True:
            async with _log_analyze_task_lock:
                task = deepcopy(_log_analyze_tasks.get(task_id))
            if not task:
                payload = {"type": "error", "message": "分析任务不存在或已过期"}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                return

            events = task.get("events", []) if isinstance(task, dict) else []
            if last_event_index == 0:
                yield f"data: {json.dumps({'type': 'meta', 'task_id': task_id, 'status': task.get('status'), 'created_at': task.get('created_at')}, ensure_ascii=False)}\n\n"
            for event in events[last_event_index:]:
                yield f"data: {json.dumps({'type': 'event', 'event': event, 'task_id': task_id, 'status': task.get('status')}, ensure_ascii=False)}\n\n"
            last_event_index = len(events)

            status = task.get("status")
            if status in {"completed", "failed"}:
                done_payload = {
                    "type": "done",
                    "task_id": task_id,
                    "status": status,
                    "error": task.get("error"),
                    "result": task.get("result"),
                    "event_id": task.get("event_id"),
                }
                yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
                return

            await asyncio.sleep(0.35)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/analyze-from-logs/history")
async def get_analyze_from_logs_history(
    limit: int = LOG_ANALYZE_HISTORY_LIMIT,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(limit, LOG_ANALYZE_HISTORY_LIMIT))
    task_history: List[Dict[str, Any]] = []
    async with _log_analyze_task_lock:
        task_snapshots = deepcopy(list(_log_analyze_tasks.values()))
    for task in task_snapshots:
        if not isinstance(task, dict):
            continue
        status = str(task.get("status") or "")
        if status not in {"completed", "failed"}:
            continue
        if task.get("event_id"):
            continue
        params = task.get("params", {}) if isinstance(task.get("params"), dict) else {}
        events = task.get("events", []) if isinstance(task.get("events"), list) else []
        task_history.append(
            {
                "task_id": task.get("task_id"),
                "event_id": None,
                "alert_name": params.get("alert_name") or "UploadedLogAnomalyBurst",
                "status": status,
                "created_at": task.get("created_at"),
                "service": params.get("service"),
                "severity": params.get("severity") or "warning",
                "root_cause_summary": task.get("error") or "",
                "process_events_count": len(events),
                "is_failed_task": status == "failed",
            }
        )

    events = (
        db.query(AlertEvent)
        .filter(AlertEvent.source == "log_upload")
        .order_by(AlertEvent.created_at.desc())
        .limit(safe_limit * 2)
        .all()
    )
    history: List[Dict[str, Any]] = []
    for event in events:
        rca_payload = _safe_json_loads(event.rca_json, {})
        final_decision = _safe_json_loads(event.final_decision_json, {})
        process_events = rca_payload.get("process_events", []) if isinstance(rca_payload, dict) else []
        history.append(
            {
                "task_id": None,
                "event_id": event.id,
                "alert_name": event.alert_name,
                "status": event.status,
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "service": event.service,
                "severity": event.severity,
                "root_cause_summary": final_decision.get("root_cause_summary") if isinstance(final_decision, dict) else "",
                "process_events_count": len(process_events) if isinstance(process_events, list) else 0,
                "is_failed_task": False,
            }
        )

    merged = history + task_history
    merged.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {"history": merged[:safe_limit]}


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
