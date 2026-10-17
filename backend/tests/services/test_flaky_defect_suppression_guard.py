"""偶发抖动缺陷提单防击穿安全沙箱看门狗单测 (T4.1)"""

from __future__ import annotations

from app.services.flaky_defect_suppression_guard import (
    DefectSuppressionAction,
    _calculate_historical_flaky_score,
    _is_transient_network_error,
    evaluate_defect_suppression_guard,
)


def test_calculate_historical_flaky_score():
    # 频繁震荡 [通过, 失败, 通过, 失败]
    oscillating_history = [True, False, True, False]
    score = _calculate_historical_flaky_score(oscillating_history)
    assert score == 1.0

    # 稳定通过
    stable_history = [True, True, True, True]
    assert _calculate_historical_flaky_score(stable_history) == 0.0

    # 空或单次
    assert _calculate_historical_flaky_score([True]) == 0.0


def test_is_transient_network_error():
    assert _is_transient_network_error("Temporary failure in name resolution", "") is True
    assert _is_transient_network_error("Connection reset by peer at TCP handshake", "") is True
    assert _is_transient_network_error("AssertionError: 200 != 500", "") is False


def test_evaluate_retry_success_suppresses_ticket():
    decision = evaluate_defect_suppression_guard(
        case_id="case_checkout_01",
        error_message="TimeoutError: 3000ms",
        stack_trace="Traceback...",
        retry_success=True,
        retry_count=2,
    )
    assert decision.is_suppressed is True
    assert decision.action == DefectSuppressionAction.SUPPRESS_FLAKY_RECOVERED
    assert decision.quarantined is False
    assert "自愈通过" in decision.justification


def test_evaluate_high_flaky_quarantine_suppression():
    # 历史震荡率 50%
    history = [True, False, True, False, True]

    decision = evaluate_defect_suppression_guard(
        case_id="case_flaky_dom_02",
        error_message="StaleElementReferenceException: element detached",
        stack_trace="Traceback...",
        retry_success=False,
        retry_count=1,
        historical_execution_results=history,
        flaky_threshold=0.30,
    )
    assert decision.is_suppressed is True
    assert decision.action == DefectSuppressionAction.SUPPRESS_QUARANTINED_FLAKY
    assert decision.quarantined is True
    assert decision.historical_flaky_score >= 0.5


def test_evaluate_transient_network_suppression():
    decision = evaluate_defect_suppression_guard(
        case_id="case_api_03",
        error_message="DNS resolution timeout on host api.internal",
        stack_trace="Traceback...",
        retry_success=False,
        retry_count=1,
    )
    assert decision.is_suppressed is True
    assert decision.action == DefectSuppressionAction.SUPPRESS_TRANSIENT_NETWORK


def test_evaluate_genuine_defect_dispatches_ticket():
    # 经历 3 次重试持续失败，历史稳定无抖动，确定性业务逻辑报错
    decision = evaluate_defect_suppression_guard(
        case_id="case_payment_04",
        error_message="InvalidAmountException: price mismatch 100 != 90",
        stack_trace="Traceback:\n  File payment.py, line 40\n    assert 100 == 90",
        retry_success=False,
        retry_count=3,
        historical_execution_results=[True, True, True, False, False, False],
    )
    assert decision.is_suppressed is False
    assert decision.action == DefectSuppressionAction.DISPATCH_GENUINE_DEFECT
    assert decision.quarantined is False

    d = decision.to_dict()
    assert d["is_suppressed"] is False
    assert d["action"] == "DISPATCH_GENUINE_DEFECT"
