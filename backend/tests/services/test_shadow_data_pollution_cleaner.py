"""影子数据隔离防污染巡检与影子库表清理器单测 (T2.3)"""

from __future__ import annotations

from app.services.shadow_data_pollution_cleaner import (
    ShadowTargetType,
    execute_shadow_data_clean,
    is_safe_shadow_resource,
    scan_shadow_resources,
)


def test_is_safe_shadow_resource():
    # 1. 合法影子存储特征
    assert is_safe_shadow_resource("t_order_shadow") is True
    assert is_safe_shadow_resource("t_payment_stress") is True
    assert is_safe_shadow_resource("shadow:order:cache") is True
    assert is_safe_shadow_resource("topic_cart_shadow") is True

    # 2. 生产主库核心主表严格拦截拒绝
    assert is_safe_shadow_resource("t_order") is False
    assert is_safe_shadow_resource("t_account_balance") is False
    assert is_safe_shadow_resource("t_payment_record") is False
    assert is_safe_shadow_resource("t_users") is False

    # 3. 未知未标明影子后缀的普通表拦截
    assert is_safe_shadow_resource("t_unmarked_table") is False


def test_scan_shadow_resources_seed():
    items = scan_shadow_resources(target_service="order-service")
    assert len(items) == 4
    assert any(i.resource_name == "t_order_shadow" for i in items)
    assert any(i.target_type == ShadowTargetType.SHADOW_REDIS_NAMESPACE for i in items)
    assert all(i.is_legitimate_shadow is True for i in items)


def test_scan_shadow_resources_custom():
    custom = [
        {
            "resource_name": "t_custom_shadow",
            "target_type": "SHADOW_TABLE",
            "estimated_records_count": 5000,
            "estimated_size_mb": 12.0,
        },
        {
            "resource_name": "t_dangerous_master",  # 生产表
            "target_type": "SHADOW_TABLE",
            "estimated_records_count": 100000,
            "estimated_size_mb": 500.0,
        },
    ]

    items = scan_shadow_resources(target_service="custom-service", custom_resources=custom)
    assert len(items) == 2
    assert items[0].is_legitimate_shadow is True
    assert items[1].is_legitimate_shadow is False


def test_execute_shadow_data_clean_dry_run_and_actual():
    # 1. 试运行预演 (Dry Run)
    targets = ["t_order_shadow", "shadow:cart:cache"]
    rep_dry = execute_shadow_data_clean(targets, is_dry_run=True, target_service="order-service")

    assert rep_dry.is_dry_run is True
    assert rep_dry.cleaned_resources_count == 2
    assert rep_dry.total_purged_records == 170000  # 125000 + 45000
    assert rep_dry.reclaimed_space_mb > 200.0
    assert len(rep_dry.rejected_attempts) == 0
    assert rep_dry.purged_details[0]["status"] == "DRY_RUN_SIMULATED"

    # 2. 真实安全清理
    rep_actual = execute_shadow_data_clean(targets, is_dry_run=False, target_service="order-service")
    assert rep_actual.is_dry_run is False
    assert rep_actual.purged_details[0]["status"] == "PURGED_SUCCESS"


def test_execute_shadow_data_clean_rejects_master_table():
    # 试图对真实生产主表执行清空，必须被绝对拦截！
    dangerous_targets = ["t_order_shadow", "t_order", "t_account_balance"]
    rep = execute_shadow_data_clean(dangerous_targets, is_dry_run=False, target_service="order-service")

    assert rep.cleaned_resources_count == 1  # 仅 t_order_shadow 准予清理
    assert len(rep.rejected_attempts) == 2
    assert any("t_order" in r for r in rep.rejected_attempts)
    assert any("t_account_balance" in r for r in rep.rejected_attempts)

    d = rep.to_dict()
    assert d["cleaned_resources_count"] == 1
    assert len(d["rejected_attempts"]) == 2
