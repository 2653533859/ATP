"""生产防击穿自适应分级限流与熔断保护大脑单元测试 (T3.3)。"""

from __future__ import annotations

import pytest
from app.services.adaptive_avalanche_circuit_breaker import (
    BreakerAction,
    BreakerState,
    clear_avalanche_breaker_store,
    evaluate_adaptive_circuit_breaker,
    get_avalanche_breaker_report,
    get_current_breaker_state,
    list_avalanche_breaker_reports,
    reset_circuit_breaker,
)


@pytest.fixture(autouse=True)
def _reset_breaker_state():
    clear_avalanche_breaker_store()
    yield
    clear_avalanche_breaker_store()


def test_evaluate_adaptive_circuit_breaker_levels():
    """测试多阶梯评估：正常全速放行、一级缓速、二级急刹与硬核阻断熔断。"""
    # 1. 正常区间 (水位 50% < 70%) -> CLOSED_NORMAL, PASS_FULL_SPEED
    normal_rep = evaluate_adaptive_circuit_breaker(
        scenario_name="normal_load",
        max_resource_watermark_pct=50.0,
        p99_latency_ms=100.0,
        current_tps=1000.0,
    )
    assert normal_rep.is_circuit_broken is False
    assert normal_rep.final_decision.breaker_state == BreakerState.CLOSED_NORMAL
    assert normal_rep.final_decision.action == BreakerAction.PASS_FULL_SPEED
    assert normal_rep.final_decision.throttle_ratio_pct == 100.0

    # 2. 一级缓速 (水位 75% -> 70%~80%) -> THROTTLING_STAGE_1, 降速 25% (通过 75%)
    stage1_rep = evaluate_adaptive_circuit_breaker(
        scenario_name="stage1_load",
        max_resource_watermark_pct=75.0,
        current_tps=1000.0,
    )
    assert stage1_rep.final_decision.breaker_state == BreakerState.THROTTLING_STAGE_1
    assert stage1_rep.final_decision.action == BreakerAction.THROTTLE_DOWN
    assert stage1_rep.final_decision.throttle_ratio_pct == 75.0
    assert stage1_rep.final_decision.suggested_safe_tps == 750.0

    # 3. 二级急刹 (水位 82% -> 80%~85%) -> THROTTLING_STAGE_2, 降速 60% (通过 40%)
    stage2_rep = evaluate_adaptive_circuit_breaker(
        scenario_name="stage2_load",
        max_resource_watermark_pct=82.0,
        current_tps=1000.0,
    )
    assert stage2_rep.final_decision.breaker_state == BreakerState.THROTTLING_STAGE_2
    assert stage2_rep.final_decision.action == BreakerAction.THROTTLE_DOWN
    assert stage2_rep.final_decision.throttle_ratio_pct == 40.0
    assert stage2_rep.final_decision.suggested_safe_tps == 400.0

    # 4. 硬核阻断熔断 (水位 90% >= 85%) -> TRIPPED_HARD_BREAK, ABORT_STRESS_TEST
    break_rep = evaluate_adaptive_circuit_breaker(
        scenario_name="avalanche_risk_load",
        max_resource_watermark_pct=90.0,
        current_tps=1000.0,
    )
    assert break_rep.is_circuit_broken is True
    assert break_rep.final_decision.breaker_state == BreakerState.TRIPPED_HARD_BREAK
    assert break_rep.final_decision.action == BreakerAction.ABORT_STRESS_TEST
    assert break_rep.final_decision.throttle_ratio_pct == 0.0
    assert get_current_breaker_state() == BreakerState.TRIPPED_HARD_BREAK

    saved = get_avalanche_breaker_report(break_rep.report_id)
    assert saved is not None
    assert saved.report_id == break_rep.report_id
    assert len(list_avalanche_breaker_reports()) == 4


def test_reset_circuit_breaker():
    """测试手动重置熔断器。"""
    # 触发熔断
    evaluate_adaptive_circuit_breaker(scenario_name="trip_it", max_resource_watermark_pct=96.0)
    assert get_current_breaker_state() == BreakerState.TRIPPED_HARD_BREAK

    # 重置
    new_state = reset_circuit_breaker()
    assert new_state == BreakerState.CLOSED_NORMAL
    assert get_current_breaker_state() == BreakerState.CLOSED_NORMAL
