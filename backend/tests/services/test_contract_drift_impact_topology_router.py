"""Unit tests for Contract Drift Impact Topology Router Service (T3.3)."""

from __future__ import annotations

import pytest

from app.services.contract_drift_impact_topology_router import (
    BlastRadiusLevel,
    ImpactTier,
    analyze_contract_drift_impact,
    clear_topology_and_reports,
    get_impact_analysis_report,
    get_service_topology,
    list_impact_analysis_reports,
    register_service_dependency,
    register_service_node,
)


@pytest.fixture(autouse=True)
def clean_topology():
    clear_topology_and_reports()
    yield
    clear_topology_and_reports()


def test_default_topology_initialized():
    """验证出厂默认微服务节点与依赖调用边正确初始化。"""
    topo = get_service_topology()
    assert topo["services_count"] >= 5
    assert topo["dependencies_count"] >= 4

    # 包含 order-service 与 payment-service
    service_ids = [n["service_id"] for n in topo["nodes"]]
    assert "order-service" in service_ids
    assert "payment-service" in service_ids


def test_analyze_contract_drift_impact_direct_and_transitive():
    """验证当订单接口发生破损时，精准定位直接受损服务与级联下游服务。"""
    # 破坏字段: amount (支付中心与大数据中台直接消费)
    report = analyze_contract_drift_impact(
        endpoint="POST /api/v1/orders/checkout",
        broken_fields=["amount"],
        dispatch_alerts=True,
    )

    assert report.total_impacted_services >= 2
    assert report.direct_services_count >= 2
    assert report.blast_radius_level in (BlastRadiusLevel.CRITICAL, BlastRadiusLevel.HIGH)

    direct_svc_ids = [s.service_id for s in report.impacted_services if s.impact_tier == ImpactTier.DIRECT]
    assert "payment-service" in direct_svc_ids  # 直接依赖 amount 发生破坏

    # 验证级联多跳波及: notification-service 依赖了 payment-service
    transitive_svc_ids = [s.service_id for s in report.impacted_services if s.impact_tier == ImpactTier.TRANSITIVE]
    assert "notification-service" in transitive_svc_ids

    # 验证安全告警自动路由派发
    assert len(report.dispatched_alerts) == report.total_impacted_services
    pay_alert = next(a for a in report.dispatched_alerts if a.target_service_id == "payment-service")
    assert pay_alert.status == "SENT"
    assert pay_alert.recipient == "dev-bob"


def test_analyze_contract_drift_zero_impact():
    """验证当破损字段未被任何下游消费时，爆炸半径为 LOW 且 0 受损。"""
    # 假设破损了一个从未被下游引用的无用参数
    report = analyze_contract_drift_impact(
        endpoint="POST /api/v1/orders/checkout",
        broken_fields=["completely_unused_legacy_arg"],
        dispatch_alerts=False,
    )

    assert report.total_impacted_services == 0
    assert report.blast_radius_score == 0.0
    assert report.blast_radius_level == BlastRadiusLevel.LOW
    assert "未命中任何下游消费字段" in report.verdict_summary


def test_register_custom_service_and_dependency():
    """验证动态注册新微服务与依赖边，并能够参与级联影响分析。"""
    register_service_node(
        service_id="crm-service",
        service_name="客户关系管理系统",
        owner="dev-grace",
        notification_webhook="https://hook.corp.com/crm",
        is_critical_asset=True,
    )

    register_service_dependency(
        consumer_service_id="crm-service",
        producer_service_id="order-service",
        endpoint="POST /api/v1/orders/checkout",
        consumed_fields=["vip_level", "discount_quota"],
        call_frequency="MEDIUM",
    )

    report = analyze_contract_drift_impact(
        endpoint="POST /api/v1/orders/checkout",
        broken_fields=["discount_quota"],
        dispatch_alerts=True,
    )

    impacted_ids = [s.service_id for s in report.impacted_services]
    assert "crm-service" in impacted_ids

    # 验证报告持久化
    fetched = get_impact_analysis_report(report.analysis_id)
    assert fetched is not None
    assert fetched.analysis_id == report.analysis_id
    assert len(list_impact_analysis_reports()) == 1
