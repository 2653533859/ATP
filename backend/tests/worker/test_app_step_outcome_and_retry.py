"""Unit tests for APP/UI idempotency-aware retry, error_strategy (abort/continue/ignore),
synthetic SKIP completion, and Flaky soft-instability awareness.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.models.bootstrap import load_all_models
from app.models.case import RunStatus

load_all_models()
from app.services.flaky_detector import _query_flaky_stats_from_db
from app.services.step_outcome import (
    SKIP_REASON_UPSTREAM_ABORTED,
    build_synthetic_skipped_step,
    evaluate_step_failure_outcome,
    normalize_error_strategy,
)
from app.services.step_retry import execute_ui_step_with_retry


def test_ui_retry_retries_transient_failure_but_refuses_replay_when_tap_submitted():
    # 1. Transient failure succeeds on attempt 2
    calls = {"n": 0}

    async def transient_attempt():
        calls["n"] += 1
        if calls["n"] == 1:
            return {"success": False, "error": "element not found"}
        return {"success": True, "data": {"clicked": True}}

    res, meta = asyncio.run(execute_ui_step_with_retry(transient_attempt, retry_count=2, backoff_seconds=0.0))
    assert res["success"] is True
    assert meta["attempts"] == 2
    assert meta["retried"] is True
    assert len(meta["history"]) == 1

    # 2. tap_submitted=True MUST NOT replay
    tap_calls = {"n": 0}

    async def submitted_tap_attempt():
        tap_calls["n"] += 1
        return {"success": False, "error": "timeout after tap", "tap_submitted": True}

    res2, meta2 = asyncio.run(execute_ui_step_with_retry(submitted_tap_attempt, retry_count=3, backoff_seconds=0.0))
    assert res2["success"] is False
    assert tap_calls["n"] == 1
    assert meta2["attempts"] == 1
    assert meta2["retried"] is False


def test_error_strategy_ignore_continue_abort_and_synthetic_skip():
    assert normalize_error_strategy({"error_strategy": "IGNORE"}) == "ignore"
    assert normalize_error_strategy({"error_strategy": "bogus"}) == "abort"

    # ignore -> status=skipped, does NOT fail case, preserves original error + ignored_failure=True
    st, abort, affects_pass, meta = evaluate_step_failure_outcome(
        strategy="ignore",
        error_message="关闭广告弹窗未找到元素",
        action="click",
        platform="android",
    )
    assert st == RunStatus.skipped
    assert abort is False
    assert affects_pass is False
    assert meta["ignored_failure"] is True
    assert meta["error_code"] == "E2001_ELEMENT_NOT_FOUND"
    assert "失败已忽略" in meta["skip_reason"]

    # continue -> status=failed, does NOT abort remaining, DOES fail case
    st_c, abort_c, affects_c, _ = evaluate_step_failure_outcome(
        strategy="continue",
        error_message="文本断言失败",
        action="assert_text",
    )
    assert st_c == RunStatus.failed
    assert abort_c is False
    assert affects_c is True

    # abort -> status=failed, aborts remaining
    st_a, abort_a, affects_a, _ = evaluate_step_failure_outcome(
        strategy="abort",
        error_message="timeout waiting for button",
        action="click",
    )
    assert st_a == RunStatus.failed
    assert abort_a is True
    assert affects_a is True

    # Synthetic SKIP step for remaining unexecuted steps
    syn = build_synthetic_skipped_step(
        run_id=9, step_index=2, step_name="提交订单", reason=SKIP_REASON_UPSTREAM_ABORTED
    )
    assert syn.status == RunStatus.skipped
    assert syn.duration_ms == 0
    assert syn.response_data["outcome"]["synthetic_skip"] is True


def test_flaky_detector_flags_soft_instability_from_ignored_failures_or_retries():
    fake_rows = [
        SimpleNamespace(case_id=1, status=RunStatus.passed, result_summary={"has_ignored_failure": True}),
        SimpleNamespace(case_id=1, status=RunStatus.passed, result_summary={"retried_step_count": 1}),
        SimpleNamespace(case_id=1, status=RunStatus.passed, result_summary={}),
        SimpleNamespace(case_id=1, status=RunStatus.passed, result_summary={}),
    ]

    class _FakeResult:
        def all(self):
            return fake_rows

    class _FakeDB:
        async def execute(self, _stmt):
            return _FakeResult()

    stats = asyncio.run(_query_flaky_stats_from_db(_FakeDB(), [1]))
    assert stats[1]["passed_runs"] == 4
    assert stats[1]["soft_instability_runs"] == 2
    assert stats[1]["is_flaky"] is True
