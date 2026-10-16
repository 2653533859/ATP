"""单元化架构测试隔离与流量调度 REST API 集成测试 (T2.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.cell_based_testing_traffic_controller import clear_cell_registry_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_cell_registry_store()
    yield
    app.dependency_overrides.clear()
    clear_cell_registry_store()


def test_cell_isolation_api_flow():
    """测试单元化切流 API 完整链路: 决策路由 -> 注册单元 -> 调整权重 -> 查询拓扑 -> 重置。"""
    client = TestClient(app)

    # 1. 模拟影子流量判定目标单元
    dec_resp = client.post(
        "/api/v1/stress/cell-isolation/routing/decide",
        json={"user_id": "test_user_88", "is_shadow_traffic": True},
        headers=HEADERS,
    )
    assert dec_resp.status_code == 200
    decision = dec_resp.json()["decision"]
    assert decision["assigned_cell_id"] == "cell_stress_sandbox"
    assert decision["is_stress_cell"] is True

    # 2. 注册新单元
    reg_resp = client.post(
        "/api/v1/stress/cell-isolation/routing/cells",
        json={
            "cell_id": "cell_south_01",
            "cell_name": "华南深圳单元",
            "zone": "cn-south-1a",
            "traffic_weight": 30,
            "status": "ACTIVE_PROD",
            "allowed_shards": [10, 11, 12],
        },
        headers=HEADERS,
    )
    assert reg_resp.status_code == 200
    assert reg_resp.json()["cell"]["cell_id"] == "cell_south_01"

    # 3. 查询单元列表
    list_resp = client.get("/api/v1/stress/cell-isolation/routing/cells", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 4

    # 4. 调整权重
    weight_resp = client.post(
        "/api/v1/stress/cell-isolation/routing/weights",
        json={"weights": {"cell_south_01": 50}},
        headers=HEADERS,
    )
    assert weight_resp.status_code == 200

    # 5. 查询全景拓扑报告
    topo_resp = client.get("/api/v1/stress/cell-isolation/routing/topology", headers=HEADERS)
    assert topo_resp.status_code == 200
    assert topo_resp.json()["report"]["total_cells_count"] >= 4

    # 6. 重置仓库
    clear_resp = client.delete("/api/v1/stress/cell-isolation/routing/cells", headers=HEADERS)
    assert clear_resp.status_code == 200
