"""用例自愈与断言演进 REST API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.runtime_healing_patcher import clear_healing_patches

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_app_and_state():
    clear_healing_patches()
    mock_user = User(id=1, email="heal_qa@example.com", username="heal_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    yield
    app.dependency_overrides.clear()
    clear_healing_patches()


def test_diagnose_locator_endpoint():
    client = TestClient(app)

    nodes = [
        {
            "node_id": "btn_new",
            "tag_name": "button",
            "text": "确认支付",
            "attributes": {"data-action": "checkout_pay"},
        },
    ]

    resp = client.post(
        "/api/v1/self-healing/locator/diagnose",
        json={
            "step_id": "step_pay",
            "failed_locator_type": "css",
            "failed_locator_value": "#btn_pay_legacy",
            "element_text_hint": "确认支付",
            "element_role_hint": "button",
            "screen_nodes": nodes,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    diag = resp.json()["diagnosis"]
    assert diag["has_healed_candidate"] is True
    assert diag["best_candidate"] is not None
    assert "data-action='checkout_pay'" in diag["best_candidate"]["recommended_locator_value"]


def test_heal_step_and_patch_lifecycle():
    client = TestClient(app)

    nodes = [
        {
            "node_id": "btn_add_cart_new",
            "tag_name": "button",
            "text": "立即加购",
            "attributes": {"id": "add_to_cart_btn"},
        },
    ]

    # 1. 运行时拦截并执行自愈
    heal_resp = client.post(
        "/api/v1/self-healing/locator/heal",
        json={
            "step_id": "step_add_cart",
            "failed_locator_type": "id",
            "failed_locator_value": "old_add_cart_id",
            "element_text_hint": "立即加购",
            "element_role_hint": "button",
            "screen_nodes": nodes,
            "case_id": "case_ecommerce_01",
            "platform": "web",
        },
        headers=HEADERS,
    )
    assert heal_resp.status_code == 200
    res = heal_resp.json()["result"]
    assert res["verdict"] == "HEALED_AND_RESUMED"
    patch_id = res["patch"]["patch_id"]
    assert patch_id.startswith("patch_heal_")
    assert res["patch"]["status"] == "APPLIED_IN_FLIGHT"

    # 2. 查验单张补丁详情
    get_p_resp = client.get(f"/api/v1/self-healing/patch/{patch_id}", headers=HEADERS)
    assert get_p_resp.status_code == 200
    assert get_p_resp.json()["patch"]["patch_id"] == patch_id

    # 3. 查验补丁列表
    list_p_resp = client.get("/api/v1/self-healing/patches", headers=HEADERS)
    assert list_p_resp.status_code == 200
    assert list_p_resp.json()["total"] == 1

    # 4. 确认采纳永久生效
    commit_resp = client.post(f"/api/v1/self-healing/patch/{patch_id}/commit", headers=HEADERS)
    assert commit_resp.status_code == 200
    assert commit_resp.json()["patch"]["status"] == "COMMITTED_PERMANENT"

    # 5. 否决回滚补丁
    reject_resp = client.post(f"/api/v1/self-healing/patch/{patch_id}/reject", headers=HEADERS)
    assert reject_resp.status_code == 200
    assert "已被否决回滚" in reject_resp.json()["message"]


def test_patch_not_found():
    client = TestClient(app)
    resp = client.get("/api/v1/self-healing/patch/non_existent_patch", headers=HEADERS)
    assert resp.status_code == 404


def test_assertion_evolution_and_dry_run_endpoints():
    client = TestClient(app)

    base = {"user_id": 1001, "pay_amount": 199.5}
    actual = {"code": 200, "data": {"userId": 1001, "payAmount": 199.5}}

    # 1. 检测漂移
    drift_resp = client.post(
        "/api/v1/self-healing/assertion/drift-detect",
        json={
            "baseline_response": base,
            "actual_response": actual,
            "confidence_threshold": 0.7,
        },
        headers=HEADERS,
    )
    assert drift_resp.status_code == 200
    report = drift_resp.json()["report"]
    assert report["is_drift_detected"] is True

    # 2. 演进断言
    evolve_resp = client.post(
        "/api/v1/self-healing/assertion/evolve",
        json={
            "case_id": "case_pay_01",
            "step_id": "step_assert_pay",
            "original_code": 'assert res["user_id"] == 1001 and res["pay_amount"] > 100',
            "baseline_response": base,
            "actual_response": actual,
        },
        headers=HEADERS,
    )
    assert evolve_resp.status_code == 200
    evo_data = evolve_resp.json()
    assert evo_data["evolution"]["status"] == "EVOLVED"
    assert "data" in evo_data["evolution"]["evolved_code"]
    snap_id = evo_data["snapshot"]["version_id"]

    # 3. 沙箱试跑
    dry_resp = client.post(
        "/api/v1/self-healing/assertion/dry-run",
        json={
            "assertion_code": evo_data["evolution"]["evolved_code"],
            "response_payload": actual,
        },
        headers=HEADERS,
    )
    assert dry_resp.status_code == 200
    assert dry_resp.json()["result"]["status"] == "PASS"

    # 4. 快照查询与回滚
    list_snaps = client.get("/api/v1/self-healing/assertion/snapshots", headers=HEADERS)
    assert list_snaps.status_code == 200
    assert list_snaps.json()["total"] >= 1

    rb_resp = client.post(f"/api/v1/self-healing/assertion/rollback/{snap_id}", headers=HEADERS)
    assert rb_resp.status_code == 200
    assert rb_resp.json()["snapshot"]["status"] == "ROLLBACKED"
