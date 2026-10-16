"""全链路压测阶梯加压曲线与拐点检测 REST API 集成测试 (T4.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.step_load_throughput_knee_detector import clear_throughput_knee_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_throughput_knee_store()
    yield
    app.dependency_overrides.clear()
    clear_throughput_knee_store()


def test_throughput_knee_api_flow():
    """测试阶梯加压拐点检测 API 流程: 提交采样 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 提交阶梯采样
    analyze_resp = client.post(
        "/api/v1/stress/drill-report/knee-detection/analyze",
        json={
            "scenario_name": "pay_checkout_stress",
            "samples": [
                {"concurrency_threads": 200, "measured_tps": 1500.0, "avg_latency_ms": 20.0},
                {"concurrency_threads": 500, "measured_tps": 3200.0, "avg_latency_ms": 40.0},
            ],
        },
        headers=HEADERS,
    )
    assert analyze_resp.status_code == 200
    report_data = analyze_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["knee_point_concurrency"] == 500
    assert report_data["peak_tps"] == 3200.0

    # 2. 查单次报告详情
    get_resp = client.get(f"/api/v1/stress/drill-report/knee-detection/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 获取历史列表
    list_resp = client.get("/api/v1/stress/drill-report/knee-detection/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/stress/drill-report/knee-detection/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/stress/drill-report/knee-detection/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
