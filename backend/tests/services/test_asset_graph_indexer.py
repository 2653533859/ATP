"""Unit tests for C2.1 Global Test Asset Full-Scope Dependency Graph & Reverse Indexer.

Tests:
1. Directed graph node and edge indexing across Plan -> Suite -> Case -> API Endpoint
2. get_upstream_consumers resolves full reverse lineage (Case -> Suites -> Plans)
3. get_downstream_dependencies resolves forward dependencies (Plan -> Suites -> Cases -> APIs)
4. find_orphan_assets detects unreferenced cases and unused datasets
5. export_project_subgraph produces formatted graph nodes, edges, and distribution stats
"""

from __future__ import annotations

import pytest

from app.services.asset_graph_indexer import (
    AssetGraphIndexer,
    AssetType,
    RelationType,
)


@pytest.fixture
def indexer():
    idx = AssetGraphIndexer()
    # Build sample multi-tier asset hierarchy for Project 1:
    # Plan 1 -> Suite 10 -> Case 101 -> API "POST /api/v1/orders"
    # Plan 1 -> Suite 10 -> Case 102 -> API "GET /api/v1/orders/status"
    # Suite 10 is driven by Dataset 501
    idx.add_node(AssetType.PLAN, 1, "全链路发版回归计划", project_id=1)
    idx.add_node(AssetType.SUITE, 10, "订单主流程自动化套件", project_id=1)
    idx.add_node(AssetType.CASE, 101, "提交订单并校验库存", project_id=1)
    idx.add_node(AssetType.CASE, 102, "查询订单状态流转", project_id=1)
    idx.add_node(AssetType.API_ENDPOINT, "POST /api/v1/orders", "POST /api/v1/orders", project_id=1)
    idx.add_node(AssetType.API_ENDPOINT, "GET /api/v1/orders/status", "GET /api/v1/orders/status", project_id=1)
    idx.add_node(AssetType.DATASET, 501, "商品SKU参数化数据集", project_id=1)

    # Orphan assets in Project 1:
    idx.add_node(AssetType.CASE, 999, "未被套件引用的孤儿测试用例", project_id=1)
    idx.add_node(AssetType.DATASET, 998, "未被引用的冗余历史数据集", project_id=1)

    # Wire edges:
    idx.add_edge(AssetType.PLAN, 1, AssetType.SUITE, 10, RelationType.CONTAINS)
    idx.add_edge(AssetType.SUITE, 10, AssetType.CASE, 101, RelationType.CONTAINS)
    idx.add_edge(AssetType.SUITE, 10, AssetType.CASE, 102, RelationType.CONTAINS)
    idx.add_edge(AssetType.SUITE, 10, AssetType.DATASET, 501, RelationType.DRIVEN_BY_DATASET)
    idx.add_edge(AssetType.CASE, 101, AssetType.API_ENDPOINT, "POST /api/v1/orders", RelationType.CALLS_API)
    idx.add_edge(AssetType.CASE, 102, AssetType.API_ENDPOINT, "GET /api/v1/orders/status", RelationType.CALLS_API)

    return idx


def test_asset_graph_indexing_and_node_lookup(indexer: AssetGraphIndexer):
    assert len(indexer.nodes) == 9
    case_node = indexer.nodes.get("case:101")
    assert case_node is not None
    assert case_node.name == "提交订单并校验库存"
    assert case_node.asset_type == AssetType.CASE


def test_get_upstream_consumers_reverse_lineage(indexer: AssetGraphIndexer):
    # Query upstream consumers of Case 101 -> should find Suite 10 (depth 1) and Plan 1 (depth 2)
    consumers = indexer.get_upstream_consumers(AssetType.CASE, 101)
    assert len(consumers) == 2

    node_ids = [c["node"]["node_id"] for c in consumers]
    assert "suite:10" in node_ids
    assert "plan:1" in node_ids

    # Check depth
    suite_consumer = [c for c in consumers if c["node"]["node_id"] == "suite:10"][0]
    assert suite_consumer["depth"] == 1
    plan_consumer = [c for c in consumers if c["node"]["node_id"] == "plan:1"][0]
    assert plan_consumer["depth"] == 2


def test_get_downstream_dependencies_forward_lineage(indexer: AssetGraphIndexer):
    # Query downstream dependencies of Plan 1 -> should find Suite 10, Cases 101 & 102, Dataset 501, and APIs
    deps = indexer.get_downstream_dependencies(AssetType.PLAN, 1)
    dep_node_ids = [d["node"]["node_id"] for d in deps]

    assert "suite:10" in dep_node_ids
    assert "case:101" in dep_node_ids
    assert "case:102" in dep_node_ids
    assert "dataset:501" in dep_node_ids
    assert "api_endpoint:POST /api/v1/orders" in dep_node_ids


def test_find_orphan_assets(indexer: AssetGraphIndexer):
    orphans = indexer.find_orphan_assets(project_id=1)
    assert orphans["total_orphans_count"] >= 2

    orphan_case_ids = [c["asset_id"] for c in orphans["orphan_cases"]]
    assert 999 in orphan_case_ids
    assert 101 not in orphan_case_ids  # Case 101 is consumed by Suite 10

    orphan_dataset_ids = [d["asset_id"] for d in orphans["orphan_datasets"]]
    assert 998 in orphan_dataset_ids
    assert 501 not in orphan_dataset_ids  # Dataset 501 is consumed by Suite 10


def test_export_project_subgraph(indexer: AssetGraphIndexer):
    subgraph = indexer.export_project_subgraph(project_id=1)
    assert subgraph["project_id"] == 1
    assert subgraph["total_nodes"] == 9
    assert subgraph["total_edges"] == 6

    dist = subgraph["asset_distribution"]
    assert dist["plans"] == 1
    assert dist["suites"] == 1
    assert dist["cases"] == 3  # 101, 102, 999
    assert dist["datasets"] == 2  # 501, 998
    assert dist["api_endpoints"] == 2

    # Check orphan section in export
    assert subgraph["orphans"]["total_orphans_count"] >= 2
