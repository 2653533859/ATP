"""页面内存泄漏与 DOM 节点脱落幽灵引用诊断器单元测试 (T4.2)。"""

from __future__ import annotations

import pytest
from app.services.client_memory_leak_dom_detachment_detector import (
    MemoryLeakType,
    clear_memory_leak_store,
    diagnose_memory_leak_and_detachment,
    get_memory_leak_report,
    list_memory_leak_reports,
)


@pytest.fixture(autouse=True)
def _reset_memory_leak_state():
    clear_memory_leak_store()
    yield
    clear_memory_leak_store()


def test_diagnose_memory_leak_and_detachment_detect_leaks():
    """测试探测堆持续增长 (>20%)、脱落 DOM 节点以及未释放事件监听器。"""
    snapshots = [
        {"js_heap_used_bytes": 10_000_000, "event_listener_count": 10, "detached_dom_node_count": 0},
        {"js_heap_used_bytes": 12_000_000, "event_listener_count": 13, "detached_dom_node_count": 5},
        {"js_heap_used_bytes": 14_000_000, "event_listener_count": 18, "detached_dom_node_count": 12},
    ]

    detached_nodes = [
        {
            "node_id": "div_chart_container",
            "tag_name": "div",
            "retained_size_bytes": 1048576,
            "retaining_closure": "echartsInstances.map",
            "description": "Detached chart root",
        }
    ]

    report = diagnose_memory_leak_and_detachment(
        page_or_scenario="dashboard_refresh_loop",
        snapshots=snapshots,
        detached_nodes=detached_nodes,
    )

    assert report.initial_heap_bytes == 10_000_000
    assert report.final_heap_bytes == 14_000_000
    assert report.heap_growth_percentage == 40.0  # +40% 阶梯攀升
    assert report.has_critical_leak is True
    assert report.total_unreleased_listeners_count == 8  # 18 - 10 = 8

    leak_types = {f.leak_type for f in report.findings}
    assert MemoryLeakType.PROGRESSIVE_HEAP_LEAK in leak_types
    assert MemoryLeakType.DETACHED_DOM_TREE_LEAK in leak_types
    assert MemoryLeakType.UNRELEASED_EVENT_LISTENER_LEAK in leak_types

    assert len(report.detached_nodes_sample) == 1
    assert report.detached_nodes_sample[0].node_id == "div_chart_container"


def test_diagnose_memory_leak_clean_scenario():
    """测试完全释放无内存泄漏的健康场景。"""
    snapshots = [
        {"js_heap_used_bytes": 10_000_000, "event_listener_count": 10, "detached_dom_node_count": 0},
        {"js_heap_used_bytes": 10_200_000, "event_listener_count": 10, "detached_dom_node_count": 0},
        {"js_heap_used_bytes": 9_900_000, "event_listener_count": 10, "detached_dom_node_count": 0},
    ]

    report = diagnose_memory_leak_and_detachment(
        page_or_scenario="clean_view",
        snapshots=snapshots,
        detached_nodes=[],
    )

    assert report.has_critical_leak is False
    assert report.memory_health_score_pct == 100.0
    assert len(report.findings) == 0

    saved = get_memory_leak_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_memory_leak_reports()) == 1
