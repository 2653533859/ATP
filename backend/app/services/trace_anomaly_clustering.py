"""Trace Anomaly Clustering and Root-Cause Attribution Service (T2.3).

Analyzes distributed trace spans to cluster anomalies into:
1. Downstream 5xx service failures
2. Slow database queries (slow SQL)
3. RPC / Network timeouts
4. Innermost root-cause span attribution and actionable fix suggestions
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SLOW_DB_THRESHOLD_MS = 100.0
DEFAULT_SLOW_SPAN_THRESHOLD_MS = 500.0


def classify_span(
    span: dict[str, Any],
    *,
    slow_db_threshold_ms: float = DEFAULT_SLOW_DB_THRESHOLD_MS,
    slow_span_threshold_ms: float = DEFAULT_SLOW_SPAN_THRESHOLD_MS,
) -> dict[str, Any] | None:
    """Classify a single span into an anomaly type if it exhibits errors or slowness."""
    tags = span.get("tags") or {}
    duration_ms = float(span.get("duration_ms", 0.0))
    has_error = bool(span.get("has_error", False))
    service_name = str(span.get("service_name") or "unknown-service")
    op_name = str(span.get("operation_name") or "operation")
    span_id = str(span.get("span_id") or "")

    # 1. Database Query (slow query or error)
    db_system = tags.get("db.system") or tags.get("db.type")
    db_statement = tags.get("db.statement") or tags.get("db.query")
    if db_system or db_statement:
        statement_str = str(db_statement or "").strip()[:500]
        if has_error:
            return {
                "span_id": span_id,
                "service_name": service_name,
                "operation_name": op_name,
                "category": "database_error",
                "severity": "critical",
                "duration_ms": duration_ms,
                "description": f"数据库操作异常 [{db_system or 'DB'}]: {statement_str or op_name}",
                "statement": statement_str,
            }
        if duration_ms >= slow_db_threshold_ms:
            return {
                "span_id": span_id,
                "service_name": service_name,
                "operation_name": op_name,
                "category": "slow_database_query",
                "severity": "warning" if duration_ms < 500 else "critical",
                "duration_ms": duration_ms,
                "description": f"慢数据库查询 ({duration_ms}ms >= {slow_db_threshold_ms}ms) [{db_system or 'DB'}]: {statement_str or op_name}",
                "statement": statement_str,
            }

    # 2. Timeout error
    error_msg = str(tags.get("error.message") or tags.get("exception.message") or "").lower()
    if any(k in error_msg for k in ("timeout", "timed out", "deadline exceeded")):
        return {
            "span_id": span_id,
            "service_name": service_name,
            "operation_name": op_name,
            "category": "rpc_timeout",
            "severity": "critical",
            "duration_ms": duration_ms,
            "description": f"RPC/微服务调用超时 [{service_name}]: {op_name} ({duration_ms}ms)",
        }

    # 3. Downstream HTTP / RPC Fault (5xx or explicit error)
    http_code = int(tags.get("http.status_code", 0)) if str(tags.get("http.status_code", "")).isdigit() else 0
    if has_error or http_code >= 500:
        return {
            "span_id": span_id,
            "service_name": service_name,
            "operation_name": op_name,
            "category": "downstream_service_fault",
            "severity": "critical",
            "duration_ms": duration_ms,
            "description": f"下游微服务调用失败 [{service_name}] HTTP {http_code or 'ERROR'}: {op_name}",
            "http_status": http_code or 500,
        }

    # 4. Slow service call
    if duration_ms >= slow_span_threshold_ms:
        return {
            "span_id": span_id,
            "service_name": service_name,
            "operation_name": op_name,
            "category": "slow_service_call",
            "severity": "warning",
            "duration_ms": duration_ms,
            "description": f"微服务调用延迟较高 [{service_name}]: {op_name} 耗时 {duration_ms}ms",
        }

    return None


def _flatten_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recursively flatten a tree of spans into a single list."""
    flattened: list[dict[str, Any]] = []
    for s in spans:
        flattened.append(s)
        children = s.get("children") or []
        if children:
            flattened.extend(_flatten_spans(children))
    return flattened


def cluster_trace_anomalies(
    waterfall_data: dict[str, Any],
    *,
    slow_db_threshold_ms: float = DEFAULT_SLOW_DB_THRESHOLD_MS,
    slow_span_threshold_ms: float = DEFAULT_SLOW_SPAN_THRESHOLD_MS,
) -> dict[str, Any]:
    """Analyze waterfall data and cluster all anomalous spans into root cause attribution."""
    trace_id = str(waterfall_data.get("trace_id") or "")
    raw_spans = waterfall_data.get("spans") or []
    flat_spans = _flatten_spans(raw_spans)

    anomalies: list[dict[str, Any]] = []
    for span in flat_spans:
        anomaly = classify_span(
            span,
            slow_db_threshold_ms=slow_db_threshold_ms,
            slow_span_threshold_ms=slow_span_threshold_ms,
        )
        if anomaly:
            anomalies.append(anomaly)

    # Sort anomalies by severity (critical first) and then by duration (descending)
    anomalies.sort(key=lambda x: (0 if x["severity"] == "critical" else 1, -x["duration_ms"]))

    error_spans = [
        a for a in anomalies if a["category"] in ("downstream_service_fault", "database_error", "rpc_timeout")
    ]
    slow_spans = [a for a in anomalies if a["category"] in ("slow_database_query", "slow_service_call")]

    # Root cause attribution: innermost or highest-severity anomaly
    root_cause_service = "none"
    root_cause_span = None
    root_cause_category = "none"
    root_cause_summary = "调用链未发现显著异常或慢调用"

    if anomalies:
        primary = anomalies[0]
        root_cause_service = primary["service_name"]
        root_cause_span = primary["span_id"]
        root_cause_category = primary["category"]
        root_cause_summary = primary["description"]

    return {
        "trace_id": trace_id,
        "root_cause_service": root_cause_service,
        "root_cause_span": root_cause_span,
        "root_cause_category": root_cause_category,
        "root_cause_summary": root_cause_summary,
        "error_span_count": len(error_spans),
        "slow_span_count": len(slow_spans),
        "total_anomalies": len(anomalies),
        "anomalies": anomalies,
    }
