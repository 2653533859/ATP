"""分布式混沌实验编排与稳态探测引擎单测 (T1.2)"""

from __future__ import annotations

import pytest

from app.services.chaos_steady_state_evaluator import (
    ChaosExperimentState,
    SteadyStateHypothesis,
    create_steady_state_sample,
    evaluate_steady_state,
    get_global_chaos_manager,
)


@pytest.fixture(autouse=True)
def clean_manager():
    get_global_chaos_manager().clear()
    yield
    get_global_chaos_manager().clear()


def test_create_steady_state_sample():
    sample = create_steady_state_sample(
        total_requests=1000,
        failed_requests=10,
        p99_latency_ms=180.5,
        is_probe_healthy=True,
    )
    assert sample.total_requests == 1000
    assert sample.success_requests == 990
    assert sample.current_success_rate_pct == 99.0
    assert sample.current_p99_latency_ms == 180.5
    assert sample.is_probe_healthy is True


def test_evaluate_steady_state_compliance():
    hypo = SteadyStateHypothesis(
        hypothesis_id="h1",
        target_service="order-service",
        min_success_rate_pct=98.0,
        max_p99_latency_ms=300.0,
        require_probe_healthy=True,
    )

    # 1. 达标合规采样点
    good_sample = create_steady_state_sample(1000, 5, 150.0, is_probe_healthy=True)
    is_ok, violations = evaluate_steady_state(hypo, good_sample)
    assert is_ok is True
    assert len(violations) == 0

    # 2. 成功率跌破门限
    bad_rate_sample = create_steady_state_sample(1000, 50, 200.0, is_probe_healthy=True)
    is_ok, violations = evaluate_steady_state(hypo, bad_rate_sample)
    assert is_ok is False
    assert any("成功率跌破稳态门限" in v for v in violations)

    # 3. P99 延迟击穿上限
    high_latency_sample = create_steady_state_sample(1000, 2, 550.0, is_probe_healthy=True)
    is_ok, violations = evaluate_steady_state(hypo, high_latency_sample)
    assert is_ok is False
    assert any("P99 延迟击穿稳态上限" in v for v in violations)

    # 4. 探针宕机
    down_probe_sample = create_steady_state_sample(1000, 0, 100.0, is_probe_healthy=False)
    is_ok, violations = evaluate_steady_state(hypo, down_probe_sample)
    assert is_ok is False
    assert any("系统健康检查探针失联" in v for v in violations)


def test_experiment_lifecycle_and_evaluation():
    mgr = get_global_chaos_manager()

    hypo = SteadyStateHypothesis(
        hypothesis_id="hypo_test",
        target_service="sms-service",
        min_success_rate_pct=95.0,
        max_p99_latency_ms=400.0,
    )

    # 1. 创建实验
    session = mgr.create_experiment(
        name="短信超时演练",
        target_service="sms-service",
        fault_id="fault_sms_loss_20pct",
        hypothesis=hypo,
    )
    assert session.state == ChaosExperimentState.CREATED

    # 2. 正常采样点合流 -> 稳态成立
    sample_1 = create_steady_state_sample(500, 2, 120.0)
    state, violations = mgr.record_and_evaluate(session.experiment_id, sample_1)
    assert state == ChaosExperimentState.STEADY_STATE_VERIFIED
    assert len(violations) == 0

    # 3. 故障恶化导致稳态破损 -> 稳态被打破
    sample_violated = create_steady_state_sample(500, 100, 600.0)
    state, violations = mgr.record_and_evaluate(session.experiment_id, sample_violated)
    assert state == ChaosExperimentState.STEADY_STATE_VIOLATED
    assert len(violations) >= 1
    assert len(session.violation_reasons) >= 1

    # 4. 终止实验
    stopped_sess = mgr.stop_experiment(session.experiment_id)
    assert stopped_sess is not None
    assert stopped_sess.state == ChaosExperimentState.STOPPED

    d = stopped_sess.to_dict()
    assert d["state"] == "STOPPED"
    assert d["experiment_id"] == session.experiment_id
