"""接口契约与业务 Spec 驱动的端到端用例智能生成 REST API 集成测试 (T3.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.llm_spec_to_e2e_case_synthesizer import clear_synthesized_cases_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_synthesized_cases_store()
    yield
    app.dependency_overrides.clear()
    clear_synthesized_cases_store()


def test_synthesize_case_api_generate_flow():
    """测试端到端用例合成 API: 生成 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 触发生成
    gen_resp = client.post(
        "/api/v1/llm-testing/synthesize-cases/generate",
        json={
            "spec_title": "极简三步业务测试",
            "business_flow_description": "验证登录与下单",
        },
        headers=HEADERS,
    )
    assert gen_resp.status_code == 200
    case_data = gen_resp.json()["case"]
    case_id = case_data["case_id"]
    assert case_data["steps_count"] >= 2
    assert "import pytest" in case_data["generated_python_script"]

    # 2. 查用例详情
    get_resp = client.get(f"/api/v1/llm-testing/synthesize-cases/cases/{case_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["case"]["case_id"] == case_id

    # 3. 查用例列表
    list_resp = client.get("/api/v1/llm-testing/synthesize-cases/cases", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/llm-testing/synthesize-cases/cases", headers=HEADERS)
    assert clear_resp.status_code == 200
