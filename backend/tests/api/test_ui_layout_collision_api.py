"""布局碰撞与溢出检测 REST API 集成测试 (T2.2)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.ui_layout_overflow_collision_detector import clear_layout_defect_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_layout_defect_store()
    yield
    app.dependency_overrides.clear()
    clear_layout_defect_store()


def test_layout_collision_api_flow():
    """测试布局检测 API 流程: 执行检测 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 发起检测
    det_resp = client.post(
        "/api/v1/visual-ai/layout-collision/detect",
        json={
            "page_name": "mobile_checkout",
            "viewport_width": 375,
            "viewport_height": 812,
            "elements": [
                {"element_id": "box_1", "tag_name": "div", "x": 10, "y": 10, "width": 100, "height": 40},
                {"element_id": "box_2", "tag_name": "div", "x": 20, "y": 15, "width": 100, "height": 40},  # 碰撞
            ],
        },
        headers=HEADERS,
    )
    assert det_resp.status_code == 200
    report_data = det_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["collision_count"] == 1

    # 2. 查详情与列表
    get_resp = client.get(f"/api/v1/visual-ai/layout-collision/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    list_resp = client.get("/api/v1/visual-ai/layout-collision/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 3. 清空
    clear_resp = client.delete("/api/v1/visual-ai/layout-collision/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
