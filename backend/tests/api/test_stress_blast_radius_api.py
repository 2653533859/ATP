"""生产全链路压测安全审计与爆炸半径评估 REST API 集成测试 (T4.2)。"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.stress_blast_radius_safety_evaluator import clear_blast_radius_store

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def _setup_app_and_state():
    mock_user = User(id="user_test_eng", username="eng_tester", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    clear_blast_radius_store()
    yield
    app.dependency_overrides.clear()
    clear_blast_radius_store()


def test_stress_blast_radius_api_flow():
    """测试爆炸半径评估 API 流程: 评估安全准入 -> 查详情 -> 查列表 -> 清空。"""
    client = TestClient(app)

    # 1. 提交安全评估
    eval_resp = client.post(
        "/api/v1/stress/drill-report/blast-radius/evaluate",
        json={
            "drill_id": "drill_pre_holiday_01",
            "target_services": ["gateway", "order_service"],
            "shadow_traffic_isolated": True,
            "shadow_tables_ready": True,
            "external_bypasses_ready": True,
            "circuit_breaker_active": True,
            "estimated_max_qps": 2500.0,
            "participating_cell_ids": ["cell_east_01"],
        },
        headers=HEADERS,
    )
    assert eval_resp.status_code == 200
    report_data = eval_resp.json()["report"]
    report_id = report_data["report_id"]
    assert report_data["safety_verdict"] == "PASS_READY_FOR_STRESS"
    assert report_data["is_stress_approved"] is True
    assert len(report_data["audit_tamper_evident_fingerprint"]) == 64

    # 2. 查单次报告详情
    get_resp = client.get(f"/api/v1/stress/drill-report/blast-radius/reports/{report_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["report"]["report_id"] == report_id

    # 3. 获取历史列表
    list_resp = client.get("/api/v1/stress/drill-report/blast-radius/reports", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. 清空
    clear_resp = client.delete("/api/v1/stress/drill-report/blast-radius/reports", headers=HEADERS)
    assert clear_resp.status_code == 200
    empty_resp = client.get("/api/v1/stress/drill-report/blast-radius/reports", headers=HEADERS)
    assert empty_resp.json()["total"] == 0
