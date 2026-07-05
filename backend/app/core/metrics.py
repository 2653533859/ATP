"""Prometheus metrics 封装。

设计目标：本地缺少 `prometheus_client` 或 `prometheus_fastapi_instrumentator`
依赖时所有 metric 调用变 no-op，不破坏既有测试与运行路径。
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    Counter = None  # type: ignore[assignment]
    Gauge = None  # type: ignore[assignment]
    Histogram = None  # type: ignore[assignment]
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


def _histogram(name: str, doc: str, buckets: tuple[float, ...] | None = None) -> Any:
    if _PROMETHEUS_AVAILABLE and Histogram is not None:
        kwargs: dict[str, Any] = {}
        if buckets is not None:
            kwargs["buckets"] = buckets
        return Histogram(name, doc, **kwargs)
    return _NOOP


def _gauge(name: str, doc: str, labelnames: tuple[str, ...] = ()) -> Any:
    if _PROMETHEUS_AVAILABLE and Gauge is not None:
        return Gauge(name, doc, labelnames=labelnames)
    return _NOOP


# 业务指标 — 与 A.3/A.4/A.5 已有 logger.debug/warning 信号保持同源
STATS_CACHE = _counter("atp_stats_cache_total", "Statistics cache outcomes", ("result",))
SLOW_QUERY = _counter("atp_slow_queries_total", "SQL queries exceeding the slow threshold")
CELERY_TIMEOUT = _counter("atp_celery_timeouts_total", "Celery task timeouts by kind", ("kind",))
RUN_RETENTION_DELETED = _counter(
    "atp_run_retention_deleted_total", "Old runs deleted by retention task", ("model",)
)
STORAGE_TOTAL_BYTES = _gauge("atp_storage_total_bytes", "MinIO bucket total bytes", ("bucket",))
STORAGE_TOTAL_OBJECTS = _gauge("atp_storage_total_objects", "MinIO bucket total object count", ("bucket",))

# Q7 A.3.2 — ADB 自愈可观测性
# result: success | failure | not_tcp_serial | adb_not_found
ADB_RECONNECT_TOTAL = _counter(
    "atp_adb_reconnect_total",
    "ADB ensure_reachable outcomes by result label",
    ("result",),
)
# executor: android | perf | stability | fluency
ADB_HEARTBEAT_LOST_TOTAL = _counter(
    "atp_adb_heartbeat_lost_total",
    "ADB heartbeat lost events by executor",
    ("executor",),
)
# 探测延迟分布（含可能的 reconnect 时间），单位秒
ADB_ENSURE_REACHABLE_DURATION = _histogram(
    "atp_adb_ensure_reachable_duration_seconds",
    "ADB ensure_reachable execution duration in seconds",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
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


def start_worker_metrics_server(port: int) -> bool:
    """为 Celery worker 子进程启动 Prometheus HTTP server。

    返回 True 表示已成功监听；False 表示被跳过（port=0 / 缺依赖 / 绑定失败）。
    与 enable_metrics_for 类似的兜底语义：任何异常都不应阻断 worker 启动。
    """
    if port <= 0:
        logger.info("WORKER_METRICS_PORT=%d, worker metrics endpoint disabled", port)
        return False
    if not _PROMETHEUS_AVAILABLE:
        logger.info("prometheus_client not installed; worker /metrics disabled")
        return False
    try:
        from prometheus_client import start_http_server

        start_http_server(port)
        logger.info("Worker Prometheus /metrics enabled at :%d", port)
        return True
    except OSError as exc:
        # 端口被占（多 worker 进程共享同一物理端口时）— 仅第一个子进程能成功，其余 OSError 不致命
        logger.info("Worker metrics port :%d already bound: %s", port, exc)
        return False
    except Exception as exc:
        logger.warning("Failed to start worker metrics server on :%d: %s", port, exc)
        return False
