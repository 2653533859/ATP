"""全链路压力演练综合审计报告生成器单元测试 (T4.3)。"""

from __future__ import annotations

import pytest
from app.services.full_link_stress_drill_reporter import (
    DrillGrade,
    clear_full_drill_report_store,
    generate_full_link_stress_drill_report,
    get_full_drill_report,
    list_full_drill_reports,
)


@pytest.fixture(autouse=True)
def _reset_full_drill_state():
    clear_full_drill_report_store()
    yield
    clear_full_drill_report_store()


def test_generate_full_link_stress_drill_report_grade_a():
    """测试各项指标卓越 (GRADE_A_EXCELLENT)，获得生产容量准入通过并导出 Markdown。"""
    report = generate_full_link_stress_drill_report(
        drill_id="drill_d11_001",
        scenario_name="全链路核心结算加压演练",
        peak_concurrency_vu=2000,
        peak_tps=4800.0,
        p99_latency_ms=120.0,
        error_rate_pct=0.01,
        knee_point_concurrency=2000,
        knee_point_tps=4800.0,
        cliff_point_concurrency=None,
        max_db_watermark_pct=65.0,
        max_redis_watermark_pct=50.0,
        max_mq_backlog=800,
        circuit_breaker_triggered=False,
        failover_rto_ms=1350.0,
    )

    assert report.overall_drill_grade == DrillGrade.GRADE_A_EXCELLENT
    assert report.is_production_approved is True
    assert report.composite_health_score_pct == 100.0
    assert len(report.sha256_audit_fingerprint) == 64

    # 验证 Markdown 格式输出
    md = report.to_markdown()
    assert "# 生产全链路压测综合审计与容量规划报告" in md
    assert "✅ 生产容量准入通过 (APPROVED)" in md
    assert "GRADE_A_EXCELLENT" in md
    assert "4800.0 TPS" in md
    assert "120.0 ms" in md

    # 持久化检验
    saved = get_full_drill_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_full_drill_reports()) == 1


def test_generate_full_link_stress_drill_report_rejected():
    """测试发生熔断或错误率过高时，判定为 GRADE_D_REJECTED 阻断生产上线。"""
    report = generate_full_link_stress_drill_report(
        drill_id="drill_fail_002",
        scenario_name="失败演练",
        peak_concurrency_vu=5000,
        peak_tps=1200.0,
        p99_latency_ms=3500.0,
        error_rate_pct=8.5,
        knee_point_concurrency=1000,
        knee_point_tps=3000.0,
        circuit_breaker_triggered=True,
    )

    assert report.overall_drill_grade == DrillGrade.GRADE_D_REJECTED
    assert report.is_production_approved is False
    assert report.composite_health_score_pct == 45.0
    md = report.to_markdown()
    assert "❌ 存在高危风险阻断 (BLOCKED)" in md
