"""全链路影子流量染色与透传校验 REST API 集成测试 (T1.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.shadow_traffic_taint_propagator import clear_shadow_taint_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_shadow_taint_store()
    yield
    app.dependency_overrides.clear()
    clear_shadow_taint_store()


def test_shadow_traffic_api_flow():
    """测试影子染色 API 流程: 注入染色标 -> 校验透传链路 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 注入染色标
    inj_resp = client.post(
        "/api/v1/stress/shadow-traffic/taint/inject",
        json={
            "protocol": "HTTP_REST",
            "headers": {"Authorization": "Bearer token123"},
            "trace_id": "st_test_001",
        },
        headers=HEADERS,
    )
    assert inj_resp.status_code == 200
    inj_data = inj_resp.json()
    assert inj_data["injected_headers"]["X-ATP-Shadow"] == "true"
    assert inj_data["injected_headers"]["X-ATP-Shadow-Trace"] == "st_test_001"

    # 2. 校验透传链路
    ver_resp = client.post(
        "/api/v1/stress/shadow-traffic/taint/verify-propagation",
        json={
            "trace_id": "st_test_001",
            "hop_traces": [
                {
                    "service_name": "gateway",
                    "protocol": "HTTP_REST",
                    "headers": {"X-ATP-Shadow": "true", "X-ATP-Shadow-Trace": "st_test_001"},
                },
                {
                    "service_name": "backend",
                    "protocol": "HTTP_REST",
                    "headers": {"X-ATP-Shadow": "true", "X-ATP-Shadow-Trace": "st_test_001"},
                },
            ],
        },
        headers=HEADERS,
    )
    assert ver_resp.status_code == 200
    report_data = ver_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["total_hops_count"] == 2
    assert report_data["integrity_score_pct"] == 100.0

    # 3. 查详情
    get_resp = client.get(f"/api/v1/stress/shadow-traffic/taint/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 4. 查列表
    list_resp = client.get("/api/v1/stress/shadow-traffic/taint/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 5. 清空
    clear_resp = client.delete("/api/v1/stress/shadow-traffic/taint/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/stress/shadow-traffic/taint/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
