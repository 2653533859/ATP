"""单元故障演练与容灾接管 REST API 集成测试 (T2.3)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.cell_failover_resilience_verifier import clear_failover_report_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_failover_report_store()
    yield
    app.dependency_overrides.clear()
    clear_failover_report_store()


def test_cell_failover_api_flow():
    """测试单元容灾切流演练 API 完整链路: 触发演练 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 发起单元容灾切流演练
    sim_resp = client.post(
        "/api/v1/stress/cell-isolation/failover/simulate",
        json={
            "failed_cell_id": "cell_east_01",
            "standby_cell_id": "cell_east_02",
            "traffic_shift_percentage": 100.0,
            "dns_switch_delay_ms": 600.0,
            "db_replication_lag_ms": 150.0,
            "route_convergence_delay_ms": 350.0,
        },
        headers=HEADERS,
    )
    assert sim_resp.status_code == 200
    report_data = sim_resp.json()["report"]
    drill_id = report_data["drill_id"]
    assert report_data["verdict"] == "FAILOVER_SUCCESS"
    assert report_data["is_resilience_qualified"] is True

    # 2. 查单次报告详情
    get_resp = client.get(f"/api/v1/stress/cell-isolation/failover/reports/{drill_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["drill_id"] == drill_id

    # 3. 获取历史列表
    list_resp = client.get("/api/v1/stress/cell-isolation/failover/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/stress/cell-isolation/failover/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/stress/cell-isolation/failover/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
