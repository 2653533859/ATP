"""全链路影子压测管控与发压作业 REST API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.stress_traffic_isolation_engine import get_global_stress_manager

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_stress_api():
    mock_user = User(id=1, email="stress_qa@example.com", username="stress_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    mgr = get_global_stress_manager()
    mgr.clear()
    mgr._load_seed_rules()
    yield
    app.dependency_overrides.clear()
    mgr.clear()
    mgr._load_seed_rules()


def test_list_and_create_stress_rules():
    client = TestClient(app)

    # 1. 查询默认规则
    r1 = client.get("/api/v1/stress-testing/rules", headers=HEADERS)
    assert r1.status_code == 200
    data = r1.json()
    assert data["status"] == "success"
    assert data["total"] >= 1

    # 2. 创建新规则
    r2 = client.post(
        "/api/v1/stress-testing/rules",
        headers=HEADERS,
        json={
            "name": "用户中心阶梯压测规则",
            "rule_type": "URL_PATH_MATCH",
            "target_service": "user-service",
            "target_path_pattern": "/v1/users/.*",
            "shadow_table_suffix": "_shadow",
        },
    )
    assert r2.status_code == 200
    res2 = r2.json()
    assert res2["status"] == "success"
    assert res2["rule"]["target_service"] == "user-service"

    # 3. 错误规则类型返回 400
    r3 = client.post(
        "/api/v1/stress-testing/rules",
        headers=HEADERS,
        json={
            "name": "非法规则",
            "rule_type": "UNKNOWN_TYPE",
            "target_service": "bad-service",
        },
    )
    assert r3.status_code == 400


def test_generate_step_plan_endpoint():
    client = TestClient(app)
    resp = client.post(
        "/api/v1/stress-testing/plans/generate-step",
        headers=HEADERS,
        json={
            "target_service": "payment-service",
            "initial_vu": 500,
            "step_vu": 1000,
            "steps_count": 5,
            "stage_duration_seconds": 60,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["plan"]["stages"]) == 5
    assert data["plan"]["peak_vu_count"] == 4500


def test_workers_allocation_endpoint():
    client = TestClient(app)
    resp = client.post(
        "/api/v1/stress-testing/workers/allocation",
        headers=HEADERS,
        json={
            "target_peak_vu": 5000,
            "max_vu_per_worker": 2000,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["allocation"]["worker_nodes_count"] == 3
    assert data["allocation"]["vu_per_worker"] == 1667


def test_evaluate_progression_endpoint():
    client = TestClient(app)
    plan_dict = {
        "plan_id": "p_test_01",
        "plan_name": "支付压测计划",
        "target_service": "payment-service",
        "profile_type": "STEP_RAMP_UP",
        "stages": [
            {
                "stage_index": 1,
                "stage_name": "阶段1 (500 VU)",
                "target_vu_count": 500,
                "duration_seconds": 60,
                "expected_tps_ceiling": 5000.0,
            },
            {
                "stage_index": 2,
                "stage_name": "阶段2 (1500 VU)",
                "target_vu_count": 1500,
                "duration_seconds": 60,
                "expected_tps_ceiling": 15000.0,
            },
        ],
    }

    # 1. 阶段进行中
    r1 = client.post(
        "/api/v1/stress-testing/evaluations/progression",
        headers=HEADERS,
        json={
            "plan_dict": plan_dict,
            "current_stage_index": 1,
            "stage_elapsed_seconds": 30,
            "current_error_rate_pct": 0.05,
        },
    )
    assert r1.status_code == 200
    assert r1.json()["verdict"]["action"] == "MAINTAIN_CURRENT"

    # 2. 阶段达标晋级
    r2 = client.post(
        "/api/v1/stress-testing/evaluations/progression",
        headers=HEADERS,
        json={
            "plan_dict": plan_dict,
            "current_stage_index": 1,
            "stage_elapsed_seconds": 60,
            "current_error_rate_pct": 0.05,
        },
    )
    assert r2.status_code == 200
    assert r2.json()["verdict"]["action"] == "ADVANCE_NEXT_STAGE"
    assert r2.json()["verdict"]["recommended_next_vu"] == 1500


def test_validate_target_endpoint():
    client = TestClient(app)

    # 影子表安全通过
    r1 = client.post(
        "/api/v1/stress-testing/validate-target",
        headers=HEADERS,
        json={"target_table_or_topic": "t_order_shadow"},
    )
    assert r1.status_code == 200
    assert r1.json()["is_safe"] is True

    # 核心主表拦截
    r2 = client.post(
        "/api/v1/stress-testing/validate-target",
        headers=HEADERS,
        json={"target_table_or_topic": "t_order"},
    )
    assert r2.status_code == 200
    assert r2.json()["is_safe"] is False
    assert "致命泄漏" in r2.json()["message"]


def test_emergency_stop_endpoint():
    client = TestClient(app)
    resp = client.post(
        "/api/v1/stress-testing/emergency-stop",
        headers=HEADERS,
        json={
            "target_service": "payment-service",
            "reason": "CPU 超出 85% 紧急泄压",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "EMERGENCY_STOP_EXECUTED"
    assert data["target_service"] == "payment-service"
    assert data["disabled_rules_count"] >= 1
