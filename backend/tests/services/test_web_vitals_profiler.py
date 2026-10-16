"""Unit tests for D3.2 Web Vitals Profiler Service."""

import pytest

from app.services.web_vitals_profiler import (
    VitalRating,
    diagnose_web_vitals,
    get_web_vitals_report,
    list_web_vitals_reports,
    reset_web_vitals_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_web_vitals_registry()
    yield
    reset_web_vitals_registry()


def test_diagnose_web_vitals_good_rating():
    report = diagnose_web_vitals(
        target_url="https://app.internal/dashboard",
        lcp_ms=1800.0,
        inp_ms=90.0,
        cls_score=0.02,
        fcp_ms=1200.0,
        ttfb_ms=250.0,
        tbt_ms=50.0,
    )

    assert report.overall_rating == VitalRating.GOOD
    assert report.overall_performance_score >= 85.0
    assert report.core_vitals["LCP"].rating == VitalRating.GOOD
    assert report.core_vitals["INP"].rating == VitalRating.GOOD
    assert report.core_vitals["CLS"].rating == VitalRating.GOOD
    assert "页面 Core Web Vitals 各项体验指标表现卓越" in report.optimization_recommendations[0]


def test_diagnose_web_vitals_poor_rating_and_recommendations():
    report = diagnose_web_vitals(
        target_url="https://app.internal/checkout",
        lcp_ms=4800.0,  # 严重超时 (>4000)
        inp_ms=650.0,  # 严重延迟 (>500)
        cls_score=0.38,  # 严重抖动 (>0.25)
        fcp_ms=3200.0,
        ttfb_ms=2100.0,
        tbt_ms=800.0,
    )

    assert report.overall_rating == VitalRating.POOR
    assert report.overall_performance_score < 60.0
    assert report.core_vitals["LCP"].rating == VitalRating.POOR
    assert report.core_vitals["INP"].rating == VitalRating.POOR
    assert report.core_vitals["CLS"].rating == VitalRating.POOR

    # 校验针对性优化建议输出
    rec_text = " ".join(report.optimization_recommendations)
    assert "LCP 耗时达到 4800.0ms" in rec_text
    assert "CLS 布局偏移分数为 0.38" in rec_text
    assert "INP 交互延迟为 650.0ms" in rec_text
    assert "TTFB 首字节耗时达 2100.0ms" in rec_text


def test_blocking_resources_analysis():
    raw_res = [
        {
            "url": "https://cdn.internal/assets/vendor-bundle.js",
            "resource_type": "script",
            "duration_ms": 450.0,
            "transfer_size_kb": 1200.0,
        },
        {
            "url": "https://cdn.internal/assets/main-theme.css",
            "resource_type": "stylesheet",
            "duration_ms": 120.0,
            "transfer_size_kb": 250.0,
        },
    ]

    report = diagnose_web_vitals(
        target_url="https://app.internal/portal",
        raw_resources=raw_res,
    )

    assert len(report.blocking_resources) == 2
    res_script = report.blocking_resources[0]
    assert res_script.impact == "high"
    assert "建议对 script 资源进行异步加载" in res_script.suggestion


def test_report_persistence_and_lookup():
    report = diagnose_web_vitals(target_url="https://app.internal/login")
    assert report.audit_id.startswith("audit_wv_")

    fetched = get_web_vitals_report(report.audit_id)
    assert fetched is not None
    assert fetched.target_url == "https://app.internal/login"

    all_reports = list_web_vitals_reports()
    assert len(all_reports) == 1
