from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.services import runtime_graph_config_manager

from .base import TraceProvider
from .schemas import RuntimeTopologySnapshot, ServiceDependency, TraceAnomaly


class JaegerTraceProvider(TraceProvider):
    async def _fetch_traces(self, service: str, minutes: int) -> List[Dict[str, Any]]:
        lookback = max(1, minutes)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=lookback)
        params = {
            "service": service,
            "lookback": f"{lookback}m",
            "start": int(start_time.timestamp() * 1_000_000),
            "end": int(end_time.timestamp() * 1_000_000),
            "limit": 20,
        }
        runtime_config = runtime_graph_config_manager.get_effective_config()
        jaeger_query_url = runtime_config["jaegerQueryUrl"].rstrip("/")
        timeout = runtime_config["traceQueryTimeout"]

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{jaeger_query_url}/api/traces", params=params)
            response.raise_for_status()
            payload = response.json()
            return payload.get("data", [])

    def _get_process_service(self, trace: Dict[str, Any], process_id: Optional[str]) -> str:
        if not process_id:
            return ""
        process = trace.get("processes", {}).get(process_id, {})
        service_name = process.get("serviceName", "")
        if service_name:
            return service_name
        tags = process.get("tags", [])
        for tag in tags:
            if tag.get("key") == "service.name":
                return str(tag.get("value", ""))
        return ""

    def _find_child_service(self, trace: Dict[str, Any], span_id: str) -> Optional[str]:
        for span in trace.get("spans", []):
            references = span.get("references", [])
            for reference in references:
                if reference.get("spanID") == span_id and reference.get("refType") == "CHILD_OF":
                    child_service = self._get_process_service(trace, span.get("processID"))
                    if child_service:
                        return child_service
        return None

    def _extract_peer_dependency(self, span: Dict[str, Any]) -> Optional[str]:
        candidate_keys = [
            "peer.service",
            "db.name",
            "db.system",
            "messaging.destination",
            "rpc.service",
            "http.host",
            "net.peer.name",
        ]
        for tag in span.get("tags", []):
            if tag.get("key") in candidate_keys and tag.get("value"):
                return str(tag.get("value"))
        return None

    def _is_error_span(self, span: Dict[str, Any]) -> bool:
        for tag in span.get("tags", []):
            if tag.get("key") == "error" and str(tag.get("value")).lower() == "true":
                return True
            if tag.get("key") == "otel.status_code" and str(tag.get("value")).upper() == "ERROR":
                return True
        return False

    def _build_dependencies(self, service: str, traces: List[Dict[str, Any]]) -> List[ServiceDependency]:
        dependency_stats: Dict[tuple[str, str, str], Dict[str, Any]] = defaultdict(
            lambda: {"latencies": [], "errors": 0, "count": 0, "last_seen": None, "details": {}}
        )

        for trace in traces:
            for span in trace.get("spans", []):
                source_service = self._get_process_service(trace, span.get("processID"))
                if source_service != service:
                    continue

                target_service = self._find_child_service(trace, span.get("spanID")) or self._extract_peer_dependency(span)
                if not target_service or target_service == service:
                    continue

                dependency_type = "CALLS"
                peer_system = self._extract_peer_dependency(span)
                if peer_system:
                    lower_peer = peer_system.lower()
                    if any(token in lower_peer for token in ["mysql", "postgres", "redis", "mongo", "db"]):
                        dependency_type = "USES_DB"
                    elif any(token in lower_peer for token in ["kafka", "rabbitmq", "mq", "topic"]):
                        dependency_type = "USES_MQ"
                    elif any(token in lower_peer for token in ["cache", "memcached"]):
                        dependency_type = "USES_CACHE"

                key = (service, target_service, dependency_type)
                stats = dependency_stats[key]
                duration_ms = max(0.0, float(span.get("duration", 0)) / 1000.0)
                stats["latencies"].append(duration_ms)
                stats["count"] += 1
                if self._is_error_span(span):
                    stats["errors"] += 1
                stats["last_seen"] = datetime.now(timezone.utc)
                stats["details"] = {
                    "operation": span.get("operationName", ""),
                }

        dependencies = []
        for (source_service, target_service, dependency_type), stats in dependency_stats.items():
            if not stats["count"]:
                continue
            dependencies.append(
                ServiceDependency(
                    source_service=source_service,
                    target_service=target_service,
                    dependency_type=dependency_type,
                    avg_latency_ms=sum(stats["latencies"]) / len(stats["latencies"]),
                    error_rate=stats["errors"] / stats["count"] if stats["count"] else 0.0,
                    call_count=stats["count"],
                    last_seen=stats["last_seen"],
                    source="jaeger",
                    details=stats["details"],
                )
            )
        return sorted(dependencies, key=lambda item: (-item.call_count, -item.avg_latency_ms))

    def _build_anomalies(self, service: str, traces: List[Dict[str, Any]]) -> List[TraceAnomaly]:
        anomalies: List[TraceAnomaly] = []
        for trace in traces:
            trace_id = trace.get("traceID", "")
            for span in trace.get("spans", []):
                source_service = self._get_process_service(trace, span.get("processID"))
                if source_service != service:
                    continue

                duration_ms = max(0.0, float(span.get("duration", 0)) / 1000.0)
                is_error = self._is_error_span(span)
                if duration_ms < 1000 and not is_error:
                    continue

                anomalies.append(
                    TraceAnomaly(
                        service=service,
                        trace_id=trace_id,
                        span_name=span.get("operationName", "unknown"),
                        duration_ms=duration_ms,
                        suspected_dependency=self._find_child_service(trace, span.get("spanID")) or self._extract_peer_dependency(span),
                        anomaly_type="error_span" if is_error else "slow_span",
                        details={"spanID": span.get("spanID", "")},
                    )
                )
        return sorted(anomalies, key=lambda item: (-item.duration_ms, item.anomaly_type))

    async def get_service_dependencies(self, service: str, minutes: int = 15) -> List[ServiceDependency]:
        traces = await self._fetch_traces(service, minutes)
        return self._build_dependencies(service, traces)

    async def get_recent_trace_anomalies(self, service: str, minutes: int = 15) -> List[TraceAnomaly]:
        traces = await self._fetch_traces(service, minutes)
        return self._build_anomalies(service, traces)

    async def get_runtime_topology(self, service: str, minutes: int = 15) -> RuntimeTopologySnapshot:
        traces = await self._fetch_traces(service, minutes)
        downstream = self._build_dependencies(service, traces)
        anomalies = self._build_anomalies(service, traces)
        upstream: List[ServiceDependency] = []

        for trace in traces:
            for span in trace.get("spans", []):
                target_service = self._get_process_service(trace, span.get("processID"))
                if target_service != service:
                    continue
                references = span.get("references", [])
                for reference in references:
                    if reference.get("refType") != "CHILD_OF":
                        continue
                    parent_id = reference.get("spanID")
                    parent_span = next((item for item in trace.get("spans", []) if item.get("spanID") == parent_id), None)
                    if not parent_span:
                        continue
                    source_service = self._get_process_service(trace, parent_span.get("processID"))
                    if not source_service or source_service == service:
                        continue
                    upstream.append(
                        ServiceDependency(
                            source_service=source_service,
                            target_service=service,
                            dependency_type="CALLS",
                            avg_latency_ms=max(0.0, float(span.get("duration", 0)) / 1000.0),
                            error_rate=1.0 if self._is_error_span(span) else 0.0,
                            call_count=1,
                            last_seen=datetime.now(timezone.utc),
                            source="jaeger",
                            details={"traceID": trace.get("traceID", "")},
                        )
                    )

        aggregated_upstream: Dict[tuple[str, str], Dict[str, Any]] = defaultdict(
            lambda: {"latencies": [], "errors": 0, "count": 0, "last_seen": None}
        )
        for item in upstream:
            key = (item.source_service, item.target_service)
            stats = aggregated_upstream[key]
            stats["latencies"].append(item.avg_latency_ms)
            stats["errors"] += 1 if item.error_rate > 0 else 0
            stats["count"] += 1
            stats["last_seen"] = item.last_seen

        upstream_result = [
            ServiceDependency(
                source_service=source,
                target_service=target,
                dependency_type="CALLS",
                avg_latency_ms=sum(stats["latencies"]) / len(stats["latencies"]),
                error_rate=stats["errors"] / stats["count"] if stats["count"] else 0.0,
                call_count=stats["count"],
                last_seen=stats["last_seen"],
                source="jaeger",
            )
            for (source, target), stats in aggregated_upstream.items()
        ]

        return RuntimeTopologySnapshot(
            service=service,
            window_minutes=minutes,
            upstream=sorted(upstream_result, key=lambda item: (-item.call_count, -item.avg_latency_ms)),
            downstream=downstream,
            anomalies=anomalies[:10],
            source="jaeger",
        )
