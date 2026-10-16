"""设计系统与色彩对比度 REST API 集成测试 (T2.3)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.design_system_token_contrast_checker import clear_design_audit_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_design_audit_store()
    yield
    app.dependency_overrides.clear()
    clear_design_audit_store()


def test_design_tokens_contrast_api_flow():
    """测试设计系统与对比度 API 流程: 计算对比度 -> 审计样式 -> 查详情 -> 清空。"""
    client = TestClient(app)

    # 1. 快速计算对比度
    comp_resp = client.post(
        "/api/v1/visual-ai/design-tokens/compute-contrast",
        json={"foreground_hex": "#000000", "background_hex": "#FFFFFF"},
        headers=HEADERS,
    )
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert comp_data["contrast_ratio"] >= 20.0
    assert comp_data["is_wcag_aaa_pass"] is True

    # 2. 审计页面样式
    audit_resp = client.post(
        "/api/v1/visual-ai/design-tokens/audit",
        json={
            "target_name": "checkout_theme",
            "elements": [
                {"element_id": "btn", "color": "#FFFFFF", "background_color": "#2563EB", "font_size": 14.0},
            ],
        },
        headers=HEADERS,
    )
    assert audit_resp.status_code == 200
    report_data = audit_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["total_elements_checked"] == 1

    # 3. 查详情与列表
    get_resp = client.get(f"/api/v1/visual-ai/design-tokens/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    list_resp = client.get("/api/v1/visual-ai/design-tokens/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/visual-ai/design-tokens/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
