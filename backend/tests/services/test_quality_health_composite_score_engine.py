"""全生命周期多维质量健康综合评分单元测试 (T4.1)。"""

from __future__ import annotations

import pytest
from app.services.quality_health_composite_score_engine import (
    QualityGrade,
    QualityInputMetrics,
    calculate_quality_health_score,
    clear_health_score_store,
    get_quality_health_report,
    list_quality_health_reports,
)


@pytest.fixture(autouse=True)
def _reset_score_state():
    clear_health_score_store()
    yield
    clear_health_score_store()


def test_calculate_quality_health_score_grade_a_plus():
    """测试各项指标优异时获得 A+ 等级。"""
    metrics = QualityInputMetrics(
        test_pass_rate_pct=100.0,
        code_coverage_pct=92.0,
        mutation_score_pct=88.0,
        p0_defects_count=0,
        p1_defects_count=0,
        p2_defects_count=0,
        change_risk_score=5.0,
        compliance_score_pct=100.0,
    )

    result = calculate_quality_health_score(target_name="release-v4.2.0", metrics=metrics)
    assert result.target_name == "release-v4.2.0"
    assert result.composite_score >= 90.0
    assert result.grade == QualityGrade.GRADE_A_PLUS
    assert len(result.dimension_scores) == 6
    assert "保持" in result.optimization_recommendations[0]


def test_calculate_quality_health_score_p0_veto_constraint():
    """测试存在 P0 缺陷时触发一票否决上限限制 (最高截断为 65 分，等级 C)。"""
    metrics = QualityInputMetrics(
        test_pass_rate_pct=100.0,
        code_coverage_pct=95.0,
        mutation_score_pct=90.0,
        p0_defects_count=1,  # 存在 1 个未解决 P0
        change_risk_score=5.0,
    )

    result = calculate_quality_health_score(target_name="release-hotfix", metrics=metrics)
    assert result.composite_score <= 65.0
    assert result.grade == QualityGrade.GRADE_C
    assert any("P0" in r for r in result.primary_risk_factors)


def test_calculate_quality_health_score_coverage_and_mutation_penalty():
    metrics = QualityInputMetrics(
        test_pass_rate_pct=96.0,
        code_coverage_pct=70.0,  # 偏低
        mutation_score_pct=60.0,  # 偏低
        p0_defects_count=0,
        p1_defects_count=2,
        p2_defects_count=2,
        change_risk_score=30.0,
    )

    result = calculate_quality_health_score(target_name="feature-sprint", metrics=metrics)
    assert 70.0 <= result.composite_score < 80.0
    assert result.grade == QualityGrade.GRADE_B


def test_list_and_get_health_reports():
    """测试质量健康报告查询与持久化。"""
    metrics = QualityInputMetrics()
    res = calculate_quality_health_score(target_name="v4.2.0-rc1", metrics=metrics)

    saved = get_quality_health_report(res.report_id)
    assert saved is not None
    assert saved.report_id == res.report_id

    reports = list_quality_health_reports()
    assert len(reports) == 1
