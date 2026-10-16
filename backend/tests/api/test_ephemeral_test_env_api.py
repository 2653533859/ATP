"""临时沙箱测试环境生命周期 REST API 集成测试 (T1.3)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.ephemeral_test_env_lifecycle_manager import clear_ephemeral_envs

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_ephemeral_envs()
    yield
    app.dependency_overrides.clear()
    clear_ephemeral_envs()


def test_ephemeral_env_api_lifecycle_flow():
    """测试完整生命周期 API: 供给 -> 查详情 -> 续约 -> 列表 -> 销毁 -> 回收。"""
    client = TestClient(app)

    # 1. 供给拉起
    prov_resp = client.post(
        "/api/v1/cluster/ephemeral-env/provision",
        json={"branch_or_pr": "pr-888-pay", "cpu_limit_cores": 2.0, "memory_limit_gib": 4.0},
        headers=HEADERS,
    )
    assert prov_resp.status_code == 200
    env_data = prov_resp.json()["env"]
    env_id = env_data["env_id"]
    assert env_data["status"] == "READY"

    # 2. 查询详情
    get_resp = client.get(f"/api/v1/cluster/ephemeral-env/{env_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["env"]["env_id"] == env_id

    # 3. 延长租约
    lease_resp = client.post(
        f"/api/v1/cluster/ephemeral-env/{env_id}/extend-lease",
        json={"extra_seconds": 600},
        headers=HEADERS,
    )
    assert lease_resp.status_code == 200
    assert lease_resp.json()["env"]["ttl_seconds"] == 4200

    # 4. 列表查询
    list_resp = client.get("/api/v1/cluster/ephemeral-env/list", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 5. 优雅销毁
    teardown_resp = client.post(f"/api/v1/cluster/ephemeral-env/{env_id}/teardown", headers=HEADERS)
    assert teardown_resp.status_code == 200
    assert teardown_resp.json()["success"] is True

    # 6. 回收超期扫描
    reclaim_resp = client.post("/api/v1/cluster/ephemeral-env/reclaim-expired", headers=HEADERS)
    assert reclaim_resp.status_code == 200
    assert "result" in reclaim_resp.json()
