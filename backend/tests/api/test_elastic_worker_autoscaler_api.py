"""云原生 Worker 弹性扩缩容 REST API 集成测试 (T1.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.elastic_test_worker_autoscaler import clear_autoscaler_state

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_autoscaler_state()
    yield
    app.dependency_overrides.clear()
    clear_autoscaler_state()


def test_autoscaler_api_evaluate():
    """测试评估扩缩容 API。"""
    client = TestClient(app)
    resp = client.post(
        "/api/v1/cluster/autoscaler/evaluate",
        json={"queue_depth": 16, "current_replicas": 2},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "弹性扩缩容决策评估完成"
    assert data["decision"]["action"] == "SCALE_UP"
    assert data["decision"]["desired_replicas"] == 4


def test_autoscaler_api_apply_and_status():
    """测试执行扩缩容与获取集群状态 API。"""
    client = TestClient(app)
    apply_resp = client.post(
        "/api/v1/cluster/autoscaler/apply",
        json={"queue_depth": 24},
        headers=HEADERS,
    )
    assert apply_resp.status_code == 200
    apply_data = apply_resp.json()
    assert apply_data["status"] == "APPLIED"

    status_resp = client.get("/api/v1/cluster/autoscaler/status", headers=HEADERS)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["current_active_replicas"] == 6

    events_resp = client.get("/api/v1/cluster/autoscaler/events", headers=HEADERS)
    assert events_resp.status_code == 200
    assert events_resp.json()["total"] >= 1
