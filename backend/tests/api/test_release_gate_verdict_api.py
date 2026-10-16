"""自动化发版准入阻断裁决器与豁免网关 REST API 集成测试 (T4.2)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_admin, require_engineer
from app.main import app
from app.models.user import User
from app.services.smart_release_go_no_go_decider import clear_release_gate_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_admin = User(id="user_test_admin", username="admin_architect", role="admin")
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    app.dependency_overrides[require_engineer] = lambda: mock_admin
    app.dependency_overrides[require_admin] = lambda: mock_admin
    clear_release_gate_store()
    yield
    app.dependency_overrides.clear()
    clear_release_gate_store()


def test_release_gate_api_flow():
    """测试发版门禁 API 流程: 评估 -> 豁免特批 -> 撤销豁免 -> 列表 -> 清空。"""
    client = TestClient(app)

    # 1. 评估出 NO_GO 阻断
    eval_resp = client.post(
        "/api/v1/gatekeeper/release-verdict/evaluate",
        json={
            "target_version": "v4.2.0-hotfix",
            "quality_score": 55.0,
            "p0_defects_count": 1,
        },
        headers=HEADERS,
    )
    assert eval_resp.status_code == 200
    rec_data = eval_resp.json()["record"]
    release_id = rec_data["release_id"]
    assert rec_data["verdict"] == "NO_GO"

    # 2. 签署风险豁免
    waive_resp = client.post(
        f"/api/v1/gatekeeper/release-verdict/{release_id}/waive",
        json={
            "waiver_reason": "紧急安全漏洞热修复，已由 CTO 邮件批准",
            "rollback_plan": "K8s Helm rollback 并在 5 分钟内回滚镜像",
        },
        headers=HEADERS,
    )
    assert waive_resp.status_code == 200
    assert waive_resp.json()["record"]["verdict"] == "WAIVED_GO"

    # 3. 查详情与列表
    get_resp = client.get(f"/api/v1/gatekeeper/release-verdict/records/{release_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["record"]["is_waived"] is True

    list_resp = client.get("/api/v1/gatekeeper/release-verdict/records", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 撤销豁免
    revoke_resp = client.post(f"/api/v1/gatekeeper/release-verdict/{release_id}/revoke-waiver", headers=HEADERS)
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["record"]["verdict"] == "NO_GO"

    # 5. 清空
    clear_resp = client.delete("/api/v1/gatekeeper/release-verdict/records", headers=HEADERS)
    assert clear_resp.status_code == 200
