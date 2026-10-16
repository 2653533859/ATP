"""生产全链路压测安全审计与爆炸半径评估器单元测试 (T4.2)。"""

from __future__ import annotations

import pytest
from app.services.stress_blast_radius_safety_evaluator import (
    BlastRadiusTier,
    StressSafetyVerdict,
    clear_blast_radius_store,
    evaluate_stress_blast_radius_safety,
    get_blast_radius_report,
    list_blast_radius_reports,
)


@pytest.fixture(autouse=True)
def _reset_blast_radius_state():
    clear_blast_radius_store()
    yield
    clear_blast_radius_store()


def test_evaluate_stress_blast_radius_approved():
    """测试防护措施 100% 具备、评估准入通过 (PASS_READY_FOR_STRESS) 并生成 64 位 SHA-256 防篡改指纹。"""
    report = evaluate_stress_blast_radius_safety(
        drill_id="drill_prod_001",
        target_services=["gateway", "order_service", "pay_service"],
        shadow_traffic_isolated=True,
        shadow_tables_ready=True,
        external_bypasses_ready=True,
        circuit_breaker_active=True,
        estimated_max_qps=3500.0,
        participating_cell_ids=["cell_east_01"],
    )

    assert report.safety_score_pct == 100.0
    assert report.is_stress_approved is True
    assert report.safety_verdict == StressSafetyVerdict.PASS_READY_FOR_STRESS
    assert report.blast_radius_tier == BlastRadiusTier.TIER_1_ISOLATED
    assert len(report.audit_tamper_evident_fingerprint) == 64
    assert len(report.safety_checks) == 4
    assert all(c.is_passed for c in report.safety_checks)

    saved = get_blast_radius_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_blast_radius_reports()) == 1


def test_evaluate_stress_blast_radius_blocked_uncontrolled():
    """测试影子库表或染色未就绪触发一票否决阻断 (BLOCKED_HIGH_BLAST_RADIUS)。"""
    report = evaluate_stress_blast_radius_safety(
        drill_id="drill_risky_002",
        target_services=["finance_service"],
        shadow_traffic_isolated=True,
        shadow_tables_ready=False,  # 未准备影子表 -> 致命风险
        external_bypasses_ready=True,
        circuit_breaker_active=True,
    )

    assert report.is_stress_approved is False
    assert report.safety_verdict == StressSafetyVerdict.BLOCKED_HIGH_BLAST_RADIUS
    assert report.blast_radius_tier == BlastRadiusTier.TIER_4_UNCONTROLLED_GLOBAL
    assert report.safety_score_pct < 100.0
