"""数据库 Schema 结构漂移比对 REST API 集成测试 (T2.2)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.db_schema_drift_compatibility_checker import clear_schema_drift_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_schema_drift_store()
    yield
    app.dependency_overrides.clear()
    clear_schema_drift_store()


def test_schema_drift_api_compare_flow():
    """测试比对数据库表结构与索引差异 API 流程。"""
    client = TestClient(app)

    # 1. 登记快照
    reg_resp = client.post(
        "/api/v1/env-drift/schema/register-snapshot",
        json={
            "env_name": "production",
            "database_name": "pay_db",
            "tables": [
                {
                    "table_name": "transactions",
                    "columns": [
                        {"name": "tx_id", "data_type": "VARCHAR(64)", "nullable": False, "is_primary_key": True},
                        {"name": "amount", "data_type": "DECIMAL", "nullable": False},
                    ],
                }
            ],
        },
        headers=HEADERS,
    )
    assert reg_resp.status_code == 200

    # 2. 执行直接比对
    compare_resp = client.post(
        "/api/v1/env-drift/schema/compare",
        json={
            "database_name": "pay_db",
            "base_env": "production",
            "target_env": "testing",
            "target_tables": [
                {
                    "table_name": "transactions",
                    "columns": [
                        {"name": "tx_id", "data_type": "VARCHAR(64)", "nullable": False, "is_primary_key": True},
                        # 缺失 amount
                    ],
                }
            ],
        },
        headers=HEADERS,
    )
    assert compare_resp.status_code == 200
    report = compare_resp.json()["report"]
    report_id = report["report_id"]
    assert report["drift_items_count"] == 1
    assert "ALTER TABLE transactions ADD COLUMN amount" in report["remediation_ddl_script"]

    # 3. 查详情与列表
    get_resp = client.get(f"/api/v1/env-drift/schema/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    list_resp = client.get("/api/v1/env-drift/schema/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/env-drift/schema/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
