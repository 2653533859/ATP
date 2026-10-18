"""分布式海量虚拟用户发压调度与阶梯加压器单测 (T1.2)"""

from __future__ import annotations

from app.services.stress_load_profile_stepper import (
    StressLoadProfileType,
    StressStepperAction,
    calculate_distributed_worker_allocation,
    evaluate_stress_step_progression,
    generate_standard_step_ramp_plan,
)


def test_calculate_distributed_worker_allocation():
    # 1. 较小并发：1000 VU -> 单个发压节点 (max 2000 VU/node)
    alloc_1k = calculate_distributed_worker_allocation(1000)
    assert alloc_1k.worker_nodes_count == 1
    assert alloc_1k.vu_per_worker == 1000
    assert alloc_1k.target_peak_vu == 1000

    # 2. 中等并发：5000 VU -> 3 个发压节点
    alloc_5k = calculate_distributed_worker_allocation(5000)
    assert alloc_5k.worker_nodes_count == 3
    assert alloc_5k.vu_per_worker == 1667
    assert alloc_5k.total_assigned_vu >= 5000

    # 3. 超高并发：10,000 VU -> 5 个发压节点
    alloc_10k = calculate_distributed_worker_allocation(10000)
    assert alloc_10k.worker_nodes_count == 5
    assert alloc_10k.vu_per_worker == 2000

    d = alloc_10k.to_dict()
    assert d["worker_nodes_count"] == 5
    assert d["vu_per_worker"] == 2000


def test_generate_standard_step_ramp_plan():
    plan = generate_standard_step_ramp_plan(
        target_service="order-service",
        initial_vu=500,
        step_vu=1000,
        steps_count=5,
        stage_duration_seconds=60,
    )

    assert plan.target_service == "order-service"
    assert plan.profile_type == StressLoadProfileType.STEP_RAMP_UP
    assert len(plan.stages) == 5
    assert plan.stages[0].target_vu_count == 500
    assert plan.stages[1].target_vu_count == 1500
    assert plan.stages[4].target_vu_count == 4500
    assert plan.peak_vu_count == 4500
    assert plan.total_duration_seconds == 300

    d = plan.to_dict()
    assert d["peak_vu_count"] == 4500
    assert len(d["stages"]) == 5


def test_evaluate_step_progression_maintain_current():
    plan = generate_standard_step_ramp_plan(steps_count=3, stage_duration_seconds=60)
    # 当前阶梯 1，耗时 30 秒 (< 60 秒)
    verdict = evaluate_stress_step_progression(
        plan=plan,
        current_stage_index=1,
        stage_elapsed_seconds=30,
        current_error_rate_pct=0.1,
    )

    assert verdict.action == StressStepperAction.MAINTAIN_CURRENT
    assert verdict.current_vu_count == 500
    assert verdict.recommended_next_vu == 500
    assert "剩余 30 秒" in verdict.message


def test_evaluate_step_progression_advance_next_stage():
    plan = generate_standard_step_ramp_plan(steps_count=3, stage_duration_seconds=60)
    # 当前阶梯 1，耗时 60 秒 (达标)，应自适应推进到阶段 2
    verdict = evaluate_stress_step_progression(
        plan=plan,
        current_stage_index=1,
        stage_elapsed_seconds=60,
        current_error_rate_pct=0.05,
    )

    assert verdict.action == StressStepperAction.ADVANCE_NEXT_STAGE
    assert verdict.current_vu_count == 500
    assert verdict.recommended_next_vu == 1500
    assert "自适应晋级" in verdict.message


def test_evaluate_step_progression_completed_full_plan():
    plan = generate_standard_step_ramp_plan(steps_count=3, stage_duration_seconds=60)
    # 最后一阶梯 (3)，耗时 60 秒 (达标)，全套计划顺利完成
    verdict = evaluate_stress_step_progression(
        plan=plan,
        current_stage_index=3,
        stage_elapsed_seconds=60,
        current_error_rate_pct=0.1,
    )

    assert verdict.action == StressStepperAction.COMPLETED_FULL_PLAN
    assert verdict.current_vu_count == 2500
    assert "所有规划发压阶段已 100% 执行完成" in verdict.message


def test_evaluate_step_progression_abort_overload():
    plan = generate_standard_step_ramp_plan(steps_count=3, stage_duration_seconds=60)
    # 错误率突增至 3.5% (超过默认 1.0% 红线)
    verdict = evaluate_stress_step_progression(
        plan=plan,
        current_stage_index=2,
        stage_elapsed_seconds=20,
        current_error_rate_pct=3.5,
        error_rate_threshold_pct=1.0,
    )

    assert verdict.action == StressStepperAction.ABORT_OVERLOAD
    assert verdict.recommended_next_vu == 0
    assert "触发过载保护" in verdict.message
