"""键盘导航流转与焦点可达性 REST API 集成测试 (T3.2)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.a11y_keyboard_navigation_path_verifier import clear_keyboard_nav_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_keyboard_nav_store()
    yield
    app.dependency_overrides.clear()
    clear_keyboard_nav_store()


def test_keyboard_nav_api_flow():
    """测试键盘导航 API 流程: 仿真流转 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 提交仿真
    sim_resp = client.post(
        "/api/v1/a11y/keyboard-nav/simulate",
        json={
            "page_name": "login_modal",
            "elements": [
                {
                    "element_id": "input_user",
                    "tag_name": "input",
                    "tabindex": 0,
                    "has_focus_ring": True,
                },
                {
                    "element_id": "btn_submit",
                    "tag_name": "button",
                    "tabindex": 0,
                    "has_focus_ring": True,
                },
            ],
        },
        headers=HEADERS,
    )
    assert sim_resp.status_code == 200
    report_data = sim_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["total_focusable_elements"] == 2
    assert report_data["is_fully_keyboard_accessible"] is True

    # 2. 查询单次报告
    get_resp = client.get(f"/api/v1/a11y/keyboard-nav/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 获取历史列表
    list_resp = client.get("/api/v1/a11y/keyboard-nav/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/a11y/keyboard-nav/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/a11y/keyboard-nav/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
