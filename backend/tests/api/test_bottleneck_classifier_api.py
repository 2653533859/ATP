"""调用链热点慢调用与瓶颈归因 REST API 集成测试 (T3.2)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.distributed_bottleneck_root_cause_classifier import clear_bottleneck_report_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_bottleneck_report_store()
    yield
    app.dependency_overrides.clear()
    clear_bottleneck_report_store()


def test_bottleneck_classifier_api_flow():
    """测试瓶颈归因 API 完整链路: 归因分析 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 提交分析
    resp = client.post(
        "/api/v1/stress/bottleneck-guardian/bottlenecks/classify",
        json={
            "scenario_name": "pay_stress_test",
            "spans": [
                {
                    "service_name": "pay_svc",
                    "endpoint_or_sql": "UPDATE t_account",
                    "duration_ms": 300.0,
                    "lock_wait_time_ms": 250.0,
                }
            ],
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    report_data = resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["total_bottlenecks_count"] == 1
    assert "LOCK_CONTENTION_DEADLOCK" in report_data["primary_root_cause"]

    # 2. 查单次报告详情
    get_resp = client.get(f"/api/v1/stress/bottleneck-guardian/bottlenecks/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 获取历史列表
    list_resp = client.get("/api/v1/stress/bottleneck-guardian/bottlenecks/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/stress/bottleneck-guardian/bottlenecks/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/stress/bottleneck-guardian/bottlenecks/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
