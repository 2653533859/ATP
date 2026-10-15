"""OpenTelemetry / Jaeger Distributed Trace Retrieval Service (T2.2).

Fetches, parses, and converts Jaeger/OTel distributed traces into
hierarchical waterfall graphs with service topology and duration metrics.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.services.trace_anomaly_clustering import cluster_trace_anomalies

logger = logging.getLogger(__name__)


def parse_span_tags(raw_tags: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert Jaeger tag objects into a standard key-value map."""
    tags: dict[str, Any] = {}
    for item in raw_tags:
        if isinstance(item, dict) and "key" in item:
            tags[item["key"]] = item.get("value")
    return tags


def parse_jaeger_trace_data(raw_trace_item: dict[str, Any]) -> dict[str, Any]:
    """Parse a single trace object from Jaeger JSON API into structured waterfall."""
    spans_raw = raw_trace_item.get("spans") or []
    processes = raw_trace_item.get("processes") or {}
    trace_id = str(raw_trace_item.get("traceID") or "")

    if not spans_raw:
        fallback = {
            "trace_id": trace_id,
            "root_service": "unknown",
            "total_duration_ms": 0.0,
            "span_count": 0,
            "service_count": 0,
            "services": [],
            "has_errors": False,
            "spans": [],
        }
        fallback["anomaly_cluster"] = cluster_trace_anomalies(fallback)
        return fallback

    # Find trace baseline start time in microseconds
    min_start_us = min(int(s.get("startTime", 0)) for s in spans_raw)
    max_end_us = max(int(s.get("startTime", 0)) + int(s.get("duration", 0)) for s in spans_raw)
    total_duration_ms = round((max_end_us - min_start_us) / 1000.0, 2)

    unique_services: set[str] = set()
    has_any_error = False

    flat_spans: list[dict[str, Any]] = []
    for s in spans_raw:
        sid = str(s.get("spanID") or "")
        pid = str(s.get("processID") or "")
        proc = processes.get(pid, {}) if isinstance(processes.get(pid), dict) else {}
        service_name = str(proc.get("serviceName") or "unknown-service")
        unique_services.add(service_name)

        op_name = str(s.get("operationName") or "operation")
        start_us = int(s.get("startTime", 0))
        duration_us = int(s.get("duration", 0))
        duration_ms = round(duration_us / 1000.0, 2)
        offset_ms = round((start_us - min_start_us) / 1000.0, 2)

        tags = parse_span_tags(s.get("tags") or [])
        http_code = int(tags.get("http.status_code", 0)) if str(tags.get("http.status_code", "")).isdigit() else 0
        has_error = bool(
            tags.get("error") is True or http_code >= 400 or str(tags.get("otel.status_code", "")).upper() == "ERROR"
        )
        if has_error:
            has_any_error = True

        # Extract parent span ID from references
        parent_id = None
        for ref in s.get("references") or []:
            if isinstance(ref, dict) and ref.get("refType") == "CHILD_OF":
                parent_id = str(ref.get("spanID") or "")
                break

        flat_spans.append(
            {
                "span_id": sid,
                "parent_span_id": parent_id,
                "service_name": service_name,
                "operation_name": op_name,
                "duration_ms": duration_ms,
                "start_time_offset_ms": offset_ms,
                "has_error": has_error,
                "tags": tags,
                "children": [],
            }
        )

    # Sort flat spans chronologically
    flat_spans.sort(key=lambda x: (x["start_time_offset_ms"], -x["duration_ms"]))

    # Build hierarchical tree
    span_map = {s["span_id"]: s for s in flat_spans}
    root_spans: list[dict[str, Any]] = []

    for s in flat_spans:
        parent_id = s.get("parent_span_id")
        if parent_id and parent_id in span_map:
            span_map[parent_id]["children"].append(s)
        else:
            root_spans.append(s)

    root_service = root_spans[0]["service_name"] if root_spans else "unknown"

    waterfall = {
        "trace_id": trace_id,
        "root_service": root_service,
        "total_duration_ms": total_duration_ms,
        "span_count": len(flat_spans),
        "service_count": len(unique_services),
        "services": sorted(unique_services),
        "has_errors": has_any_error,
        "spans": root_spans,
    }
    waterfall["anomaly_cluster"] = cluster_trace_anomalies(waterfall)
    return waterfall


async def fetch_external_distributed_trace(
    trace_id: str,
    *,
    base_url: str | None = None,
    timeout_seconds: float = 3.0,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Fetch trace from Jaeger HTTP API and parse into waterfall graph."""
    query_url = (base_url or settings.JAEGER_QUERY_URL or settings.JAEGER_UI_URL or "").rstrip("/")
    if not query_url:
        return None

    cleaned_tid = trace_id.replace("-", "").strip().lower()
    endpoint = f"{query_url}/api/traces/{cleaned_tid}"

    client = http_client or httpx.AsyncClient(timeout=timeout_seconds)
    owns_client = http_client is None

    try:
        resp = await client.get(endpoint)
        if resp.status_code == 200:
            payload = resp.json()
            data_list = payload.get("data") or []
            if data_list and isinstance(data_list[0], dict):
                return parse_jaeger_trace_data(data_list[0])
        elif resp.status_code != 404:
            logger.warning("Jaeger trace query returned HTTP %s for trace %s", resp.status_code, cleaned_tid)
        return None
    except Exception as exc:
        logger.debug("Failed to query Jaeger APM trace %s: %s", cleaned_tid, exc)
        return None
    finally:
        if owns_client:
            await client.aclose()
