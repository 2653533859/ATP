"""多视口像素级视觉比对 REST API 集成测试 (T1.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.visual_pixel_ssim_diff_engine import clear_visual_diff_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_visual_diff_store()
    yield
    app.dependency_overrides.clear()
    clear_visual_diff_store()


def test_visual_diff_api_compare_flow():
    """测试多视口视觉比对 API 流程: 触发对比 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 触发比对
    resp = client.post(
        "/api/v1/visual/pixel-diff/compare",
        json={
            "snapshot_name": "checkout_responsive_matrix",
            "viewports": ["DESKTOP", "MOBILE"],
            "tolerance_threshold": 0.98,
            "simulated_viewport_diffs": {"DESKTOP": 0, "MOBILE": 10},
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    report_data = resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["overall_passed"] is True
    assert report_data["total_viewports_tested"] == 2

    # 2. 查详情
    get_resp = client.get(f"/api/v1/visual/pixel-diff/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 查列表
    list_resp = client.get("/api/v1/visual/pixel-diff/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/visual/pixel-diff/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
