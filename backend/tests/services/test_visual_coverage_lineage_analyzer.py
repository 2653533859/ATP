"""业务分支与契约多维漏测血缘分析器单测 (T2.1)"""

from __future__ import annotations

import pytest

from app.services.visual_coverage_lineage_analyzer import (
    CoverageLineageEdge,
    CoverageLineageNode,
    CoverageRiskLevel,
    LineageCategory,
    analyze_coverage_lineage,
    clear_coverage_reports,
    get_coverage_report,
    list_coverage_reports,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_coverage_reports()
    yield
    clear_coverage_reports()


def test_analyze_coverage_lineage_gaps_and_hierarchy():
    # 1. 构造血缘节点: 需求 -> 接口 -> 分支
    node_req = CoverageLineageNode(
        node_id="req_checkout",
        node_name="电商结账业务需求",
        category=LineageCategory.REQUIREMENT,
        expected_branches=["normal_pay", "insufficient_balance", "coupon_discount"],
        covered_branches=["normal_pay", "coupon_discount"],
    )
    node_api = CoverageLineageNode(
        node_id="api_pay_order",
        node_name="POST /api/v1/pay/order 接口契约",
        category=LineageCategory.API_ENDPOINT,
        expected_branches=["HTTP_200", "HTTP_400_PARAM", "HTTP_504_TIMEOUT"],
        covered_branches=["HTTP_200"],  # 缺失 2 个异常分支，其中包含 TIMEOUT
    )
    node_branch = CoverageLineageNode(
        node_id="branch_inventory",
        node_name="扣减库存失败重试分支",
        category=LineageCategory.BUSINESS_BRANCH,
        expected_branches=["retry_success", "retry_exhausted_rollback"],
        covered_branches=[],  # 覆盖率为 0，且包含 rollback 异常关键词
    )

    edges = [
        CoverageLineageEdge("e1", "req_checkout", "api_pay_order", "implements"),
        CoverageLineageEdge("e2", "api_pay_order", "branch_inventory", "triggers"),
    ]

    report = analyze_coverage_lineage("proj_ecommerce", [node_req, node_api, node_branch], edges)

    assert report.total_nodes_count == 3
    assert report.gap_nodes_count == 3  # 三个节点均存在未覆盖分支
    assert report.high_risk_gaps_count >= 2  # api_pay_order (TIMEOUT) 与 branch_inventory 应评定为 HIGH 风险

    # 查验各节点指标
    node_map = {n.node_id: n for n in report.nodes}
    assert node_map["req_checkout"].missing_branches == ["insufficient_balance"]
    assert "HTTP_504_TIMEOUT" in node_map["api_pay_order"].missing_branches
    assert node_map["api_pay_order"].risk_level == CoverageRiskLevel.HIGH
    assert node_map["branch_inventory"].coverage_rate == 0.0

    # 查验层级树结构
    assert len(report.tree_hierarchy) == 1
    root = report.tree_hierarchy[0]
    assert root["node_id"] == "req_checkout"
    assert len(root["children"]) == 1
    assert root["children"][0]["node_id"] == "api_pay_order"
    assert root["children"][0]["children"][0]["node_id"] == "branch_inventory"

    # 查验存储与查询
    assert get_coverage_report(report.report_id) is not None
    assert len(list_coverage_reports()) == 1
