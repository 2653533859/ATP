"""Unit tests for C4.2 CI/CD Intelligent Quality Gate Rule Engine & Blocking Decision.

Tests:
1. QualityGateRule operator evaluation (gte, lte, eq, gt, lt)
2. evaluate_quality_gate passes with 0 exit_code on fully compliant metrics
3. evaluate_quality_gate blocks with exit_code 1 on blocker rule violation (e.g. open blocker defect)
4. evaluate_quality_gate produces WARNING with exit_code 0 when only warning-level rules fail
5. Custom quality gate profile dynamic registration and evaluation
"""

from __future__ import annotations

from app.services.quality_gate_engine import (
    QualityGateProfile,
    QualityGateRule,
    evaluate_quality_gate,
    list_gate_profiles,
    register_gate_profile,
)


def test_quality_gate_rule_operators():
    # 1. gte
    rule_gte = QualityGateRule("pass_rate", "gte", 99.0)
    assert rule_gte.evaluate(99.5)[0] is True
    assert rule_gte.evaluate(98.5)[0] is False

    # 2. lte
    rule_lte = QualityGateRule("defects", "lte", 0.0)
    assert rule_lte.evaluate(0)[0] is True
    assert rule_lte.evaluate(1)[0] is False

    # 3. eq
    rule_eq = QualityGateRule("exit_code", "eq", 0)
    assert rule_eq.evaluate(0)[0] is True
    assert rule_eq.evaluate(2)[0] is False

    # 4. None value
    assert rule_gte.evaluate(None)[0] is False


def test_evaluate_quality_gate_production_release_passed():
    compliant_metrics = {
        "pass_rate_pct": 99.5,
        "open_blocker_defects": 0,
        "composite_health_score": 92.0,
        "defect_escape_rate_pct": 2.0,
    }

    result = evaluate_quality_gate("gate_prod_release", compliant_metrics)
    assert result.status == "PASSED"
    assert result.exit_code == 0
    assert result.failed_blockers_count == 0
    assert len(result.blocked_reasons) == 0


def test_evaluate_quality_gate_blocker_violation():
    # Violation: 1 open blocker defect and pass rate 95% (<99%)
    violating_metrics = {
        "pass_rate_pct": 95.0,
        "open_blocker_defects": 1,
        "composite_health_score": 75.0,
        "defect_escape_rate_pct": 3.0,
    }

    result = evaluate_quality_gate("gate_prod_release", violating_metrics)
    assert result.status == "BLOCKED"
    assert result.exit_code == 1  # CI build blocking signal
    assert result.failed_blockers_count >= 1
    assert len(result.blocked_reasons) >= 1
    assert any("阻塞卡点" in r for r in result.blocked_reasons)


def test_evaluate_quality_gate_warning_only():
    # Blocker rules pass, but defect escape rate = 8% (>5% warning)
    warning_metrics = {
        "pass_rate_pct": 99.5,
        "open_blocker_defects": 0,
        "composite_health_score": 88.0,
        "defect_escape_rate_pct": 8.0,  # Warning violation
    }

    result = evaluate_quality_gate("gate_prod_release", warning_metrics)
    assert result.status == "WARNING"
    assert result.exit_code == 0  # Non-blocking for warnings
    assert result.failed_blockers_count == 0
    assert result.failed_warnings_count == 1


def test_custom_gate_profile_registration():
    custom_profile = QualityGateProfile(
        profile_id="gate_custom_security",
        name="安全漏洞准入门禁",
        description="严格拦截高危安全漏洞",
        rules=[
            QualityGateRule("critical_vulnerabilities", "lte", 0, "blocker", "零严重安全漏洞"),
            QualityGateRule("high_vulnerabilities", "lte", 2, "warning", "高危漏洞不多于2个"),
        ],
        block_on_failure=True,
    )
    register_gate_profile(custom_profile)

    profiles = list_gate_profiles()
    assert any(p.profile_id == "gate_custom_security" for p in profiles)

    res = evaluate_quality_gate(
        "gate_custom_security",
        {"critical_vulnerabilities": 1, "high_vulnerabilities": 0},
    )
    assert res.status == "BLOCKED"
    assert res.exit_code == 1
