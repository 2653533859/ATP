"""全链路流量染色标规则配置与上下文透传器单测 (T1.1)"""

from __future__ import annotations

import pytest

from app.services.canary_traffic_coloration_engine import (
    CanaryColorationRule,
    ColorationRuleType,
    get_global_canary_manager,
    hash_modulo_100,
)


@pytest.fixture(autouse=True)
def setup_canary_mgr():
    mgr = get_global_canary_manager()
    mgr.clear()
    mgr._load_seed_rules()
    yield
    mgr.clear()
    mgr._load_seed_rules()


def test_hash_modulo_100_consistency():
    val_1 = hash_modulo_100("user_alice_101")
    val_2 = hash_modulo_100("user_alice_101")
    assert val_1 == val_2
    assert 0 <= val_1 < 100


def test_header_coloration_matching():
    mgr = get_global_canary_manager()

    ctx_hit = mgr.evaluate_traffic_coloration(
        headers={"x-canary": "true"},
        target_service="payment-service",
    )
    assert ctx_hit.is_canary is True
    assert ctx_hit.color_tag == "v2.1.0-canary"
    assert ctx_hit.matched_by == ColorationRuleType.HTTP_HEADER
    assert ctx_hit.headers_to_propagate["X-Canary-Traffic"] == "true"
    assert "canary.version" in ctx_hit.baggage_items

    # 错误 Header 不命中
    ctx_miss = mgr.evaluate_traffic_coloration(
        headers={"x-canary": "false"},
        target_service="payment-service",
    )
    assert ctx_miss.is_canary is False
    assert ctx_miss.color_tag == "baseline"


def test_tenant_whitelist_coloration():
    mgr = get_global_canary_manager()
    rule = CanaryColorationRule(
        rule_id="crule_vip_tenant",
        name="大客户阿里特批金丝雀通道",
        rule_type=ColorationRuleType.TENANT_WHITELIST,
        target_service="order-service",
        canary_version_tag="v3.1.0-canary",
        match_value="tenant_alipay_corp",
        is_enabled=True,
    )
    mgr.add_rule(rule)

    ctx_vip = mgr.evaluate_traffic_coloration(
        tenant_id="tenant_alipay_corp",
        target_service="order-service",
    )
    assert ctx_vip.is_canary is True
    assert ctx_vip.color_tag == "v3.1.0-canary"
    assert ctx_vip.matched_by == ColorationRuleType.TENANT_WHITELIST

    ctx_normal = mgr.evaluate_traffic_coloration(
        tenant_id="tenant_normal_guest",
        target_service="order-service",
        random_roll=99.0,
    )
    assert ctx_normal.is_canary is False


def test_user_modulo_coloration():
    mgr = get_global_canary_manager()
    rule = CanaryColorationRule(
        rule_id="crule_user_hash",
        name="用户哈希取模 20% 分流",
        rule_type=ColorationRuleType.USER_MODULO,
        target_service="auth-service",
        canary_version_tag="v2.5.0-auth",
        weight_pct=20.0,
        is_enabled=True,
    )
    mgr.add_rule(rule)

    # 构造一个取模 slot < 20 的用户
    target_user = "user_test_small"
    while hash_modulo_100(target_user) >= 20:
        target_user += "_x"

    ctx_hit = mgr.evaluate_traffic_coloration(
        user_id=target_user,
        target_service="auth-service",
    )
    assert ctx_hit.is_canary is True
    assert ctx_hit.matched_by == ColorationRuleType.USER_MODULO


def test_weight_random_coloration():
    mgr = get_global_canary_manager()

    # 10% 权重规则: 传入 roll = 5.0 <= 10.0 -> 命中
    ctx_hit = mgr.evaluate_traffic_coloration(
        target_service="order-service",
        random_roll=5.0,
    )
    assert ctx_hit.is_canary is True
    assert ctx_hit.matched_by == ColorationRuleType.WEIGHT_RANDOM

    # 传入 roll = 15.0 > 10.0 -> 不命中
    ctx_miss = mgr.evaluate_traffic_coloration(
        target_service="order-service",
        random_roll=15.0,
    )
    assert ctx_miss.is_canary is False


def test_rules_crud_and_to_dict():
    mgr = get_global_canary_manager()
    initial_len = len(mgr.list_rules())
    assert initial_len >= 2

    r_new = CanaryColorationRule(
        rule_id="crule_temp_01",
        name="临时测试规则",
        rule_type=ColorationRuleType.COOKIE_PARAM,
        target_service="web-service",
        canary_version_tag="v1.9",
        match_key="beta_cookie",
        match_value="1",
    )
    mgr.add_rule(r_new)
    assert mgr.get_rule("crule_temp_01") is not None
    assert len(mgr.list_rules(target_service="web-service")) == 1

    d = r_new.to_dict()
    assert d["rule_id"] == "crule_temp_01"
    assert d["rule_type"] == "COOKIE_PARAM"

    assert mgr.delete_rule("crule_temp_01") is True
    assert mgr.get_rule("crule_temp_01") is None
