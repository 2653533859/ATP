"""防雪崩分级熔断 REST API 集成测试 (T3.3)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.adaptive_avalanche_circuit_breaker import clear_avalanche_breaker_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_avalanche_breaker_store()
    yield
    app.dependency_overrides.clear()
    clear_avalanche_breaker_store()


def test_adaptive_circuit_breaker_api_flow():
    """测试熔断 API 完整流程: 评估熔断 -> 查看状态 -> 重置 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 触发评估 (水位 88% -> 触发熔断)
    eval_resp = client.post(
        "/api/v1/stress/bottleneck-guardian/circuit-breaker/evaluate",
        json={
            "scenario_name": "pay_peak_drill",
            "max_resource_watermark_pct": 88.0,
            "p99_latency_ms": 250.0,
            "current_tps": 5000.0,
        },
        headers=HEADERS,
    )
    assert eval_resp.status_code == 200
    report_data = eval_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["is_circuit_broken"] is True
    assert report_data["final_decision"]["action"] == "ABORT_STRESS_TEST"

    # 2. 查询当前全局状态
    status_resp = client.get("/api/v1/stress/bottleneck-guardian/circuit-breaker/status", headers=HEADERS)
    assert status_resp.status_code == 200
    assert status_resp.json()["current_state"] == "TRIPPED_HARD_BREAK"

    # 3. 手动重置熔断器
    reset_resp = client.post("/api/v1/stress/bottleneck-guardian/circuit-breaker/reset", headers=HEADERS)
    assert reset_resp.status_code == 200
    assert reset_resp.json()["current_state"] == "CLOSED_NORMAL"

    # 4. 查详情与列表
    get_resp = client.get(f"/api/v1/stress/bottleneck-guardian/circuit-breaker/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    list_resp = client.get("/api/v1/stress/bottleneck-guardian/circuit-breaker/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 5. 清空
    clear_resp = client.delete("/api/v1/stress/bottleneck-guardian/circuit-breaker/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/stress/bottleneck-guardian/circuit-breaker/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
