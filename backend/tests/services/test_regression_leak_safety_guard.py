"""增量筛选漏测风险动态防线看门狗单测 (T4.1)"""

from __future__ import annotations

from app.services.code_diff_symbol_extractor import (
    ChangedSymbolItem,
    SymbolChangeSeverity,
    SymbolChangeType,
    SymbolType,
)
from app.services.regression_leak_safety_guard import (
    LeakGuardVerdict,
    LeakRiskLevel,
    audit_precision_regression_leak,
)
from app.services.symbol_call_graph_mapper import (
    ImpactedCaseItem,
    PrecisionImpactAnalysisResult,
)


def test_audit_safe_precision_recommendation():
    # 正常增量精准推荐结果 (推荐了包含对应接口的用例)
    analysis = PrecisionImpactAnalysisResult(
        analysis_id="prec_safe_01",
        changed_symbols=["discount.calculate_discount"],
        impacted_endpoints_count=1,
        impacted_endpoints=["POST /api/v1/orders/checkout"],
        impacted_cases_count=1,
        impacted_cases=[
            ImpactedCaseItem(
                case_id="case_order_checkout_flow",
                case_name="收银台下单流程",
                impacted_by_endpoints=["POST /api/v1/orders/checkout"],
                impacted_by_symbols=["discount.calculate_discount"],
                call_lineage=[],
            )
        ],
        total_cases_in_suite=50,
        regression_reduction_ratio=0.98,
        estimated_time_saved_seconds=490.0,
    )

    report = audit_precision_regression_leak(analysis)
    assert report.verdict == LeakGuardVerdict.ALLOW
    assert report.risk_level == LeakRiskLevel.SAFE
    assert report.safety_score >= 85.0
    assert len(report.compensated_cases) == 0


def test_audit_extreme_pruning_circuit_breaker():
    # 存在代码变动，但由于未映射血缘推荐为 0，且全量套件为 100
    analysis = PrecisionImpactAnalysisResult(
        analysis_id="prec_extreme_02",
        changed_symbols=["unknown_payment_core_handler"],
        impacted_endpoints_count=0,
        impacted_endpoints=[],
        impacted_cases_count=0,
        impacted_cases=[],
        total_cases_in_suite=100,
        regression_reduction_ratio=1.0,
        estimated_time_saved_seconds=1000.0,
    )

    report = audit_precision_regression_leak(analysis)
    assert report.verdict == LeakGuardVerdict.BLOCK
    assert report.risk_level == LeakRiskLevel.CRITICAL
    assert report.safety_score < 60.0
    assert any("高危熔断" in v for v in report.violations)


def test_audit_critical_domain_auto_compensation():
    # 触碰了 auth 关键域，但推荐用例中缺少登录核心基线
    analysis = PrecisionImpactAnalysisResult(
        analysis_id="prec_auth_03",
        changed_symbols=["user_auth_helper"],
        impacted_endpoints_count=1,
        impacted_endpoints=["GET /api/v1/users/info"],
        impacted_cases_count=1,
        impacted_cases=[
            ImpactedCaseItem(
                case_id="case_user_info_query",
                case_name="用户信息查询",
                impacted_by_endpoints=["GET /api/v1/users/info"],
                impacted_by_symbols=["user_auth_helper"],
                call_lineage=[],
            )
        ],
        total_cases_in_suite=50,
        regression_reduction_ratio=0.98,
        estimated_time_saved_seconds=490.0,
    )

    report = audit_precision_regression_leak(analysis, enforce_critical_baseline=True)
    assert report.verdict == LeakGuardVerdict.COMPENSATE_AND_ALLOW
    assert report.risk_level == LeakRiskLevel.WARN
    assert "case_user_login_success" in report.compensated_cases
    assert "case_user_login_success" in report.final_approved_cases
    assert "case_user_info_query" in report.final_approved_cases

    d = report.to_dict()
    assert d["verdict"] == "COMPENSATE_AND_ALLOW"
    assert len(d["compensated_cases"]) >= 1


def test_audit_critical_signature_change_warning():
    sym = ChangedSymbolItem(
        symbol_id="s1",
        file_path="service.py",
        symbol_name="login",
        qualified_name="login",
        symbol_type=SymbolType.FUNCTION,
        change_type=SymbolChangeType.SIGNATURE_CHANGED,
        severity=SymbolChangeSeverity.CRITICAL,
        line_start=1,
        line_end=5,
        touched_lines=[1],
        signature="login(u, p)",
    )

    analysis = PrecisionImpactAnalysisResult(
        analysis_id="prec_sig_04",
        changed_symbols=["login"],
        impacted_endpoints_count=0,
        impacted_endpoints=[],
        impacted_cases_count=0,
        impacted_cases=[],
        total_cases_in_suite=20,
        regression_reduction_ratio=1.0,
        estimated_time_saved_seconds=200.0,
    )

    report = audit_precision_regression_leak(analysis, changed_symbols=[sym])
    assert report.verdict == LeakGuardVerdict.BLOCK
    assert any("函数入参签名核心变动" in v for v in report.violations)
