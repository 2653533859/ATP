"""接口-函数-用例三维调用链拓扑映射引擎单测 (T1.2)"""

from __future__ import annotations

from app.services.symbol_call_graph_mapper import (
    SymbolCallGraph,
    get_global_call_graph,
)


def test_seed_lineage_and_registration():
    graph = SymbolCallGraph()

    # 自定义注册新领域调用
    graph.register_symbol_endpoint("PaymentService.pay", "POST /api/v1/payments/pay")
    graph.register_endpoint_case("POST /api/v1/payments/pay", "case_pay_wechat", "微信支付集成用例", 12.0, "P0")

    assert "POST /api/v1/payments/pay" in graph.symbol_to_endpoints["PaymentService.pay"]
    assert "case_pay_wechat" in graph.endpoint_to_cases["POST /api/v1/payments/pay"]


def test_trace_impacted_cases_discount_symbol():
    graph = get_global_call_graph()

    # 当 discount.calculate_discount 发生变更
    res = graph.trace_impacted_cases(["calculate_discount"], total_suite_size=100)

    assert res.impacted_endpoints_count == 2
    assert "POST /api/v1/orders/checkout" in res.impacted_endpoints
    assert "GET /api/v1/discounts/preview" in res.impacted_endpoints

    assert res.impacted_cases_count == 3
    case_ids = [c.case_id for c in res.impacted_cases]
    assert "case_order_checkout_flow" in case_ids
    assert "case_order_zero_discount" in case_ids
    assert "case_discount_preview_vip" in case_ids

    # 查验调用血缘溯源链
    lineages = res.impacted_cases[0].call_lineage
    assert len(lineages) > 0
    assert "calculate_discount" in lineages[0]
    assert "➔" in lineages[0]

    # 裁剪率 100 - 3 = 97%
    assert res.regression_reduction_ratio == 0.97
    assert res.estimated_time_saved_seconds == 970.0


def test_trace_impacted_cases_user_login():
    graph = get_global_call_graph()

    res = graph.trace_impacted_cases(["UserService.authenticate"], total_suite_size=50)
    assert res.impacted_endpoints_count == 1
    assert "POST /api/v1/users/login" in res.impacted_endpoints

    case_ids = [c.case_id for c in res.impacted_cases]
    assert "case_user_login_success" in case_ids
    assert "case_user_login_invalid_pwd" in case_ids


def test_reverse_case_symbol_coverage():
    graph = get_global_call_graph()

    cov = graph.trace_case_symbol_coverage("case_user_login_success")
    assert cov["case_id"] == "case_user_login_success"
    assert "POST /api/v1/users/login" in cov["covered_endpoints"]
    assert "UserService.authenticate" in cov["covered_symbols"]
    assert "token_service.generate_jwt" in cov["covered_symbols"]


def test_serialization():
    graph = get_global_call_graph()
    res = graph.trace_impacted_cases(["UserService.get_profile"], total_suite_size=20)
    d = res.to_dict()
    assert d["analysis_id"].startswith("prec_")
    assert d["impacted_cases_count"] == 1
    assert d["impacted_cases"][0]["case_id"] == "case_user_profile_query"
