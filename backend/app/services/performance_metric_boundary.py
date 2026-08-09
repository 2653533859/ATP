"""Declare the ownership and collection boundary for performance metrics."""

from __future__ import annotations

from typing import Any


class PerformanceMetricBoundaryError(ValueError):
    """Raised when target-service metric configuration is ambiguous."""


def build_metric_boundary(options: dict[str, Any]) -> dict[str, Any]:
    target = options.get("target_metrics")
    target_enabled = bool(target)
    target_configured = False
    if target_enabled:
        if not isinstance(target, dict):
            raise PerformanceMetricBoundaryError("target_metrics 必须是 JSON 对象")
        target_url = target.get("prometheus_url") or target.get("url")
        target_env_key = target.get("url_env")
        if not target_url and not target_env_key:
            raise PerformanceMetricBoundaryError("目标服务指标必须配置 prometheus_url 或 url_env")
        if target_url and not isinstance(target_url, str):
            raise PerformanceMetricBoundaryError("目标服务指标 URL 必须是字符串")
        if target_env_key and not isinstance(target_env_key, str):
            raise PerformanceMetricBoundaryError("目标服务指标 url_env 必须是字符串")
        target_configured = True
    return {
        "worker": {"enabled": True, "source": "performance-worker"},
        "platform": {"enabled": False, "source": "atp-platform", "note": "待接入平台依赖指标"},
        "target_service": {
            "enabled": target_enabled,
            "configured": target_configured,
            "source": "target-service-prometheus",
            "collection": "boundary-only" if target_enabled else "disabled",
        },
    }
