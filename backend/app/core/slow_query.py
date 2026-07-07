"""慢查询告警 — SQLAlchemy event listener 抽离实现。

`database.py` 在模块加载时 `attach` listener；本模块的函数对 SQLAlchemy 引擎之外完全无依赖，
可独立单测。
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_START_KEY = "atp_query_start"


def _trace_id_safe() -> str:
    try:
        from app.core.tracing import get_trace_id

        return get_trace_id() or ""
    except Exception:
        return ""


def _annotate_span(elapsed_ms: float) -> None:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        span.set_attribute("atp.slow_query", True)
        span.set_attribute("atp.slow_query_ms", round(elapsed_ms, 1))
    except Exception:
        pass


def maybe_emit_warning(
    elapsed_ms: float,
    statement: str | None,
    parameters: Any,
    threshold_ms: int,
) -> bool:
    if elapsed_ms < threshold_ms:
        return False
    sql_snippet = (statement or "")[:500]
    params_snippet = repr(parameters)[:200] if parameters else ""
    logger.warning(
        "slow_query duration_ms=%.1f threshold_ms=%d trace_id=%s sql=%s params=%s",
        elapsed_ms,
        threshold_ms,
        _trace_id_safe(),
        sql_snippet,
        params_snippet,
    )
    _annotate_span(elapsed_ms)
    try:
        from app.core.metrics import SLOW_QUERY

        SLOW_QUERY.inc()
    except Exception:
        pass
    return True


def on_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info[_START_KEY] = time.perf_counter()


def make_after_cursor_handler(threshold_ms: int):
    def handler(conn, cursor, statement, parameters, context, executemany):
        start = conn.info.pop(_START_KEY, None)
        if start is None:
            return
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        maybe_emit_warning(elapsed_ms, statement, parameters, threshold_ms)

    return handler
