"""WCAG 2.2 无障碍可访问性扫描 REST API 集成测试 (T3.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.wcag_accessibility_deep_scanner import clear_wcag_report_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_wcag_report_store()
    yield
    app.dependency_overrides.clear()
    clear_wcag_report_store()


def test_wcag_accessibility_api_flow():
    """测试 WCAG 扫描 API 完整生命周期: 扫描 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 发起无障碍扫描
    scan_resp = client.post(
        "/api/v1/a11y/wcag-scanner/scan",
        json={
            "page_url_or_name": "https://atp.example.com/login",
            "elements": [
                {
                    "element_id": "img_logo",
                    "tag_name": "img",
                    "attributes": {"src": "/logo.svg", "alt": "Logo"},
                },
                {
                    "element_id": "btn_login",
                    "tag_name": "button",
                    "text_content": "登录",
                    "width": 120.0,
                    "height": 40.0,
                },
            ],
        },
        headers=HEADERS,
    )
    assert scan_resp.status_code == 200
    report_data = scan_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["total_elements_scanned"] == 2
    assert report_data["is_wcag_aa_compliant"] is True

    # 2. 查询单次报告详情
    get_resp = client.get(f"/api/v1/a11y/wcag-scanner/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 获取历史报告列表
    list_resp = client.get("/api/v1/a11y/wcag-scanner/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空报告仓库
    clear_resp = client.delete("/api/v1/a11y/wcag-scanner/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_list = client.get("/api/v1/a11y/wcag-scanner/reports", headers=HEADERS)
    assert empty_list.json()["total"] == 0
