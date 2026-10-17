"""灰度击穿自动熔断与秒级一键回滚看门狗单测 (T2.2)"""

from __future__ import annotations

import pytest

from app.services.canary_auto_rollback_guard import (
    CanaryGuardAction,
    CanaryRollbackPolicy,
    evaluate_canary_rollback_guard,
)
from app.services.canary_baseline_metric_comparator import (
    CanaryDualTrackComparisonReport,
    MetricDeviationVerdict,
    TrackMetricsSample,
)
from app.services.canary_traffic_coloration_engine import (
    CanaryColorationRule,
    ColorationRuleType,
    get_global_canary_manager,
)


@pytest.fixture(autouse=True)
def setup_mgr():
    mgr = get_global_canary_manager()
    mgr.clear()
    mgr._load_seed_rules()
    yield
    mgr.clear()
    mgr._load_seed_rules()


def _build_test_report(
    error_diff: float = 0.1,
    lat_ratio: float = 1.05,
    canary_success: float = 99.8,
    verdict: MetricDeviationVerdict = MetricDeviationVerdict.CONFORMANT,
) -> CanaryDualTrackComparisonReport:
    base = TrackMetricsSample(
        track_name="baseline",
        version_tag="v1.0",
        total_requests=5000,
        error_requests=5,
        error_rate_pct=0.1,
        success_rate_pct=99.9,
        p99_latency_ms=100.0,
        avg_latency_ms=30.0,
    )
    canary = TrackMetricsSample(
        track_name="canary",
        version_tag="v1.1-canary",
        total_requests=1000,
        error_requests=int(1000 * (0.1 + error_diff) / 100.0),
        error_rate_pct=0.1 + error_diff,
        success_rate_pct=canary_success,
        p99_latency_ms=100.0 * lat_ratio,
        avg_latency_ms=30.0 * lat_ratio,
    )
    return CanaryDualTrackComparisonReport(
        report_id="comp_01",
        target_service="payment-service",
        canary_version="v1.1-canary",
        baseline_version="v1.0",
        overall_verdict=verdict,
        baseline_metrics=base,
        canary_metrics=canary,
        error_rate_diff_pct=error_diff,
        latency_p99_ratio=lat_ratio,
        cpu_diff_pct=1.0,
        findings=[],
    )


def test_evaluate_guard_safe_proceed():
    rep = _build_test_report(error_diff=0.05, lat_ratio=1.02)
    verdict = evaluate_canary_rollback_guard(rep)
    assert verdict.is_tripped is False
    assert verdict.action == CanaryGuardAction.SAFE_PROCEED
    assert verdict.disabled_rules_count == 0


def test_evaluate_guard_error_rate_breach_triggers_rollback():
    mgr = get_global_canary_manager()
    # 确保 payment-service 有启用的规则
    rule = CanaryColorationRule(
        rule_id="r_pay_test",
        name="支付灰度规则",
        rule_type=ColorationRuleType.WEIGHT_RANDOM,
        target_service="payment-service",
        canary_version_tag="v1.1-canary",
        weight_pct=15.0,
        is_enabled=True,
    )
    mgr.add_rule(rule)

    # 错误率突增 3.5% (超过默认 2.0% 红线)
    rep = _build_test_report(error_diff=3.5, lat_ratio=1.05)
    verdict = evaluate_canary_rollback_guard(rep)

    assert verdict.is_tripped is True
    assert verdict.action == CanaryGuardAction.TRIGGERED_AUTO_ROLLBACK
    assert any("错误率增量" in r for r in verdict.tripped_rules)
    assert verdict.disabled_rules_count >= 1
    assert "紧急熔断触发" in verdict.verdict_message

    # 验证规则已被强制禁用，权重清零
    updated_rule = mgr.get_rule("r_pay_test")
    assert updated_rule is not None
    assert updated_rule.is_enabled is False
    assert updated_rule.weight_pct == 0.0


def test_evaluate_guard_latency_and_success_rate_breaches():
    # 延迟倍率 2.0x (超过 1.5x) 且 成功率 92.0% (跌破 95.0% 保底)
    rep = _build_test_report(error_diff=0.1, lat_ratio=2.0, canary_success=92.0)
    verdict = evaluate_canary_rollback_guard(rep)

    assert verdict.is_tripped is True
    assert verdict.action == CanaryGuardAction.TRIGGERED_AUTO_ROLLBACK
    assert len(verdict.tripped_rules) == 2


def test_evaluate_guard_warning_when_auto_rollback_disabled():
    policy = CanaryRollbackPolicy(
        max_error_rate_diff_pct=2.0,
        auto_rollback_enabled=False,  # 仅报警不自动回滚
    )
    rep = _build_test_report(error_diff=3.0)
    verdict = evaluate_canary_rollback_guard(rep, policy=policy)

    assert verdict.is_tripped is True
    assert verdict.action == CanaryGuardAction.WARNING_WATCH
    assert verdict.disabled_rules_count == 0
    assert "未开启自动回滚" in verdict.verdict_message

    d = verdict.to_dict()
    assert d["action"] == "WARNING_WATCH"
    assert d["is_tripped"] is True
