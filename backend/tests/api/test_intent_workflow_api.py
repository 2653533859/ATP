"""自然语言意图驱动工作流 API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.intent_workflow_synthesizer import clear_synthesis_history

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_app_and_state():
    clear_synthesis_history()
    mock_user = User(id=1, email="intent_qa@example.com", username="intent_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    yield
    app.dependency_overrides.clear()
    clear_synthesis_history()


def test_intent_workflow_api_flow():
    client = TestClient(app)

    prompt = "通过 HTTP 接口创建订单，并在数据库中核验订单状态"

    # 1. 意图驱动生成工作流
    gen_resp = client.post(
        "/api/v1/workflow/intent/generate",
        json={"prompt": prompt},
        headers=HEADERS,
    )
    assert gen_resp.status_code == 200
    synth_data = gen_resp.json()["synthesis"]
    synthesis_id = synth_data["synthesis_id"]
    assert len(synth_data["nodes"]) >= 2

    # 2. 对话式微调工作流
    refine_resp = client.post(
        "/api/v1/workflow/intent/refine",
        json={
            "synthesis_id": synthesis_id,
            "refinement_prompt": "追加一个延时等待 300ms",
        },
        headers=HEADERS,
    )
    assert refine_resp.status_code == 200
    refined_data = refine_resp.json()["synthesis"]
    assert len(refined_data["nodes"]) > len(synth_data["nodes"])

    # 3. 查询单条合成记录
    get_resp = client.get(f"/api/v1/workflow/intent/{synthesis_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["synthesis"]["synthesis_id"] == synthesis_id

    # 4. 查询历史列表
    list_resp = client.get("/api/v1/workflow/intent/history/list", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1
