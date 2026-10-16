"""IaC 基础设施合规巡检 REST API 集成测试 (T2.3)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.iac_network_policy_compliance_scanner import clear_compliance_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_compliance_store()
    yield
    app.dependency_overrides.clear()
    clear_compliance_store()


def test_iac_compliance_api_scan_flow():
    """测试 IaC 合规扫描 API 流程: 规则查询 -> 扫描 -> 查报告 -> 清空。"""
    client = TestClient(app)

    # 1. 查询内置规则
    rules_resp = client.get("/api/v1/env-drift/iac-compliance/rules", headers=HEADERS)
    assert rules_resp.status_code == 200
    assert rules_resp.json()["total"] >= 5

    # 2. 执行扫描
    scan_resp = client.post(
        "/api/v1/env-drift/iac-compliance/scan",
        json={
            "target_name": "release-v4.2.0",
            "manifests": [
                {
                    "kind": "Deployment",
                    "metadata": {"name": "api-gateway"},
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {"name": "gateway", "securityContext": {"privileged": True}},
                                ],
                            }
                        }
                    },
                }
            ],
        },
        headers=HEADERS,
    )
    assert scan_resp.status_code == 200
    data = scan_resp.json()["report"]
    report_id = data["report_id"]
    assert data["verdict"] == "BLOCKED"
    assert data["critical_count"] >= 1

    # 3. 查报告详情与列表
    get_resp = client.get(f"/api/v1/env-drift/iac-compliance/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    list_resp = client.get("/api/v1/env-drift/iac-compliance/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/env-drift/iac-compliance/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
