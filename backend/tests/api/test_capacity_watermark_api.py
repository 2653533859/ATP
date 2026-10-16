"""多源基础设施容量水位度量 REST API 集成测试 (T3.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.multisource_capacity_watermark_meter import clear_watermark_report_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_watermark_report_store()
    yield
    app.dependency_overrides.clear()
    clear_watermark_report_store()


def test_capacity_watermark_api_flow():
    """测试容量水位度量 API 流程: 采集评估 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 提交容量水位采样
    meter_resp = client.post(
        "/api/v1/stress/bottleneck-guardian/watermark/meter",
        json={
            "target_cluster_or_env": "k8s_prod_cluster",
            "metric_samples": [
                {
                    "resource_id": "hikari_db_pool",
                    "resource_type": "DATABASE_POOL",
                    "current_value": 50.0,
                    "capacity_limit": 100.0,
                    "unit": "conns",
                }
            ],
        },
        headers=HEADERS,
    )
    assert meter_resp.status_code == 200
    report_data = meter_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["max_utilization_pct"] == 50.0
    assert report_data["requires_avalanche_breaker"] is False

    # 2. 查单次报告详情
    get_resp = client.get(f"/api/v1/stress/bottleneck-guardian/watermark/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 获取历史列表
    list_resp = client.get("/api/v1/stress/bottleneck-guardian/watermark/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/stress/bottleneck-guardian/watermark/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/stress/bottleneck-guardian/watermark/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
