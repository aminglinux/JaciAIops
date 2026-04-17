import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends
import httpx

from app.core.database import get_db, Log, Feedback
from app.core.config import settings
from app.api.auth import User, get_current_user, require_admin
from app.services import log_source_config_manager
from algorithm.anomaly_detector import AnomalyDetector

router = APIRouter(prefix="/api/logs", tags=["logs"])
logger = logging.getLogger(__name__)

detector = AnomalyDetector()

class LogCreate(BaseModel):
    level: str
    content: str
    source: str = "api"

class LogResponse(BaseModel):
    id: int
    timestamp: datetime
    level: str
    content: str
    source: str
    is_anomaly: bool
    anomaly_score: Optional[float]
    user_feedback: Optional[bool]

class FeedbackRequest(BaseModel):
    feedback_type: bool

class StatsResponse(BaseModel):
    total_logs: int
    anomaly_count: int
    anomaly_rate: float
    level_distribution: dict
    top_patterns: List[dict]


class UnifiedLogResponse(BaseModel):
    id: str
    timestamp: datetime
    level: str
    content: str
    source: str
    source_type: str = "local"
    service: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    is_anomaly: bool
    anomaly_score: Optional[float]
    user_feedback: Optional[bool]
    raw: Optional[Dict[str, Any]] = None


class LogSourceConfigPayload(BaseModel):
    elasticsearch_enabled: bool = True
    elasticsearch_url: str
    elasticsearch_index_pattern: str = "logstash-*"
    elasticsearch_auth_type: str = "none"
    elasticsearch_username: Optional[str] = ""
    elasticsearch_password: Optional[str] = ""
    elasticsearch_api_key: Optional[str] = ""
    elasticsearch_tls_verify: bool = True
    loki_enabled: bool = True
    loki_url: str


class LogSourceTestResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class UploadLogResponse(BaseModel):
    message: str
    filename: str
    logs_created: int
    anomaly_count: int
    upload_time: datetime


INCIDENT_KEYWORDS = ["error", "exception", "fail", "failed", "timeout", "refused", "panic", "oom", "fatal"]


