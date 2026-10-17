"""跨端测试用例智能迁移 REST API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.api.v1.cross_platform_migration_api import clear_migration_history
from app.main import app
from app.models.user import User

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_app_and_state():
    clear_migration_history()
    mock_user = User(id=1, email="mig_qa@example.com", username="mig_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    yield
    app.dependency_overrides.clear()
    clear_migration_history()


def test_translate_case_endpoint():
    client = TestClient(app)

    steps = [
        {
            "step_id": "step_1",
            "action_type": "TAP",
            "locator": {"type": "id", "value": "checkout_btn", "text": "立即结算"},
        },
        {
            "step_id": "step_2",
            "action_type": "FILL_TEXT",
            "locator": {"type": "id", "value": "input_coupon"},
            "input_text": "VIP2026",
        },
    ]

    target_candidates = [
        {
            "element_id": "cand_01",
            "element_type": "button",
            "platform": "android",
            "text": "确认结算",
            "identifier": "com.shop.app:id/checkout_action",
        },
        {
            "element_id": "cand_02",
            "element_type": "input",
            "platform": "android",
            "text": "优惠券码",
            "identifier": "com.shop.app:id/coupon_field",
        },
    ]

    resp = client.post(
        "/api/v1/migration/case/translate",
        json={
            "case_id": "case_web_checkout_01",
            "case_name": "Web 加购与结算主流程",
            "source_platform": "web",
            "target_platform": "android",
            "steps": steps,
            "target_candidates": target_candidates,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()["result"]
    assert data["source_platform"] == "web"
    assert data["target_platform"] == "android"
    assert len(data["mapped_steps"]) == 2
    assert data["average_confidence"] >= 0.8
    migration_id = data["mapping_id"]

    # 查验证书/单条迁移查询
    get_resp = client.get(f"/api/v1/migration/{migration_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["migration"]["mapping_id"] == migration_id


def test_translate_case_invalid_platform():
    client = TestClient(app)
    resp = client.post(
        "/api/v1/migration/case/translate",
        json={
            "source_platform": "unsupported_os",
            "target_platform": "android",
            "steps": [],
        },
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_match_elements_endpoint():
    client = TestClient(app)
    resp = client.post(
        "/api/v1/migration/elements/match",
        json={
            "source_element": {
                "element_id": "s1",
                "element_type": "button",
                "text": "立即付款",
                "identifier": "btn_pay",
            },
            "candidates": [
                {
                    "element_id": "c1",
                    "element_type": "button",
                    "text": "确认支付",
                    "identifier": "com.app:id/pay_btn",
                },
            ],
            "threshold": 0.65,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_confident"] is True
    assert data["match"]["matched_element"]["element_id"] == "c1"


def test_batch_migration_and_history():
    client = TestClient(app)

    batch_resp = client.post(
        "/api/v1/migration/batch",
        json={
            "case_ids": ["case_001", "case_002", "case_003"],
            "source_platform": "ios",
            "target_platform": "android",
            "target_device_id": "127.0.0.1:5555",
        },
        headers=HEADERS,
    )
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()["batch"]
    assert batch_data["total_cases"] == 3
    assert batch_data["status"] == "COMPLETED"

    # 查询列表
    list_resp = client.get("/api/v1/migration/history/list", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1


def test_get_migration_not_found():
    client = TestClient(app)
    resp = client.get("/api/v1/migration/unknown_mig_id", headers=HEADERS)
    assert resp.status_code == 404


def test_analyze_parity_endpoint_and_reports():
    client = TestClient(app)

    src_elements = [
        {"node_id": "ios_1", "role": "button", "text": "立即支付", "identifier": "btn_pay"},
        {"node_id": "ios_2", "role": "input", "text": "账号", "identifier": "acc_input"},
    ]
    tgt_elements = [
        {"node_id": "and_1", "role": "button", "text": "确认付款", "identifier": "pay_btn"},
        {"node_id": "and_2", "role": "input", "text": "账号", "identifier": "acc_field"},
    ]

    resp = client.post(
        "/api/v1/migration/parity/analyze",
        json={
            "screen_name": "收银台页面",
            "source_platform": "ios",
            "target_platform": "android",
            "source_elements": src_elements,
            "target_elements": tgt_elements,
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    report = resp.json()["report"]
    assert report["screen_name"] == "收银台页面"
    assert report["grade"] in ("GRADE_A", "GRADE_B")
    assert report["verdict"] in ("PASS", "WARN")
    report_id = report["report_id"]

    # 获取列表
    list_resp = client.get("/api/v1/migration/parity/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 获取单张详情
    get_resp = client.get(f"/api/v1/migration/parity/report/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id
