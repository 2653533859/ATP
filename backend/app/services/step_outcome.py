"""Unified step error-strategy evaluation (abort / continue / ignore) and synthetic SKIP completion."""

from __future__ import annotations

from typing import Any, Literal

from app.models.case import RunStatus, StepResult
from app.services.execution_errors import classify_step_failure

ErrorStrategy = Literal["abort", "continue", "ignore"]

SKIP_REASON_UPSTREAM_ABORTED = "上游步骤失败，中止执行"
SKIP_REASON_USER_CANCELLED = "用户取消执行"
SKIP_REASON_LEASE_LOST = "设备租约丢失，中止执行"


def normalize_error_strategy(step_or_raw: Any) -> ErrorStrategy:
    if isinstance(step_or_raw, dict):
        raw = step_or_raw.get("error_strategy", (step_or_raw.get("params") or {}).get("error_strategy", "abort"))
    else:
        raw = step_or_raw
    val = str(raw or "abort").strip().lower()
    if val in {"abort", "continue", "ignore"}:
        return val  # type: ignore[return-value]
    return "abort"


def evaluate_step_failure_outcome(
    *,
    strategy: ErrorStrategy,
    error_message: str,
    action: str,
    platform: str = "android",
    exc: Exception | None = None,
) -> tuple[RunStatus, bool, bool, dict[str, Any]]:
    """Evaluate how a failed step maps to persisted status and control flow.

    Returns ``(persisted_status, should_abort, affects_case_pass, outcome_meta)``:
    - ``abort``:    status=failed,  should_abort=True,  affects_case_pass=True
    - ``continue``: status=failed,  should_abort=False, affects_case_pass=True
    - ``ignore``:   status=skipped, should_abort=False, affects_case_pass=False,
                    preserving full error/code/suggestion/screenshot + ``ignored_failure=True``
                    so Flaky analytics still capture the real instability signal.
    """
    error_code, suggestion = classify_step_failure(error_message, action=action, platform=platform, exc=exc)
    if strategy == "ignore":
        skip_reason = f"失败已忽略：{error_message}"
        return (
            RunStatus.skipped,
            False,
            False,
            {
                "strategy": "ignore",
                "ignored_failure": True,
                "skip_reason": skip_reason,
                "original_error": error_message,
                "error_code": error_code,
                "suggestion": suggestion,
            },
        )
    return (
        RunStatus.failed,
        strategy == "abort",
        True,
        {
            "strategy": strategy,
            "ignored_failure": False,
            "error_code": error_code,
            "suggestion": suggestion,
        },
    )


def build_synthetic_skipped_step(
    *,
    run_id: int,
    step_index: int,
    step_name: str,
    reason: str,
) -> StepResult:
    """Create a synthetic SKIP record for an unexecuted trailing step after abort/cancel/lease-loss."""
    return StepResult(
        run_id=run_id,
        step_index=step_index,
        name=step_name,
        status=RunStatus.skipped,
        duration_ms=0,
        request_data=None,
        response_data={
            "outcome": {
                "synthetic_skip": True,
                "skip_reason": reason,
            }
        },
        error_message=reason,
        screenshot_url=None,
    )
