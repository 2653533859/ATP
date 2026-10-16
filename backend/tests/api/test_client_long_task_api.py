"""前端运行时长任务与掉帧卡顿诊断 REST API 集成测试 (T4.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.client_long_task_jank_profiler import clear_long_task_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_long_task_store()
    yield
    app.dependency_overrides.clear()
    clear_long_task_store()


def test_client_long_task_api_flow():
    """测试长任务 API 完整链路: 提交采样 -> 查报告 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 提交长任务性能采样批次
    prof_resp = client.post(
        "/api/v1/client-perf/long-tasks/profile",
        json={
            "page_name": "device_matrix_panel",
            "task_events": [
                {
                    "duration_ms": 120.0,
                    "culprit_symbol": "echarts.init",
                    "call_stack": ["renderChart", "echarts"],
                },
                {
                    "duration_ms": 10.0,
                    "culprit_symbol": "onMount",
                },
            ],
            "sampling_duration_ms": 5000.0,
        },
        headers=HEADERS,
    )
    assert prof_resp.status_code == 200
    report_data = prof_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["total_tasks_count"] == 2
    assert report_data["long_tasks_count"] == 1
    assert report_data["total_blocking_time_ms"] == 70.0  # 120 - 50 = 70ms

    # 2. 查询单次报告
    get_resp = client.get(f"/api/v1/client-perf/long-tasks/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 查列表
    list_resp = client.get("/api/v1/client-perf/long-tasks/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/client-perf/long-tasks/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/client-perf/long-tasks/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
