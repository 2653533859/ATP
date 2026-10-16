"""核心体验 Web Vitals 全景审计报告生成器单元测试 (T4.3)。"""

from __future__ import annotations

import pytest
from app.services.web_vitals_experience_audit_reporter import (
    MetricRating,
    clear_web_vitals_store,
    generate_web_vitals_report,
    get_web_vitals_report,
    list_web_vitals_reports,
)


@pytest.fixture(autouse=True)
def _reset_web_vitals_state():
    clear_web_vitals_store()
    yield
    clear_web_vitals_store()


def test_generate_web_vitals_report_all_good():
    """测试各项核心指标全绿、综合达标的报告。"""
    report = generate_web_vitals_report(
        target_url_or_page="https://atp.example.com/workbench",
        lcp_ms=1800.0,  # Good (<= 2500ms)
        inp_ms=120.0,  # Good (<= 200ms)
        cls_score=0.045,  # Good (<= 0.1)
        fcp_ms=900.0,
        ttfb_ms=250.0,
    )

    assert report.overall_cwv_passed is True
    assert report.performance_score_pct == 100.0
    assert report.lcp_metric.rating == MetricRating.GOOD
    assert report.inp_metric.rating == MetricRating.GOOD
    assert report.cls_metric.rating == MetricRating.GOOD
    assert len(report.auxiliary_metrics) == 2

    # 导出 Markdown
    md = report.to_markdown()
    assert "# Web Vitals 核心体验审计报告" in md
    assert "✅ 达标 (PASS)" in md
    assert "100.0 / 100" in md

    # 持久化检验
    saved = get_web_vitals_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_web_vitals_reports()) == 1


def test_generate_web_vitals_report_poor_and_recommendations():
    """测试多项指标严重恶化 (POOR)，触发针对性调优指引。"""
    report = generate_web_vitals_report(
        target_url_or_page="https://atp.example.com/heavy_table",
        lcp_ms=4500.0,  # Poor (> 4000ms)
        inp_ms=620.0,  # Poor (> 500ms)
        cls_score=0.35,  # Poor (> 0.25)
    )

    assert report.overall_cwv_passed is False
    assert report.performance_score_pct < 20.0
    assert report.lcp_metric.rating == MetricRating.POOR
    assert report.inp_metric.rating == MetricRating.POOR
    assert report.cls_metric.rating == MetricRating.POOR

    assert len(report.optimization_recommendations) == 3
    rec_text = " ".join(report.optimization_recommendations)
    assert "LCP" in rec_text
    assert "INP" in rec_text
    assert "CLS" in rec_text

    md = report.to_markdown()
    assert "❌ 未达标 (FAIL)" in md
