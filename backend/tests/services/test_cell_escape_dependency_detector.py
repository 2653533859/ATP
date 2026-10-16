"""跨单元服务依赖逃逸与拓扑孤岛检测器单元测试 (T2.2)。"""

from __future__ import annotations

import pytest
from app.services.cell_escape_dependency_detector import (
    EscapeViolationType,
    clear_cell_escape_store,
    detect_cell_escapes,
    get_cell_escape_report,
    list_cell_escape_reports,
)


@pytest.fixture(autouse=True)
def _reset_cell_escape_state():
    clear_cell_escape_store()
    yield
    clear_cell_escape_store()


def test_detect_cell_escapes_violations():
    """测试探测影子流量逃逸、跨单元 RPC 调用与混用共享数据源。"""
    edges = [
        # 1. 影子压测流量从压测单元逃逸到生产单元 (CRITICAL)
        {
            "source_cell_id": "cell_stress_sandbox",
            "source_service": "stress_generator",
            "target_cell_id": "cell_east_prod_01",
            "target_service": "order_service",
            "target_resource_type": "MICROSERVICE_RPC",
            "is_shadow_traffic": True,
        },
        # 2. 正常生产跨单元直接 RPC 调用 (HIGH)
        {
            "source_cell_id": "cell_east_prod_01",
            "source_service": "order_service",
            "target_cell_id": "cell_east_prod_02",
            "target_service": "user_service",
            "target_resource_type": "MICROSERVICE_RPC",
            "is_shadow_traffic": False,
        },
        # 3. 混用共享未隔离全局数据库 (HIGH)
        {
            "source_cell_id": "cell_east_prod_01",
            "source_service": "order_service",
            "target_cell_id": "cell_global",
            "target_service": "shared_mysql_master",
            "target_resource_type": "DATABASE",
            "is_shared_resource": True,
        },
        # 4. 单元内正常自包含调用 -> 绝无逃逸
        {
            "source_cell_id": "cell_east_prod_01",
            "source_service": "order_service",
            "target_cell_id": "cell_east_prod_01",
            "target_service": "payment_service",
            "target_resource_type": "MICROSERVICE_RPC",
        },
    ]

    report = detect_cell_escapes(topology_name="banking_cell_mesh", invocation_edges=edges)

    assert report.total_edges_checked == 4
    assert report.total_escapes_count == 3
    assert report.shadow_escapes_count == 1
    assert report.is_strictly_cell_isolated is False
    assert report.isolation_purity_score_pct < 50.0

    v_types = {v.violation_type for v in report.violations}
    assert EscapeViolationType.SHADOW_TRAFFIC_ESCAPE in v_types
    assert EscapeViolationType.CROSS_CELL_RPC_ESCAPE in v_types
    assert EscapeViolationType.SHARED_RESOURCE_CONTAMINATION in v_types

    saved = get_cell_escape_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_cell_escape_reports()) == 1


def test_detect_cell_escapes_strictly_isolated():
    """测试完全严格单元化闭环拓扑。"""
    edges = [
        {
            "source_cell_id": "cell_east_01",
            "source_service": "gateway",
            "target_cell_id": "cell_east_01",
            "target_service": "order_svc",
        },
        {
            "source_cell_id": "cell_east_01",
            "source_service": "order_svc",
            "target_cell_id": "cell_east_01",
            "target_service": "cell_db",
            "target_resource_type": "DATABASE",
        },
    ]

    report = detect_cell_escapes(topology_name="clean_isolated_cell", invocation_edges=edges)
    assert report.total_escapes_count == 0
    assert report.isolation_purity_score_pct == 100.0
    assert report.is_strictly_cell_isolated is True
