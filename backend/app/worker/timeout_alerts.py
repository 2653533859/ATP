"""Celery 任务超时告警 handler — 抽离实现。

celery_app.py 把 `task_failure` / `task_revoked` 信号桥接到本模块函数，
本模块不直接 import celery（仅靠类名判断 SoftTimeLimitExceeded），方便独立单测。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _annotate_span(kind: str) -> None:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        span.set_attribute("atp.task_timeout", kind)
    except Exception:
        pass


def on_task_failure(
    sender_name: str,
    task_id: str | None,
    exception: BaseException | None,
) -> None:
    if exception is None:
        return
    if type(exception).__name__ != "SoftTimeLimitExceeded":
        return
    logger.warning(
        "celery_soft_timeout task=%s id=%s",
        sender_name,
        task_id,
    )
    _annotate_span("soft")
    try:
        from app.core.metrics import CELERY_TIMEOUT

        CELERY_TIMEOUT.labels(kind="soft").inc()
    except Exception:
        pass


def on_task_revoked(
    sender_name: str,
    task_id: str | None,
    terminated: bool,
    signum: int | None,
    expired: bool,
) -> None:
    if not terminated or expired:
        return
    logger.warning(
        "celery_hard_timeout task=%s id=%s signum=%s",
        sender_name,
        task_id,
        signum,
    )
    _annotate_span("hard")
    try:
        from app.core.metrics import CELERY_TIMEOUT

        CELERY_TIMEOUT.labels(kind="hard").inc()
    except Exception:
        pass
