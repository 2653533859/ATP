"""视觉掩码与抗锯齿微去噪 REST API 集成测试 (T1.2)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.visual_anti_aliasing_noise_filter import clear_noise_filter_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_noise_filter_store()
    yield
    app.dependency_overrides.clear()
    clear_noise_filter_store()


def test_visual_noise_filter_api_flow():
    """测试视觉去噪 API 流程: 注册掩码 -> 应用去噪 -> 查报告 -> 清空。"""
    client = TestClient(app)

    # 1. 注册掩码
    mask_resp = client.post(
        "/api/v1/visual/noise-filter/masks",
        json={"name": "live_clock", "x": 10, "y": 10, "width": 80, "height": 30},
        headers=HEADERS,
    )
    assert mask_resp.status_code == 200

    # 2. 应用过滤
    raw_pixels = [
        {"x": 15, "y": 15, "delta_e": 25.0},  # 落在掩码内
        {"x": 500, "y": 500, "delta_e": 50.0},  # 真实差异
    ]
    filter_resp = client.post(
        "/api/v1/visual/noise-filter/apply",
        json={
            "target_name": "landing_hero",
            "raw_pixels": raw_pixels,
        },
        headers=HEADERS,
    )
    assert filter_resp.status_code == 200
    report_data = filter_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["mask_filtered_count"] == 1
    assert report_data["effective_structural_diff_count"] == 1

    # 3. 查详情与列表
    get_resp = client.get(f"/api/v1/visual/noise-filter/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    list_resp = client.get("/api/v1/visual/noise-filter/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/visual/noise-filter/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
