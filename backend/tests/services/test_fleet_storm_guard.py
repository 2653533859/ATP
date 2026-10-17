"""任务调度风暴熔断防雪崩看门狗单测 (T4.1)"""

from __future__ import annotations

import pytest

from app.services.fleet_storm_guard import (
    StormGuardConfig,
    StormGuardState,
    StormGuardVerdict,
    calculate_jittered_backoff,
    clear_storm_guard_state,
    evaluate_dispatch_storm_protection,
    get_storm_guard_status,
    record_dispatch_outcome,
    reset_circuit_breaker,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_storm_guard_state()
    yield
    clear_storm_guard_state()


def test_storm_guard_normal_allow():
    verdict, reason = evaluate_dispatch_storm_protection("task_001")
    assert verdict == StormGuardVerdict.ALLOW
    assert "通过调度风暴安全审查" in reason

    status = get_storm_guard_status()
    assert status.state == StormGuardState.CLOSED
    assert status.active_circuit_breaker is False


def test_consecutive_failures_trips_circuit_breaker():
    cfg = StormGuardConfig(consecutive_failure_threshold=3, circuit_break_duration_sec=10.0)

    # 连续记录 3 次调度失败
    record_dispatch_outcome(False, cfg)
    record_dispatch_outcome(False, cfg)
    record_dispatch_outcome(False, cfg)

    status = get_storm_guard_status()
    assert status.state == StormGuardState.OPEN
    assert status.active_circuit_breaker is True
    assert status.consecutive_failures == 3

    # 在断路器处于 OPEN 时尝试派发调度，必须被快速失败熔断阻断
    verdict, reason = evaluate_dispatch_storm_protection("task_blocked", cfg)
    assert verdict == StormGuardVerdict.CIRCUIT_TRIPPED
    assert "处于 OPEN 状态" in reason


def test_reset_circuit_breaker():
    cfg = StormGuardConfig(consecutive_failure_threshold=2)
    record_dispatch_outcome(False, cfg)
    record_dispatch_outcome(False, cfg)

    assert get_storm_guard_status().state == StormGuardState.OPEN

    # 手动复位
    reset_circuit_breaker()
    status_reset = get_storm_guard_status()
    assert status_reset.state == StormGuardState.CLOSED
    assert status_reset.consecutive_failures == 0

    verdict, _ = evaluate_dispatch_storm_protection("task_after_reset")
    assert verdict == StormGuardVerdict.ALLOW


def test_calculate_jittered_backoff():
    # 测试指数退避抖动打散在指定区间内
    for retry in range(5):
        b = calculate_jittered_backoff(retry, base_delay_ms=100.0, max_delay_ms=2000.0)
        assert b >= 0.0
        assert b <= 2000.0
