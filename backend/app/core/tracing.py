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


def normalize_w3c_trace_id(raw_id: str | None = None) -> str:
    """Ensure a 32-hex character valid W3C trace ID string."""
    if not raw_id:
        return uuid.uuid4().hex
    cleaned = raw_id.replace("-", "").strip().lower()
    if len(cleaned) == 32 and all(c in "0123456789abcdef" for c in cleaned) and cleaned != "0" * 32:
        return cleaned
    if len(cleaned) == 16 and all(c in "0123456789abcdef" for c in cleaned):
        return f"{cleaned}{cleaned}"
    import hashlib

    return hashlib.md5(cleaned.encode("utf-8")).hexdigest()


def generate_w3c_span_id() -> str:
    """Generate a random 16-hex character non-zero W3C span ID."""
    return uuid.uuid4().hex[:16]


def generate_w3c_traceparent(
    trace_id: str | None = None,
    span_id: str | None = None,
    *,
    sampled: bool = True,
) -> str:
    """Format a W3C traceparent header: 00-{trace_id}-{span_id}-{flags}."""
    tid = normalize_w3c_trace_id(trace_id or get_trace_id())
    sid = span_id or generate_w3c_span_id()
    flags = "01" if sampled else "00"
    return f"00-{tid}-{sid}-{flags}"


def build_w3c_tracestate(
    *,
    run_id: int | None = None,
    case_id: int | None = None,
    vendor: str = "atp",
) -> str:
    """Format a W3C tracestate header containing ATP test execution context."""
    parts = []
    if run_id is not None:
        parts.append(f"r:{run_id}")
    if case_id is not None:
        parts.append(f"c:{case_id}")
    val = ";".join(parts) or "1"
    return f"{vendor}={val}"


def inject_w3c_trace_headers(
    headers: dict[str, str],
    *,
    run_id: int | None = None,
    case_id: int | None = None,
    trace_id: str | None = None,
) -> dict[str, str]:
    """Inject W3C traceparent and tracestate headers if not explicitly supplied."""
    out_headers = dict(headers)
    has_traceparent = any(k.lower() == "traceparent" for k in out_headers)
    if not has_traceparent:
        out_headers["traceparent"] = generate_w3c_traceparent(trace_id=trace_id)

    has_tracestate = any(k.lower() == "tracestate" for k in out_headers)
    if not has_tracestate and (run_id is not None or case_id is not None):
        out_headers["tracestate"] = build_w3c_tracestate(run_id=run_id, case_id=case_id)

    return out_headers