def _normalize_level(content: str, level: Optional[str] = None) -> str:
    normalized = (level or "").upper().strip()
    if normalized in {"ERROR", "WARN", "INFO", "DEBUG"}:
        return normalized

    content_lower = (content or "").lower()
    if "error" in content_lower:
        return "ERROR"
    if "warn" in content_lower:
        return "WARN"
    if "debug" in content_lower:
        return "DEBUG"
    return "INFO"


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    normalized = normalized.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _to_iso_timestamp(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _build_local_log_response(log: Log) -> UnifiedLogResponse:
    return UnifiedLogResponse(
        id=str(log.id),
        timestamp=log.timestamp,
        level=log.level,
        content=log.content,
        source=log.source,
        source_type="local",
        service=None,
        labels=None,
        is_anomaly=log.is_anomaly,
        anomaly_score=log.anomaly_score,
        user_feedback=log.user_feedback,
        raw=None,
    )


def _resolve_elasticsearch_connection_config(payload: LogSourceConfigPayload) -> Dict[str, Any]:
    saved_config = log_source_config_manager.get_effective_config()
    auth_type = (payload.elasticsearch_auth_type or "none").strip() or "none"
    username = (payload.elasticsearch_username or "").strip()
    password = payload.elasticsearch_password or ""
    api_key = payload.elasticsearch_api_key or ""

    if auth_type == "basic":
        if not username:
            username = str(saved_config.get("elasticsearchUsername", "") or "")
        if not password and str(saved_config.get("elasticsearchAuthType", "")) == "basic":
            password = str(saved_config.get("elasticsearchPassword", "") or "")
    elif auth_type == "api_key":
        if not api_key and str(saved_config.get("elasticsearchAuthType", "")) == "api_key":
            api_key = str(saved_config.get("elasticsearchApiKey", "") or "")
    else:
        username = ""
        password = ""
        api_key = ""

    return {
        "base_url": str(payload.elasticsearch_url).rstrip("/"),
        "auth_type": auth_type,
        "username": username,
        "password": password,
        "api_key": api_key,
        "tls_verify": bool(payload.elasticsearch_tls_verify),
    }


def _resolve_loki_connection_config(payload: LogSourceConfigPayload) -> Dict[str, Any]:
    return {
        "base_url": str(payload.loki_url).rstrip("/"),
    }


def _extract_http_error_detail(response: httpx.Response) -> str:
    detail = f"HTTP {response.status_code}"
    try:
        payload = response.json()
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return detail

    error_obj = payload.get("error")
    if isinstance(error_obj, dict):
        error_type = error_obj.get("type")
        reason = error_obj.get("reason")
        if error_type and reason:
            return f"{detail}: {error_type} - {reason}"
        if error_type:
            return f"{detail}: {error_type}"
    if isinstance(error_obj, str):
        return f"{detail}: {error_obj}"

    return detail


async def _query_elasticsearch_logs(
    keyword: Optional[str],
    level: Optional[str],
    levels: Optional[List[str]],
    service: Optional[str],
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    limit: int,
    incident_only: bool,
) -> List[UnifiedLogResponse]:
    source_config = log_source_config_manager.get_effective_config()
    if not source_config["elasticsearchEnabled"]:
        raise ValueError("Elasticsearch 日志源未启用")
    base_url = str(source_config.get("elasticsearchUrl", "http://localhost:9200")).rstrip("/")
    index_pattern = str(source_config.get("elasticsearchIndexPattern", "logstash-*"))
    auth_type = str(source_config.get("elasticsearchAuthType", "none") or "none")
    username = str(source_config.get("elasticsearchUsername", "") or "")
    tls_verify = bool(source_config.get("elasticsearchTlsVerify", True))

    must_clauses: List[Dict[str, Any]] = []
    if keyword:
        must_clauses.append(
            {
                "simple_query_string": {
                    "query": keyword,
                    "fields": ["message", "content", "log", "service", "kubernetes.container_name"],
                    "default_operator": "and",
                }
            }
        )
    normalized_levels = [item for item in (levels or []) if item]
    if level and level not in normalized_levels:
        normalized_levels.append(level)
    if normalized_levels:
        must_clauses.append({"terms": {"level.keyword": normalized_levels}})
    if service:
        must_clauses.append(
            {
                "bool": {
                    "should": [
                        {"term": {"service.keyword": service}},
                        {"term": {"service_name.keyword": service}},
                        {"term": {"kubernetes.container_name.keyword": service}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )

    time_range: Dict[str, str] = {}
    if start_time:
        time_range["gte"] = _to_iso_timestamp(start_time) or ""
    if end_time:
        time_range["lte"] = _to_iso_timestamp(end_time) or ""
    if time_range:
        must_clauses.append({"range": {"@timestamp": time_range}})
    if incident_only:
        should_clauses = [{"term": {"level.keyword": "ERROR"}}, {"term": {"level.keyword": "WARN"}}]
        for incident_keyword in INCIDENT_KEYWORDS:
            should_clauses.append(
                {
                    "simple_query_string": {
                        "query": incident_keyword,
                        "fields": ["message", "content", "log"],
                    }
                }
            )
        must_clauses.append({"bool": {"should": should_clauses, "minimum_should_match": 1}})

    payload = {
        "size": limit,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {
            "bool": {
                "must": must_clauses or [{"match_all": {}}],
            }
        },
    }

    headers: Dict[str, str] = {}
    auth = None
    if auth_type == "basic":
        password = str(source_config.get("elasticsearchPassword", "") or "")
        if username and password:
            auth = (username, password)
    elif auth_type == "api_key":
        api_key = str(source_config.get("elasticsearchApiKey", "") or "")
        if api_key:
            headers["Authorization"] = f"ApiKey {api_key}"

    async with httpx.AsyncClient(timeout=20.0, verify=tls_verify) as client:
        try:
            response = await client.post(f"{base_url}/{index_pattern}/_search", json=payload, headers=headers, auth=auth)
            if response.status_code == 404:
                response_body = response.json()
                error_obj = response_body.get("error", {}) if isinstance(response_body, dict) else {}
                error_type = ""
                if isinstance(error_obj, dict):
                    error_type = str(error_obj.get("type") or "")
                    if not error_type:
                        root_cause = error_obj.get("root_cause")
                        if isinstance(root_cause, list) and root_cause:
                            first_cause = root_cause[0]
                            if isinstance(first_cause, dict):
                                error_type = str(first_cause.get("type") or "")
                if error_type == "index_not_found_exception":
                    logger.warning("Elasticsearch index not found for pattern '%s', return empty list", index_pattern)
                    return []
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            upstream_detail = _extract_http_error_detail(exc.response)
            raise RuntimeError(f"Elasticsearch 请求失败：{upstream_detail}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Elasticsearch 请求异常：{exc}") from exc

        hits = response.json().get("hits", {}).get("hits", [])

    results: List[UnifiedLogResponse] = []
    for hit in hits:
        source_doc = hit.get("_source", {})
        content = str(
            source_doc.get("message")
            or source_doc.get("content")
            or source_doc.get("log")
            or json.dumps(source_doc, ensure_ascii=False)
        )
        normalized_level = _normalize_level(content, source_doc.get("level"))
        anomaly, score = detector.detect(content)
        timestamp = _parse_datetime(str(source_doc.get("@timestamp") or source_doc.get("timestamp") or datetime.utcnow().isoformat()))
        if not timestamp:
            timestamp = datetime.utcnow()
        service_name = source_doc.get("service") or source_doc.get("service_name") or source_doc.get("kubernetes", {}).get("container_name")

        results.append(
            UnifiedLogResponse(
                id=str(hit.get("_id") or f"es-{len(results)}"),
                timestamp=timestamp,
                level=normalized_level,
                content=content[:4000],
                source=str(hit.get("_index") or "elasticsearch"),
                source_type="elasticsearch",
                service=str(service_name) if service_name else None,
                labels=None,
                is_anomaly=anomaly,
                anomaly_score=score,
                user_feedback=None,
                raw=source_doc,
            )
        )
    return results


async def _query_loki_logs(
    keyword: Optional[str],
    level: Optional[str],
    levels: Optional[List[str]],
    service: Optional[str],
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    limit: int,
    incident_only: bool,
) -> List[UnifiedLogResponse]:
    source_config = log_source_config_manager.get_effective_config()
    if not source_config["lokiEnabled"]:
        raise ValueError("Loki 日志源未启用")
    base_url = str(source_config.get("lokiUrl", "http://localhost:3100")).rstrip("/")

    selector_parts: List[str] = []
    if service:
        selector_parts.append(f'service="{service}"')
    stream_selector = "{" + ",".join(selector_parts) + "}" if selector_parts else "{job=~\".+\"}"

    pipeline_parts: List[str] = []
    if keyword:
        pipeline_parts.append(f'|= "{keyword}"')
    normalized_levels = [item for item in (levels or []) if item]
    if level and level not in normalized_levels:
        normalized_levels.append(level)
    if normalized_levels:
        level_pattern = "|".join(normalized_levels)
        pipeline_parts.append(f'|~ "(?i)({level_pattern})"')
    if incident_only:
        keyword_pattern = "|".join(INCIDENT_KEYWORDS)
        pipeline_parts.append(f'|~ "(?i)({keyword_pattern}|error|warn)"')
    query = f"{stream_selector} {' '.join(pipeline_parts)}".strip()

    params: Dict[str, Any] = {
        "query": query,
        "limit": limit,
        "direction": "BACKWARD",
    }
    if start_time:
        params["start"] = str(int(start_time.timestamp() * 1_000_000_000))
    if end_time:
        params["end"] = str(int(end_time.timestamp() * 1_000_000_000))

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{base_url}/loki/api/v1/query_range", params=params)
        response.raise_for_status()
        streams = response.json().get("data", {}).get("result", [])

    results: List[UnifiedLogResponse] = []
    for stream in streams:
        labels = {key: str(value) for key, value in stream.get("stream", {}).items()}
        for value in stream.get("values", []):
            if len(value) < 2:
                continue
            timestamp_ns, content = value[0], str(value[1])
            normalized_level = _normalize_level(content, labels.get("level"))
            anomaly, score = detector.detect(content)
            try:
                timestamp = datetime.fromtimestamp(int(timestamp_ns) / 1_000_000_000)
            except Exception:
                timestamp = datetime.utcnow()
            results.append(
                UnifiedLogResponse(
                    id=f"loki-{timestamp_ns}-{len(results)}",
                    timestamp=timestamp,
                    level=normalized_level,
                    content=content[:4000],
                    source=labels.get("job") or labels.get("app") or "loki",
                    source_type="loki",
                    service=labels.get("service") or labels.get("app"),
                    labels=labels,
                    is_anomaly=anomaly,
                    anomaly_score=score,
                    user_feedback=None,
                    raw={"stream": labels},
                )
            )

    results.sort(key=lambda item: item.timestamp, reverse=True)
    return results[:limit]

@router.post("/upload", response_model=UploadLogResponse)
async def upload_log_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(('.log', '.txt')):
        raise HTTPException(status_code=400, detail="只支持 .log 和 .txt 文件")
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")
    
    lines = content.decode('utf-8', errors='ignore').split('\n')
    logs_created = 0
    anomaly_count = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        level = "INFO"
        if "ERROR" in line or "error" in line:
            level = "ERROR"
        elif "WARN" in line or "warn" in line:
            level = "WARN"
        elif "DEBUG" in line:
            level = "DEBUG"
        
        is_anomaly, score = detector.detect(line)
        if is_anomaly:
            anomaly_count += 1
        
        log = Log(
            level=level,
            content=line[:1000],
            source="file",
            is_anomaly=is_anomaly,
            anomaly_score=score
        )
        db.add(log)
        logs_created += 1
    
    db.commit()
    
    return {
        "message": f"成功上传 {logs_created} 条日志",
        "filename": file.filename,
        "logs_created": logs_created,
        "anomaly_count": anomaly_count,
        "upload_time": datetime.utcnow(),
    }

@router.post("/ingest", response_model=LogResponse)
async def ingest_log(log_data: LogCreate, db: Session = Depends(get_db)):
    is_anomaly, score = detector.detect(log_data.content)
    
    log = Log(
        level=log_data.level,
        content=log_data.content,
        source=log_data.source,
        is_anomaly=is_anomaly,
        anomaly_score=score
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    
    return LogResponse(
        id=log.id,
        timestamp=log.timestamp,
        level=log.level,
        content=log.content,
        source=log.source,
        is_anomaly=log.is_anomaly,
        anomaly_score=log.anomaly_score,
        user_feedback=log.user_feedback
    )

@router.get("", response_model=List[LogResponse])
async def get_logs(
    level: Optional[str] = None,
    is_anomaly: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(Log)
    
    if level:
        query = query.filter(Log.level == level)
    if is_anomaly is not None:
        query = query.filter(Log.is_anomaly == is_anomaly)
    
    logs = query.order_by(Log.timestamp.desc()).offset(offset).limit(limit).all()
    
    return [
        LogResponse(
            id=log.id,
            timestamp=log.timestamp,
            level=log.level,
            content=log.content,
            source=log.source,
            is_anomaly=log.is_anomaly,
            anomaly_score=log.anomaly_score,
            user_feedback=log.user_feedback,
        )
        for log in logs
    ]


@router.get("/query", response_model=List[UnifiedLogResponse])
async def query_logs(
    source_type: str = "local",
    keyword: Optional[str] = None,
    level: Optional[str] = None,
    levels: Optional[str] = None,
    service: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    incident_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    normalized_source = (source_type or "local").strip().lower()
    safe_limit = min(max(limit, 1), 200)
    parsed_start = _parse_datetime(start_time)
    parsed_end = _parse_datetime(end_time)
    normalized_levels = [item.strip().upper() for item in (levels or "").split(",") if item.strip()]
    if incident_only and not normalized_levels:
        normalized_levels = ["ERROR", "WARN"]

    if normalized_source == "local":
        query = db.query(Log)
        if normalized_levels:
            query = query.filter(Log.level.in_(normalized_levels))
        elif level:
            query = query.filter(Log.level == level)
        if keyword:
            query = query.filter(Log.content.contains(keyword))
        if service:
            query = query.filter(Log.source.contains(service))
        if parsed_start:
            query = query.filter(Log.timestamp >= parsed_start)
        if parsed_end:
            query = query.filter(Log.timestamp <= parsed_end)
        if incident_only:
            incident_filters = [Log.level.in_(["ERROR", "WARN"])]
            for incident_keyword in INCIDENT_KEYWORDS:
                incident_filters.append(Log.content.ilike(f"%{incident_keyword}%"))
            from sqlalchemy import or_
            query = query.filter(or_(*incident_filters))

        logs = query.order_by(Log.timestamp.desc()).offset(offset).limit(safe_limit).all()
        return [_build_local_log_response(log) for log in logs]

    if normalized_source == "elasticsearch":
        try:
            return await _query_elasticsearch_logs(keyword, level, normalized_levels, service, parsed_start, parsed_end, safe_limit, incident_only)
        except Exception as exc:
            logger.exception("Elasticsearch query failed")
            raise HTTPException(status_code=502, detail=f"查询 Elasticsearch 日志失败: {exc}") from exc

    if normalized_source == "loki":
        try:
            return await _query_loki_logs(keyword, level, normalized_levels, service, parsed_start, parsed_end, safe_limit, incident_only)
        except Exception as exc:
            logger.exception("Loki query failed")
            raise HTTPException(status_code=502, detail=f"查询 Loki 日志失败: {exc}") from exc

    raise HTTPException(status_code=400, detail="不支持的日志来源")


@router.get("/config", response_model=dict)
def get_log_source_config(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "code": 200,
        "message": "success",
        "data": log_source_config_manager.get_config(db),
    }


@router.put("/config", response_model=dict)
def update_log_source_config(
    payload: LogSourceConfigPayload,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        result = log_source_config_manager.update_config(db, payload.model_dump(), current_user.username)
        return {"code": 200, "message": "更新成功", "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/config/test", response_model=LogSourceTestResponse)
async def test_elasticsearch_log_source_config(
    payload: LogSourceConfigPayload,
    current_user: User = Depends(require_admin),
):
    _ = current_user
    connection_config = _resolve_elasticsearch_connection_config(payload)
    headers: Dict[str, str] = {}
    auth = None

    if connection_config["auth_type"] == "basic":
        if not connection_config["username"] or not connection_config["password"]:
            raise HTTPException(status_code=400, detail="Basic Auth 缺少用户名或密码")
        auth = (connection_config["username"], connection_config["password"])
    elif connection_config["auth_type"] == "api_key":
        if not connection_config["api_key"]:
            raise HTTPException(status_code=400, detail="API Key 不能为空")
        headers["Authorization"] = f"ApiKey {connection_config['api_key']}"

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=connection_config["tls_verify"]) as client:
            response = await client.get(f"{connection_config['base_url']}/", headers=headers, auth=auth)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPStatusError as exc:
        detail = f"连接失败：HTTP {exc.response.status_code}"
        try:
            response_body = exc.response.json()
            if isinstance(response_body, dict) and response_body.get("error"):
                detail = f"{detail}，{response_body.get('error')}"
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"连接失败：{exc}") from exc

    version = body.get("version", {}) if isinstance(body, dict) else {}
    details = {
        "clusterName": body.get("cluster_name") if isinstance(body, dict) else None,
        "clusterUuid": body.get("cluster_uuid") if isinstance(body, dict) else None,
        "version": version.get("number") if isinstance(version, dict) else None,
        "tagline": body.get("tagline") if isinstance(body, dict) else None,
        "authenticatedAs": connection_config["username"] if connection_config["auth_type"] == "basic" else connection_config["auth_type"],
    }
    return LogSourceTestResponse(success=True, message="Elasticsearch 连接测试成功", details=details)


@router.post("/config/test-loki", response_model=LogSourceTestResponse)
async def test_loki_log_source_config(
    payload: LogSourceConfigPayload,
    current_user: User = Depends(require_admin),
):
    _ = current_user
    connection_config = _resolve_loki_connection_config(payload)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{connection_config['base_url']}/loki/api/v1/labels",
                params={"start": str(int((datetime.utcnow().timestamp() - 3600) * 1_000_000_000))},
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPStatusError as exc:
        detail = f"Loki 连接失败：HTTP {exc.response.status_code}"
        raise HTTPException(status_code=400, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"Loki 连接失败：{exc}") from exc

    labels = body.get("data", []) if isinstance(body, dict) else []
    details = {
        "endpoint": connection_config["base_url"],
        "labelsCount": len(labels) if isinstance(labels, list) else 0,
        "status": body.get("status") if isinstance(body, dict) else None,
        "sampleLabels": ", ".join(labels[:6]) if isinstance(labels, list) and labels else None,
    }
    return LogSourceTestResponse(success=True, message="Loki 连接测试成功", details=details)

@router.post("/{log_id}/feedback")
async def submit_feedback(log_id: int, feedback: FeedbackRequest, db: Session = Depends(get_db)):
    log = db.query(Log).filter(Log.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="日志不存在")
    
    log.user_feedback = feedback.feedback_type
    
    feedback_record = Feedback(
        log_id=log_id,
        feedback_type=feedback.feedback_type
    )
    db.add(feedback_record)
    db.commit()
    
    return {"message": "反馈已记录", "log_id": log_id}

@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    total = db.query(Log).count()
    anomaly_count = db.query(Log).filter(Log.is_anomaly == True).count()
    
    level_counts = {}
    for level in ["ERROR", "WARN", "INFO", "DEBUG"]:
        count = db.query(Log).filter(Log.level == level).count()
        level_counts[level] = count
    
    anomaly_logs = db.query(Log).filter(Log.is_anomaly == True).limit(5).all()
    top_patterns = [
        {"content": log.content[:50], "score": log.anomaly_score}
        for log in anomaly_logs
    ]
    
    return StatsResponse(
        total_logs=total,
        anomaly_count=anomaly_count,
        anomaly_rate=anomaly_count / total if total > 0 else 0,
        level_distribution=level_counts,
        top_patterns=top_patterns
    )
