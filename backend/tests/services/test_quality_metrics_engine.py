"""Unit tests for C4.1 Software Quality Health Metrics & Multi-Dimensional Scoring Engine.

Tests:
1. calculate_coverage_score calculates automation coverage index and normalization
2. calculate_escape_score assesses defect escape rate and penalties
3. calculate_stability_score and calculate_mttr_score evaluate test run variance and repair latency
4. compute_quality_health_report produces Grade A and APPROVED readiness for healthy projects
5. compute_quality_health_report produces BLOCKED readiness and alerts on high-risk projects
"""

from __future__ import annotations

from app.services.quality_metrics_engine import (
    calculate_coverage_score,
    calculate_escape_score,
    calculate_mttr_score,
    calculate_stability_score,
    compute_quality_health_report,
)


def test_coverage_score_calculation():
    # 85 automated out of 100 cases = 85%
    pct, score = calculate_coverage_score(100, 85)
    assert pct == 85.0
    assert score >= 90.0

    # Low coverage: 30 automated out of 100 cases = 30%
    low_pct, low_score = calculate_coverage_score(100, 30)
    assert low_pct == 30.0
    assert low_score < 50.0


def test_defect_escape_score_calculation():
    # 2 escapes out of 42 defects = ~4.76%
    esc_pct, esc_score = calculate_escape_score(internal_defects=40, prod_escapes=2)
    assert round(esc_pct, 1) == 4.8
    assert esc_score >= 70.0

    # Severe escape: 10 escapes out of 20 defects = 50%
    bad_pct, bad_score = calculate_escape_score(internal_defects=10, prod_escapes=10)
    assert bad_pct == 50.0
    assert bad_score <= 0.0


def test_stability_and_mttr_scores():
    # 2 flaky runs out of 50 runs = 4% flaky
    flaky_pct, stab_score = calculate_stability_score(total_runs=50, flaky_runs=2)
    assert flaky_pct == 4.0
    assert stab_score == 90.0

    # Fast MTTR (1.5 hours) -> 100 score
    assert calculate_mttr_score(1.5) == 100.0
    # Slow MTTR (50 hours) -> 30 score
    assert calculate_mttr_score(50.0) == 30.0


def test_compute_quality_health_report_healthy_project():
    report = compute_quality_health_report(
        project_id=1,
        total_cases=120,
        automated_cases=110,  # ~91.6% coverage
        internal_defects=50,
        prod_escapes=1,  # ~1.96% escape
        total_runs=80,
        flaky_runs=1,  # 1.25% flaky
        mttr_hours=2.5,  # 85 score
    )

    assert report.project_id == 1
    assert report.composite_health_score >= 88.0
    assert report.grade in {"A", "B"}
    assert report.release_readiness == "APPROVED"
    assert len(report.actionable_recommendations) >= 1
    assert len(report.risk_alerts) == 0  # No critical alerts


def test_compute_quality_health_report_high_risk_project():
    report = compute_quality_health_report(
        project_id=2,
        total_cases=100,
        automated_cases=20,  # 20% coverage -> low
        internal_defects=10,
        prod_escapes=6,  # 37.5% escape -> high
        total_runs=20,
        flaky_runs=5,  # 25% flaky -> high
        mttr_hours=36.0,  # 36 hours -> slow
    )

    assert report.composite_health_score < 65.0
    assert report.grade in {"D", "F"}
    assert report.release_readiness == "BLOCKED"
    assert len(report.risk_alerts) >= 3  # Triggers escape, coverage, and flaky alerts
    assert any("缺陷逃逸率严重超标" in a for a in report.risk_alerts)
    assert any("自动化覆盖率偏低" in a for a in report.risk_alerts)
