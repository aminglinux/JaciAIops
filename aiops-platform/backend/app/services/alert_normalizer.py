from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AlertAnalyzeRequest(BaseModel):
    alert_name: str
    severity: str = "warning"
    service: Optional[str] = None
    instance: Optional[str] = None
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    description: Optional[str] = None
    labels: Dict[str, Any] = Field(default_factory=dict)
    annotations: Dict[str, Any] = Field(default_factory=dict)
    source: str = "custom"
    lookback_minutes: int = 15


class NormalizedAlert(BaseModel):
    alert_name: str
    severity: str
    service: Optional[str] = None
    instance: Optional[str] = None
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    description: str = ""
    labels: Dict[str, Any] = Field(default_factory=dict)
    annotations: Dict[str, Any] = Field(default_factory=dict)
    source: str = "custom"
    lookback_minutes: int = 15


class AlertNormalizer:
    SERVICE_LABEL_KEYS = [
        "service",
        "service_name",
        "app",
        "application",
        "job",
        "deployment",
        "container",
        "pod",
    ]
    INSTANCE_LABEL_KEYS = ["instance", "host", "hostname", "node", "pod", "ip"]
    SEVERITY_LABEL_KEYS = ["severity", "level", "priority"]
    METRIC_LABEL_KEYS = ["metric", "metric_name", "__name__"]

    def normalize_custom(self, payload: AlertAnalyzeRequest) -> NormalizedAlert:
        labels = {key: value for key, value in (payload.labels or {}).items() if value is not None}
        annotations = {key: value for key, value in (payload.annotations or {}).items() if value is not None}
        service = payload.service or self._first_value(labels, self.SERVICE_LABEL_KEYS)
        instance = payload.instance or self._first_value(labels, self.INSTANCE_LABEL_KEYS)
        severity = payload.severity or self._first_value(labels, self.SEVERITY_LABEL_KEYS) or "warning"
        metric_name = payload.metric_name or self._first_value(labels, self.METRIC_LABEL_KEYS)
        description = payload.description or self._first_value(annotations, ["description", "summary", "message"]) or ""

        return NormalizedAlert(
            alert_name=payload.alert_name,
            severity=str(severity),
            service=str(service) if service else None,
            instance=str(instance) if instance else None,
            metric_name=str(metric_name) if metric_name else None,
            metric_value=payload.metric_value,
            threshold=payload.threshold,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            description=str(description),
            labels=labels,
            annotations=annotations,
            source=payload.source or "custom",
            lookback_minutes=max(1, int(payload.lookback_minutes or 15)),
        )

    def normalize_alertmanager(self, payload: Dict[str, Any]) -> List[NormalizedAlert]:
        alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else [payload]
        normalized_alerts: List[NormalizedAlert] = []
        for alert in alerts:
            labels = alert.get("labels", {}) or {}
            annotations = alert.get("annotations", {}) or {}
            alert_name = labels.get("alertname") or labels.get("alert_name") or payload.get("groupKey") or "unknown_alert"
            starts_at = alert.get("startsAt") or alert.get("starts_at")
            ends_at = alert.get("endsAt") or alert.get("ends_at")
            normalized_alerts.append(
                self.normalize_custom(
                    AlertAnalyzeRequest(
                        alert_name=str(alert_name),
                        severity=str(self._first_value(labels, self.SEVERITY_LABEL_KEYS) or "warning"),
                        service=self._first_value(labels, self.SERVICE_LABEL_KEYS),
                        instance=self._first_value(labels, self.INSTANCE_LABEL_KEYS),
                        metric_name=self._first_value(labels, self.METRIC_LABEL_KEYS),
                        starts_at=starts_at,
                        ends_at=ends_at,
                        description=str(self._first_value(annotations, ["description", "summary", "message"]) or ""),
                        labels=labels,
                        annotations=annotations,
                        source="alertmanager",
                    )
                )
            )
        return normalized_alerts

    def build_rca_query(self, alert: NormalizedAlert) -> str:
        time_context = alert.starts_at or datetime.utcnow().isoformat()
        service_context = alert.service or "未知服务"
        instance_context = alert.instance or "未知实例"
        metric_context = alert.metric_name or alert.alert_name
        value_context = "未知"
        if alert.metric_value is not None:
            value_context = str(alert.metric_value)
        threshold_context = "未知"
        if alert.threshold is not None:
            threshold_context = str(alert.threshold)

        return (
            "[ALERT_RCA] 监控告警触发根因分析。\n"
            f"告警名称: {alert.alert_name}\n"
            f"告警级别: {alert.severity}\n"
            f"服务: {service_context}\n"
            f"实例/IP/Pod: {instance_context}\n"
            f"指标: {metric_context}\n"
            f"当前值: {value_context}\n"
            f"阈值: {threshold_context}\n"
            f"发生时间: {time_context}\n"
            f"回看窗口: 告警时间前后 {alert.lookback_minutes} 分钟\n"
            f"告警描述: {alert.description or '无'}\n"
            "请结合知识图谱中的服务拓扑和依赖关系，优先定位直接根因、影响范围、证据链和下一步排查建议。\n"
            "日志检索是标准环节之一：必须尝试检索相关日志；若命中关键错误日志，请将其作为重要依据；若未命中，请明确说明日志证据不足但继续完成 RCA。"
        )

    def _first_value(self, mapping: Dict[str, Any], keys: List[str]) -> Optional[Any]:
        for key in keys:
            value = mapping.get(key)
            if value not in (None, ""):
                return value
        return None


alert_normalizer = AlertNormalizer()
