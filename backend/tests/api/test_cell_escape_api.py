"""跨单元依赖逃逸检测 REST API 集成测试 (T2.2)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.cell_escape_dependency_detector import clear_cell_escape_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_cell_escape_store()
    yield
    app.dependency_overrides.clear()
    clear_cell_escape_store()


def test_cell_escape_api_flow():
    """测试单元逃逸检测 API 流程: 提交调用边 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 发起逃逸检测
    detect_resp = client.post(
        "/api/v1/stress/cell-isolation/escape/detect",
        json={
            "topology_name": "pay_core_mesh",
            "invocation_edges": [
                {
                    "source_cell_id": "cell_01",
                    "source_service": "cart",
                    "target_cell_id": "cell_01",
                    "target_service": "checkout",
                }
            ],
        },
        headers=HEADERS,
    )
    assert detect_resp.status_code == 200
    report_data = detect_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["total_edges_checked"] == 1
    assert report_data["is_strictly_cell_isolated"] is True

    # 2. 查单次报告详情
    get_resp = client.get(f"/api/v1/stress/cell-isolation/escape/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 获取历史列表
    list_resp = client.get("/api/v1/stress/cell-isolation/escape/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/stress/cell-isolation/escape/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/stress/cell-isolation/escape/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
