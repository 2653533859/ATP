"""色盲模拟与分类 REST API 集成测试 (T3.3)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.color_blindness_simulation_classifier import clear_cvd_report_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_cvd_report_store()
    yield
    app.dependency_overrides.clear()
    clear_cvd_report_store()


def test_color_blindness_api_flow():
    """测试色盲仿真 API 完整链路: 颜色变换 -> 审计指示器 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 模拟单色色盲变换
    sim_resp = client.post(
        "/api/v1/a11y/color-blindness/simulate-color",
        json={"hex_color": "#22C55E"},
        headers=HEADERS,
    )
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()["simulation"]
    assert sim_data["original_hex"] == "#22C55E"
    assert "protanopia_hex" in sim_data
    assert "deuteranopia_hex" in sim_data

    # 2. 审计状态指示器
    audit_resp = client.post(
        "/api/v1/a11y/color-blindness/audit",
        json={
            "component_or_page": "worker_grid",
            "status_indicators": [
                {
                    "element_id": "pod_dot",
                    "color_hex": "#22C55E",
                    "has_text": True,
                    "has_icon": True,
                    "status_meaning": "success",
                }
            ],
        },
        headers=HEADERS,
    )
    assert audit_resp.status_code == 200
    report_data = audit_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["is_wcag_1_4_1_compliant"] is True

    # 3. 查详情
    get_resp = client.get(f"/api/v1/a11y/color-blindness/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 4. 查列表
    list_resp = client.get("/api/v1/a11y/color-blindness/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 5. 清空
    clear_resp = client.delete("/api/v1/a11y/color-blindness/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/a11y/color-blindness/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
