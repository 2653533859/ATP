"""Unit tests for C2.2 API Contract Change Impact Analysis & Reverse Case Attribution.

Tests:
1. Breaking contract schema change detects breaking impact and reverse-traces affected cases
2. Non-breaking additive schema change flags warning level without breaking status
3. Identical compatible schema produces compatible status with no impact
4. Project-level boundary filtering isolates cases belonging to requested project
"""

from __future__ import annotations

import pytest

from app.services.asset_graph_indexer import (
    AssetType,
    RelationType,
    get_global_asset_indexer,
)
from app.services.contract_change_impact_analyzer import (
    analyze_contract_change_impact,
)


@pytest.fixture(autouse=True)
def setup_asset_graph():
    indexer = get_global_asset_indexer()
    indexer.clear()

    # Index: Plan 1 -> Suite 10 -> Case 101 -> API "POST /api/v1/orders"
    indexer.add_node(AssetType.PLAN, 1, "全链路回归计划", project_id=1)
    indexer.add_node(AssetType.SUITE, 10, "订单主流程套件", project_id=1)
    indexer.add_node(AssetType.CASE, 101, "提交订单核心用例", project_id=1)
    indexer.add_node(AssetType.API_ENDPOINT, "POST /api/v1/orders", "POST /api/v1/orders", project_id=1)

    indexer.add_edge(AssetType.PLAN, 1, AssetType.SUITE, 10, RelationType.CONTAINS)
    indexer.add_edge(AssetType.SUITE, 10, AssetType.CASE, 101, RelationType.CONTAINS)
    indexer.add_edge(AssetType.CASE, 101, AssetType.API_ENDPOINT, "POST /api/v1/orders", RelationType.CALLS_API)

    # Cross-project case in Project 2 also calling same API
    indexer.add_node(AssetType.CASE, 201, "外部租户测试用例", project_id=2)
    indexer.add_edge(AssetType.CASE, 201, AssetType.API_ENDPOINT, "POST /api/v1/orders", RelationType.CALLS_API)

    yield
    indexer.clear()


def test_breaking_contract_change_impact():
    # Baseline schema has required field 'order_id'
    baseline = {
        "type": "object",
        "required": ["order_id", "amount"],
        "properties": {
            "order_id": {"type": "string"},
            "amount": {"type": "number"},
        },
    }

    # Current schema removed required field 'order_id' (Breaking Change)
    current = {
        "type": "object",
        "required": ["amount"],
        "properties": {
            "amount": {"type": "number"},
        },
    }

    report = analyze_contract_change_impact(
        method="POST",
        path="/api/v1/orders",
        baseline_schema=baseline,
        current_schema=current,
        project_id=1,
    )

    assert report.endpoint == "POST /api/v1/orders"
    assert report.is_breaking is True
    assert len(report.breaking_changes) >= 1
    assert report.total_impacted_cases_count == 1
    assert report.total_impacted_suites_count == 1
    assert report.total_impacted_plans_count == 1

    impacted_case = report.impacted_cases[0]
    assert impacted_case.case_id == 101
    assert impacted_case.case_name == "提交订单核心用例"
    assert impacted_case.impact_level == "breaking"
    assert "破坏性变更" in impacted_case.reason
    assert "紧急建议" in report.recommended_action


def test_non_breaking_warning_contract_change():
    baseline = {
        "type": "object",
        "properties": {
            "amount": {"type": "number"},
        },
    }

    # Additive optional property
    current = {
        "type": "object",
        "properties": {
            "amount": {"type": "number"},
            "coupon_code": {"type": "string"},
        },
    }

    report = analyze_contract_change_impact(
        method="POST",
        path="/api/v1/orders",
        baseline_schema=baseline,
        current_schema=current,
        project_id=1,
    )

    assert report.is_breaking is False
    assert report.total_impacted_cases_count == 1
    assert report.impacted_cases[0].impact_level in {"warning", "compatible"}


def test_identical_compatible_contract_change():
    schema = {
        "type": "object",
        "properties": {
            "amount": {"type": "number"},
        },
    }

    report = analyze_contract_change_impact(
        method="POST",
        path="/api/v1/orders",
        baseline_schema=schema,
        current_schema=schema,
        project_id=1,
    )

    assert report.is_breaking is False
    assert len(report.breaking_changes) == 0
    assert report.impacted_cases[0].impact_level == "compatible"
    assert "完全向后兼容" in report.impacted_cases[0].reason


def test_project_id_boundary_filter():
    # Without project_id filter: should find both Case 101 (Project 1) and Case 201 (Project 2)
    baseline = {"type": "object", "properties": {"a": {"type": "string"}}}
    current = {"type": "object", "properties": {"a": {"type": "integer"}}}  # type change

    report_all = analyze_contract_change_impact(
        method="POST",
        path="/api/v1/orders",
        baseline_schema=baseline,
        current_schema=current,
        project_id=None,
    )
    case_ids_all = [c.case_id for c in report_all.impacted_cases]
    assert 101 in case_ids_all
    assert 201 in case_ids_all

    # With project_id=1 filter: only Case 101 should be returned
    report_proj1 = analyze_contract_change_impact(
        method="POST",
        path="/api/v1/orders",
        baseline_schema=baseline,
        current_schema=current,
        project_id=1,
    )
    case_ids_proj1 = [c.case_id for c in report_proj1.impacted_cases]
    assert 101 in case_ids_proj1
    assert 201 not in case_ids_proj1
