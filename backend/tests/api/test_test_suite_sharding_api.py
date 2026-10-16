"""大规模测试套件智能动态分片 REST API 集成测试 (T1.2)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.test_suite_dynamic_sharding_scheduler import clear_sharding_plans

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_sharding_plans()
    yield
    app.dependency_overrides.clear()
    clear_sharding_plans()


def test_sharding_api_calculate_plan():
    """测试生成分片调度方案 API。"""
    client = TestClient(app)
    body = {
        "cases": [
            {"case_id": "c1", "case_name": "API_1", "historical_duration_ms": 1200.0, "priority": "P0"},
            {"case_id": "c2", "case_name": "API_2", "historical_duration_ms": 800.0, "priority": "P1"},
            {"case_id": "c3", "case_name": "API_3", "historical_duration_ms": 400.0, "priority": "P2"},
        ],
        "total_shards": 2,
    }
    resp = client.post("/api/v1/cluster/sharding/plan", json=body, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "动态分片调度方案生成成功"
    assert data["plan"]["total_cases"] == 3
    assert data["plan"]["total_shards"] == 2
    assert len(data["plan"]["shards"]) == 2

    plan_id = data["plan"]["plan_id"]
    get_resp = client.get(f"/api/v1/cluster/sharding/plans/{plan_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["plan"]["plan_id"] == plan_id


def test_sharding_api_rebalance_detect():
    """测试掉队节点再平衡检测 API。"""
    client = TestClient(app)
    body = {
        "shard_progress": [
            {"shard_index": 0, "node_id": "worker-1", "elapsed_ms": 15000.0, "remaining_cases": 20, "total_cases": 25},
            {"shard_index": 1, "node_id": "worker-2", "elapsed_ms": 2000.0, "remaining_cases": 0, "total_cases": 25},
        ]
    }
    resp = client.post("/api/v1/cluster/sharding/rebalance-detect", json=body, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_straggler"] is True
    assert len(data["stragglers"]) == 1
