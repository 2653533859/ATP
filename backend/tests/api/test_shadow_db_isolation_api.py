"""影子库表防污染隔离 REST API 集成测试 (T1.2)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.shadow_database_isolation_inspector import clear_db_isolation_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_db_isolation_store()
    yield
    app.dependency_overrides.clear()
    clear_db_isolation_store()


def test_shadow_db_isolation_api_flow():
    """测试影子库表 API 完整流程: 注册映射 -> 审查 SQL -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 注册影子表映射
    reg_resp = client.post(
        "/api/v1/stress/shadow-traffic/db-isolation/mappings",
        json={
            "production_table": "t_points",
            "shadow_table": "__shadow_t_points__",
            "strategy": "SHADOW_TABLE",
        },
        headers=HEADERS,
    )
    assert reg_resp.status_code == 200
    assert reg_resp.json()["mapping"]["production_table"] == "t_points"

    # 2. 获取映射列表
    maps_resp = client.get("/api/v1/stress/shadow-traffic/db-isolation/mappings", headers=HEADERS)
    assert maps_resp.status_code == 200
    assert maps_resp.json()["total"] >= 4

    # 3. 审查 SQL 隔离路由
    insp_resp = client.post(
        "/api/v1/stress/shadow-traffic/db-isolation/inspect",
        json={
            "target_cluster": "prod_mysql_cluster",
            "queries": [
                {
                    "sql": "INSERT INTO t_points (user_id, delta) VALUES (101, 50)",
                    "is_shadow_traffic": True,
                }
            ],
        },
        headers=HEADERS,
    )
    assert insp_resp.status_code == 200
    report_data = insp_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["routed_to_shadow_count"] == 1

    # 4. 查详情与列表
    get_resp = client.get(f"/api/v1/stress/shadow-traffic/db-isolation/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    list_resp = client.get("/api/v1/stress/shadow-traffic/db-isolation/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 5. 清空
    clear_resp = client.delete("/api/v1/stress/shadow-traffic/db-isolation/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/stress/shadow-traffic/db-isolation/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
