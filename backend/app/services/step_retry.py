"""Idempotency-aware retry helper for APP / UI automation steps."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

MAX_UI_RETRY_COUNT = 3
DEFAULT_UI_RETRY_BACKOFF_SECONDS = 1.0


def parse_ui_retry_count(step: dict[str, Any] | None) -> int:
    """Parse bounded UI step retry count (0..3, default 0)."""
    if not isinstance(step, dict):
        return 0
    raw = step.get("retry_count", (step.get("params") or {}).get("retry_count", 0))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_UI_RETRY_COUNT, value))


async def _cancellable_backoff(seconds: float, check_cancel: Callable[[], None] | None) -> None:
    if seconds <= 0:
        return
    deadline = time.monotonic() + seconds
    while True:
        if check_cancel is not None:
            check_cancel()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        await asyncio.sleep(min(0.1, remaining))


async def execute_ui_step_with_retry(
    attempt_fn: Callable[[], Awaitable[dict[str, Any]]],
    *,
    retry_count: int = 0,
    backoff_seconds: float = DEFAULT_UI_RETRY_BACKOFF_SECONDS,
    check_cancel: Callable[[], None] | None = None,
    deadline: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run a UI step attempt up to ``1 + retry_count`` times with side-effect guard.

    Rules:
    - Only retries when ``result["success"] is False``.
    - NEVER retries if ``result.get("tap_submitted")`` or ``result.get("action_submitted")``
      or ``(result.get("data") or {}).get("tap_submitted")`` is truthy (irreversible side effect).
    - Checks ``check_cancel`` during backoff so user cancellation aborts immediately.
    - Respects shared ``deadline`` when provided (e.g. image matching timeout budget).
    """
    max_retries = max(0, min(MAX_UI_RETRY_COUNT, int(retry_count or 0)))
    history: list[dict[str, Any]] = []
    attempts = 0
    last_result: dict[str, Any] = {"success": False, "error": "步骤未执行"}

    for attempt in range(1, max_retries + 2):
        attempts = attempt
        last_result = await attempt_fn()
        if last_result.get("success"):
            break

        raw_data = last_result.get("data")
        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
        raw_match = data.get("image_match")
        image_match: dict[str, Any] = raw_match if isinstance(raw_match, dict) else {}
        if (
            last_result.get("tap_submitted")
            or last_result.get("action_submitted")
            or data.get("tap_submitted")
            or image_match.get("tap_submitted")
        ):
            # Side-effect already submitted with unknown outcome -> NEVER replay
            break

        if attempt > max_retries:
            break

        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sleep_for = min(backoff_seconds, remaining)
        else:
            sleep_for = backoff_seconds

        history.append({"attempt": attempt, "error": str(last_result.get("error") or "")})
        await _cancellable_backoff(sleep_for, check_cancel)
        if deadline is not None and time.monotonic() >= deadline:
            break

    retry_meta = {
        "attempts": attempts,
        "retry_count": max_retries,
        "retried": attempts > 1,
        "history": history,
    }
    return last_result, retry_meta
