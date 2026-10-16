"""多可用区单元化 (Cell/Zone) 流量切流与路由策略控制器单元测试 (T2.1)。"""

from __future__ import annotations

import pytest
from app.services.cell_based_testing_traffic_controller import (
    CellStatus,
    clear_cell_registry_store,
    generate_cell_topology_report,
    list_cells,
    register_cell,
    route_request_to_cell,
    update_cell_weights,
)


@pytest.fixture(autouse=True)
def _reset_cell_state():
    clear_cell_registry_store()
    yield
    clear_cell_registry_store()


def test_route_request_to_cell_shadow_and_prod_sharding():
    """测试将影子压测流量定向至专属压测单元，以及正常流量按用户分片分配。"""
    # 1. 影子压测流量 -> 必须路由至 cell_stress_sandbox
    shadow_decision = route_request_to_cell(
        user_id="user_1001",
        is_shadow_traffic=True,
    )
    assert shadow_decision.is_shadow_traffic is True
    assert shadow_decision.assigned_cell_id == "cell_stress_sandbox"
    assert shadow_decision.is_stress_cell is True

    # 2. 正常生产流量 (user_25 -> shard 25 -> cell_east_01 [0..49])
    prod_decision_1 = route_request_to_cell(
        user_id="user_25",
        is_shadow_traffic=False,
    )
    assert prod_decision_1.assigned_cell_id == "cell_east_01"
    assert prod_decision_1.is_stress_cell is False

    # 3. 正常生产流量 (user_75 -> shard 75 -> cell_east_02 [50..99])
    prod_decision_2 = route_request_to_cell(
        user_id="user_75",
        is_shadow_traffic=False,
    )
    assert prod_decision_2.assigned_cell_id == "cell_east_02"
    assert prod_decision_2.is_stress_cell is False


def test_register_cell_and_update_weights():
    """测试动态注册新机房单元、更新流量权重与生成拓扑报告。"""
    # 注册新单元
    cell = register_cell(
        cell_id="cell_dr_beijing",
        cell_name="北京异地容灾单元",
        zone="cn-north-1a",
        traffic_weight=0,
        status=CellStatus.DRAINING,
    )
    assert cell.cell_id == "cell_dr_beijing"

    cells = list_cells()
    assert any(c["cell_id"] == "cell_dr_beijing" for c in cells)

    # 调整权重
    updated = update_cell_weights({"cell_east_01": 80, "cell_east_02": 20})
    east_01 = next(c for c in updated if c["cell_id"] == "cell_east_01")
    assert east_01["traffic_weight"] == 80

    # 生成拓扑报告
    report = generate_cell_topology_report()
    assert report.total_cells_count >= 4
    assert report.active_prod_cells == 2
    assert report.stress_cells_count == 1
    assert report.isolated_cells_count >= 1
