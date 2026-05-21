"""Prometheus metrics 封装。

设计目标：本地缺少 `prometheus_client` 或 `prometheus_fastapi_instrumentator`
依赖时所有 metric 调用变 no-op，不破坏既有测试与运行路径。
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    Counter = None  # type: ignore[assignment]
    _PROMETHEUS_AVAILABLE = False


class _NoopMetric:
    def labels(self, **_kwargs: Any) -> "_NoopMetric":
        return self

    def inc(self, _amount: float = 1) -> None:
        pass

    def observe(self, _amount: float) -> None:
        pass

    def set(self, _value: float) -> None:
        pass


_NOOP = _NoopMetric()


def _counter(name: str, doc: str, labelnames: tuple[str, ...] = ()) -> Any:
    if _PROMETHEUS_AVAILABLE and Counter is not None:
        return Counter(name, doc, labelnames=labelnames)
    return _NOOP


# 业务指标 — 与 A.3/A.4/A.5 已有 logger.debug/warning 信号保持同源
STATS_CACHE = _counter("atp_stats_cache_total", "Statistics cache outcomes", ("result",))
SLOW_QUERY = _counter("atp_slow_queries_total", "SQL queries exceeding the slow threshold")
CELERY_TIMEOUT = _counter("atp_celery_timeouts_total", "Celery task timeouts by kind", ("kind",))
RUN_RETENTION_DELETED = _counter(
    "atp_run_retention_deleted_total", "Old runs deleted by retention task", ("model",)
)


def enable_metrics_for(app: Any) -> None:
    """注册 FastAPI 请求 instrumentator + /metrics 端点；缺依赖时 no-op。

    必须在 ``app.include_router(...)`` 之前调用，instrumentator 才能覆盖所有路由。
    """
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
    except ImportError:
        logger.info("prometheus-fastapi-instrumentator not installed; /metrics endpoint disabled")
        return

    try:
        Instrumentator(
            excluded_handlers=["/metrics", "/health"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
        logger.info("Prometheus metrics enabled at /metrics")
    except Exception as exc:
        logger.warning("Failed to enable Prometheus instrumentator: %s", exc)
