"""自主 API 模糊变异探查 REST API 集成测试 (T3.3)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.autonomous_api_fuzzing_explorer import clear_fuzzing_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_fuzzing_store()
    yield
    app.dependency_overrides.clear()
    clear_fuzzing_store()


def test_autonomous_fuzzing_api_flow():
    """测试模糊变异 API 流程: 查询策略 -> 执行探测 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 查询策略
    strat_resp = client.get("/api/v1/llm-testing/fuzzing-explore/strategies", headers=HEADERS)
    assert strat_resp.status_code == 200
    assert len(strat_resp.json()["strategies"]) >= 5

    # 2. 发起变异测试
    run_resp = client.post(
        "/api/v1/llm-testing/fuzzing-explore/run",
        json={
            "endpoint": "/api/v1/search",
            "method": "POST",
            "base_payload": {"keyword": "phone"},
            "strategies": ["SQL_INJECTION_PROBE"],
        },
        headers=HEADERS,
    )
    assert run_resp.status_code == 200
    session_data = run_resp.json()["session"]
    session_id = session_data["session_id"]
    assert session_data["total_mutations_count"] == 3

    # 3. 查详情
    get_resp = client.get(f"/api/v1/llm-testing/fuzzing-explore/sessions/{session_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["session"]["session_id"] == session_id

    # 4. 查列表
    list_resp = client.get("/api/v1/llm-testing/fuzzing-explore/sessions", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 5. 清空
    clear_resp = client.delete("/api/v1/llm-testing/fuzzing-explore/sessions", headers=HEADERS)
    assert clear_resp.status_code == 200
