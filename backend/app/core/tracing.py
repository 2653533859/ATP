import uuid
from contextvars import ContextVar, Token

import opentelemetry.trace as trace

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def generate_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def get_trace_id() -> str:
    return trace_id_var.get("")


def set_trace_id(trace_id: str) -> Token[str]:
    return trace_id_var.set(trace_id)


def reset_trace_id(token: Token[str]) -> None:
    trace_id_var.reset(token)


def build_trace_context(*, trace_id: str | None = None, **extra: object) -> dict:
    context = {
        "trace_id": trace_id or get_trace_id() or generate_trace_id(),
    }
    return {
        **context,
        **{key: value for key, value in extra.items() if value is not None},
    }


def attach_app_trace_id_to_current_span(trace_id: str | None = None) -> None:
    """把 application 层 trace_id 写入当前 OTel span 的 attribute。

    便于在 Jaeger UI 通过 `app.trace_id` tag 反查到当前业务 trace。未启用 OTel 时
    `get_current_span()` 返回 NonRecordingSpan，set_attribute 为 no-op。
    """
    tid = trace_id or get_trace_id()
    if not tid:
        return
    span = trace.get_current_span()
    span.set_attribute("app.trace_id", tid)
