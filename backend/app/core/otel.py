"""OpenTelemetry 初始化与全局 tracer 提供者。

设计原则：
- `OTEL_EXPORTER_OTLP_ENDPOINT` 留空时整个模块降级为 no-op，业务调用方无需写任何
  if 判断，所有 `with tracer.start_as_current_span(...)` 都会拿到一个空操作的
  tracer，零运行时副作用。
- backend 进程在 FastAPI lifespan 中初始化；worker 进程在 `worker_process_init`
  信号处理器里初始化（Celery 跨进程模型决定）。
"""
from __future__ import annotations

import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import (
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

_initialized = False


def _build_sampler() -> Sampler:
    name = (settings.OTEL_TRACES_SAMPLER or "").lower()
    ratio = max(0.0, min(float(settings.OTEL_TRACES_SAMPLER_ARG or 0.0), 1.0))
    if name == "traceidratio":
        return TraceIdRatioBased(ratio)
    # 默认与 OTEL 规范一致：parentbased_traceidratio
    return ParentBased(root=TraceIdRatioBased(ratio))


def init_tracer(service_name: Optional[str] = None) -> None:
    """初始化全局 TracerProvider，绑定 OTLP gRPC exporter。

    重复调用安全：第二次起为 no-op。当 endpoint 未配置时同样为 no-op。
    """
    global _initialized
    if _initialized:
        return
    endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    if not endpoint:
        logger.info("OTEL endpoint not configured; tracing disabled")
        return

    resource = Resource.create({"service.name": service_name or settings.OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource, sampler=_build_sampler())
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _initialized = True
    logger.info("OTEL tracer initialized: service=%s endpoint=%s", service_name, endpoint)


def shutdown_tracer() -> None:
    """flush 并关闭 TracerProvider；进程退出时调用。"""
    global _initialized
    if not _initialized:
        return
    provider = trace.get_tracer_provider()
    shutdown = getattr(provider, "shutdown", None)
    if callable(shutdown):
        try:
            shutdown()
        except Exception:
            logger.exception("OTEL tracer shutdown failed")
    _initialized = False


def get_tracer(name: str = "atp"):
    """返回 tracer。未初始化时 OTel API 自动返回 no-op tracer。"""
    return trace.get_tracer(name)
