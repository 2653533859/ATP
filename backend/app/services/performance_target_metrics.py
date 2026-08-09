"""Bounded Prometheus target-service metric sampling for performance runs."""

from __future__ import annotations

import json
import os
from collections.abc import Collection
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class TargetMetricError(ValueError):
    """Raised when target metric configuration is invalid."""


MAX_QUERIES = 8
MAX_RESPONSE_BYTES = 1_000_000


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise TargetMetricError("Prometheus target must not redirect to another host")


_TARGET_METRIC_OPENER = build_opener(_NoRedirectHandler)


def build_target_metric_sampler(options: dict[str, Any], *, allowed_hosts: Collection[str] | None = None):
    """Return a best-effort sampler or ``None`` when target metrics are not configured."""
    config = options.get("target_metrics")
    if not config:
        return None
    if not isinstance(config, dict):
        raise TargetMetricError("target_metrics 必须是 JSON 对象")
    base_url = str(config.get("prometheus_url") or config.get("url") or "").strip()
    if not base_url:
        env_key = str(config.get("url_env") or "").strip()
        raw_env_values = options.get("env")
        env_values: dict[str, Any] = raw_env_values if isinstance(raw_env_values, dict) else {}
        base_url = str(env_values.get(env_key) or os.getenv(env_key, "")).strip() if env_key else ""
    parsed_base_url = urlparse(base_url)
    if parsed_base_url.scheme not in {"http", "https"} or not parsed_base_url.netloc:
        raise TargetMetricError("target_metrics URL 必须是 HTTP 或 HTTPS 地址")
    host = (parsed_base_url.hostname or "").lower()
    normalized_allowed_hosts = {str(item).strip().lower() for item in (allowed_hosts or []) if str(item).strip()}
    if normalized_allowed_hosts and not (
        host in normalized_allowed_hosts or any(host.endswith(f".{item}") for item in normalized_allowed_hosts)
    ):
        raise TargetMetricError(f"Prometheus target host is not in the node allowlist: {host}")
    raw_queries = config.get("queries") or {}
    if not isinstance(raw_queries, dict) or not raw_queries:
        return None
    queries = [
        (str(name).strip(), str(query).strip())
        for name, query in raw_queries.items()
        if str(name).strip() and str(query).strip()
    ]
    if not queries:
        return None
    if len(queries) > MAX_QUERIES:
        raise TargetMetricError(f"target_metrics 查询数量不能超过 {MAX_QUERIES}")
    try:
        timeout = max(0.2, min(float(config.get("timeout_seconds", 2)), 10.0))
    except (TypeError, ValueError) as exc:
        raise TargetMetricError("target_metrics timeout_seconds 必须是数字") from exc

    def collect() -> dict[str, Any]:
        metrics: dict[str, float] = {}
        errors: list[str] = []
        for name, query in queries:
            try:
                payload = _query_prometheus(base_url, query, timeout)
                value = _extract_scalar(payload)
                if value is None:
                    errors.append(f"{name}: no scalar result")
                else:
                    metrics[name] = value
            except Exception as exc:
                errors.append(f"{name}: {str(exc)[:200]}")
        return {"source": "target-service-prometheus", "metrics": metrics, "errors": errors}

    return collect


def _query_prometheus(base_url: str, query: str, timeout: float) -> dict[str, Any]:
    endpoint = urljoin(base_url.rstrip("/") + "/", "api/v1/query")
    parsed_endpoint = urlparse(endpoint)
    if parsed_endpoint.scheme not in {"http", "https"} or not parsed_endpoint.netloc:
        raise TargetMetricError("Prometheus endpoint must use an explicit http or https URL")
    request = Request(f"{endpoint}?{urlencode({'query': query})}", headers={"Accept": "application/json"})
    with _TARGET_METRIC_OPENER.open(request, timeout=timeout) as response:  # nosec B310 - endpoint scheme is validated above
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise TargetMetricError("Prometheus 响应超过大小限制")
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("status") != "success":
        raise TargetMetricError(str(payload.get("error") or "Prometheus query failed"))
    return payload


def _extract_scalar(payload: dict[str, Any]) -> float | None:
    data = payload.get("data") or {}
    results = data.get("result") or []
    if not results:
        return None
    value = results[0].get("value") if isinstance(results[0], dict) else None
    if not isinstance(value, list) or len(value) < 2:
        return None
    try:
        return float(value[1])
    except (TypeError, ValueError):
        return None
