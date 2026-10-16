"""跨环境配置漂移 REST API 集成测试 (T2.1)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.multi_env_config_drift_detector import clear_config_drift_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_config_drift_store()
    yield
    app.dependency_overrides.clear()
    clear_config_drift_store()


def test_config_drift_api_compare_flow():
    """测试配置漂移 API: 登记快照 -> 执行比对 -> 查报告 -> 清空。"""
    client = TestClient(app)

    # 1. 登记生产快照
    reg_resp = client.post(
        "/api/v1/env-drift/config/register-snapshot",
        json={
            "env_name": "production",
            "service_name": "cart-service",
            "configs": {"CART_EXPIRY_SECONDS": 7200, "ENABLE_REDIS_CACHE": True},
        },
        headers=HEADERS,
    )
    assert reg_resp.status_code == 200

    # 2. 执行比对
    compare_resp = client.post(
        "/api/v1/env-drift/config/compare",
        json={
            "service_name": "cart-service",
            "base_env": "production",
            "target_env": "testing",
            "target_configs": {"CART_EXPIRY_SECONDS": 300, "ENABLE_REDIS_CACHE": True},
        },
        headers=HEADERS,
    )
    assert compare_resp.status_code == 200
    report_data = compare_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["total_keys_checked"] == 2
    assert report_data["drift_count"] == 1

    # 3. 查报告详情
    get_resp = client.get(f"/api/v1/env-drift/config/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 4. 查报告列表
    list_resp = client.get("/api/v1/env-drift/config/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 5. 清空报告
    clear_resp = client.delete("/api/v1/env-drift/config/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
