import uuid
from contextvars import ContextVar, Token

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
