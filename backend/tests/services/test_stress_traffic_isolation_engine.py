"""全链路影子压测标注入与上下文透传引擎单测 (T1.1)"""

from __future__ import annotations

import pytest

from app.services.stress_traffic_isolation_engine import (
    STRESS_EXECUTION_HEADER,
    STRESS_HTTP_HEADER,
    STRESS_W3C_BAGGAGE_KEY,
    StressIsolationRule,
    StressTrafficRuleType,
    derive_shadow_target,
    get_global_stress_manager,
    inspect_stress_write_safety,
)


@pytest.fixture(autouse=True)
def setup_stress_mgr():
    mgr = get_global_stress_manager()
    mgr.clear()
    mgr._load_seed_rules()
    yield
    mgr.clear()
    mgr._load_seed_rules()


def test_derive_shadow_target():
    # 正常生产表推导为影子表
    assert derive_shadow_target("t_order") == "t_order_shadow"
    assert derive_shadow_target("t_payment_record") == "t_payment_record_shadow"
    assert derive_shadow_target("topic_order_created") == "topic_order_created_shadow"

    # 若已经是影子资源则保持幂等不重复叠加
    assert derive_shadow_target("t_order_shadow") == "t_order_shadow"
    assert derive_shadow_target("db_stress_users") == "db_stress_users"
    assert derive_shadow_target("sandbox_cart") == "sandbox_cart"


def test_inspect_stress_write_safety():
    # 合规影子表安全放行
    safe1, msg1 = inspect_stress_write_safety("t_order_shadow")
    assert safe1 is True
    assert "符合影子存储隔离规范" in msg1
    safe2, msg2 = inspect_stress_write_safety("t_payment_stress")
    assert safe2 is True
    assert "符合影子存储隔离规范" in msg2

    # 致命生产主表穿透拦截
    safe_leak1, msg_leak1 = inspect_stress_write_safety("t_order")
    assert safe_leak1 is False
    assert "致命泄漏" in msg_leak1

    safe_leak2, msg_leak2 = inspect_stress_write_safety("t_account_balance")
    assert safe_leak2 is False
    assert "生产核心主表" in msg_leak2

    # 未知普通表未标明影子表警告
    safe_un, msg_un = inspect_stress_write_safety("t_temp_data")
    assert safe_un is False
    assert "未携带任何合规影子后缀" in msg_un


def test_evaluate_stress_traffic_via_header():
    mgr = get_global_stress_manager()
    headers = {STRESS_HTTP_HEADER: "true"}

    ctx = mgr.evaluate_stress_traffic(
        target_service="order-service",
        path="/v1/order/create",
        headers=headers,
        virtual_user_id="VU-0042",
    )

    assert ctx.is_stress_test is True
    assert ctx.virtual_user_id == "VU-0042"
    assert ctx.headers[STRESS_HTTP_HEADER] == "true"
    assert ctx.headers[STRESS_EXECUTION_HEADER].startswith("st_exec_")
    assert ctx.baggage == STRESS_W3C_BAGGAGE_KEY
    assert ctx.mq_properties["__stress_tag__"] == "true"

    # 验证透传注入到下游请求头
    outgoing = ctx.inject_into_headers({"Authorization": "Bearer token123"})
    assert outgoing["Authorization"] == "Bearer token123"
    assert outgoing[STRESS_HTTP_HEADER] == "true"
    assert outgoing["baggage"] == STRESS_W3C_BAGGAGE_KEY
    assert outgoing["X-Stress-Virtual-User"] == "VU-0042"


def test_evaluate_stress_traffic_via_tenant_rule():
    mgr = get_global_stress_manager()
    rule = StressIsolationRule(
        rule_id="r_tenant_01",
        name="压测专用租户全量加压",
        rule_type=StressTrafficRuleType.TENANT_STRESS,
        target_service="user-service",
        tenant_id="perf-stress-tenant-99",
    )
    mgr.add_rule(rule)

    # 匹配租户
    ctx_matched = mgr.evaluate_stress_traffic(
        target_service="user-service",
        tenant_id="perf-stress-tenant-99",
    )
    assert ctx_matched.is_stress_test is True

    # 不匹配租户
    ctx_unmatched = mgr.evaluate_stress_traffic(
        target_service="user-service",
        tenant_id="normal-tenant-01",
    )
    assert ctx_unmatched.is_stress_test is False


def test_stress_rule_manager_crud():
    mgr = get_global_stress_manager()
    initial_count = len(mgr.list_rules())

    rule = StressIsolationRule(
        rule_id="r_crud_01",
        name="购物车压测规则",
        rule_type=StressTrafficRuleType.URL_PATH_MATCH,
        target_service="cart-service",
        target_path_pattern="/cart/add.*",
    )
    mgr.add_rule(rule)
    assert len(mgr.list_rules()) == initial_count + 1
    assert mgr.get_rule("r_crud_01") == rule

    assert len(mgr.list_rules(target_service="cart-service")) == 1
    assert len(mgr.list_rules(target_service="non-existent")) == 0

    assert mgr.delete_rule("r_crud_01") is True
    assert mgr.get_rule("r_crud_01") is None
    assert mgr.delete_rule("non_existent") is False
