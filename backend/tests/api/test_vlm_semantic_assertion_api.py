"""基于视觉大模型 (VLM) 的 UI 页面断言 REST API 集成测试 (T2.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.vlm_ui_semantic_assertion_reasoner import clear_vlm_assertion_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_vlm_assertion_store()
    yield
    app.dependency_overrides.clear()
    clear_vlm_assertion_store()


def test_vlm_assertion_api_flow():
    """测试视觉断言 API 流程: 查询规则类型 -> 执行评估 -> 查详情 -> 清空。"""
    client = TestClient(app)

    # 1. 查询规则类型
    types_resp = client.get("/api/v1/visual-ai/semantic-assertion/rule-types", headers=HEADERS)
    assert types_resp.status_code == 200
    assert types_resp.json()["total"] >= 4

    # 2. 执行断言推理
    eval_resp = client.post(
        "/api/v1/visual-ai/semantic-assertion/evaluate",
        json={
            "page_name": "checkout_screen",
            "rules": [
                {"rule_type": "ASSERT_NO_WHITE_SCREEN", "target_description": "防白屏"},
                {"rule_type": "ASSERT_KEY_ELEMENT_VISIBLE", "target_description": "支付按钮"},
            ],
            "simulated_white_screen_ratio": 0.02,
        },
        headers=HEADERS,
    )
    assert eval_resp.status_code == 200
    report_data = eval_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["overall_passed"] is True
    assert report_data["passed_count"] == 2

    # 3. 查详情与列表
    get_resp = client.get(f"/api/v1/visual-ai/semantic-assertion/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    list_resp = client.get("/api/v1/visual-ai/semantic-assertion/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/visual-ai/semantic-assertion/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
