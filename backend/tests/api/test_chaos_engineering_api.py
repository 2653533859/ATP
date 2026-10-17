"""全链路分布式混沌工程与弹性韧性攻防演练 REST API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.chaos_fault_injector_library import get_global_fault_library
from app.services.chaos_steady_state_evaluator import get_global_chaos_manager

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_app_and_state():
    lib = get_global_fault_library()
    mgr = get_global_chaos_manager()
    mock_user = User(id=1, email="chaos_qa@example.com", username="chaos_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    yield
    app.dependency_overrides.clear()
    lib.clear()
    lib._load_seed_faults()
    mgr.clear()
    mgr._load_seed_experiments()


def test_fault_rules_lifecycle():
    client = TestClient(app)

    # 1. 查询默认算子库列表
    list_resp = client.get("/api/v1/chaos-engineering/fault-rules", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 3

    # 2. 注册新故障算子
    create_resp = client.post(
        "/api/v1/chaos-engineering/fault-rule",
        json={
            "name": "数据库只读超时注入",
            "fault_type": "TIMEOUT_ABORT",
            "target_pattern": "*/db/query/*",
            "description": "模拟慢 SQL 导致只读库连接耗尽",
        },
        headers=HEADERS,
    )
    assert create_resp.status_code == 200
    rule = create_resp.json()["rule"]
    assert rule["fault_type"] == "TIMEOUT_ABORT"
    assert rule["target_pattern"] == "*/db/query/*"


def test_experiment_full_lifecycle():
    client = TestClient(app)

    # 1. 创建混沌实验
    create_resp = client.post(
        "/api/v1/chaos-engineering/experiment",
        json={
            "name": "优惠券抵扣超时熔断演练",
            "target_service": "coupon-service",
            "fault_id": "fault_pay_latency_500ms",
            "min_success_rate_pct": 95.0,
            "max_p99_latency_ms": 500.0,
            "require_probe_healthy": True,
        },
        headers=HEADERS,
    )
    assert create_resp.status_code == 200
    exp = create_resp.json()["experiment"]
    exp_id = exp["experiment_id"]
    assert exp["state"] == "CREATED"

    # 2. 查询实验列表
    list_resp = client.get("/api/v1/chaos-engineering/experiments", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 2

    # 3. 查验单条实验详情
    get_resp = client.get(f"/api/v1/chaos-engineering/experiment/{exp_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["experiment"]["experiment_id"] == exp_id

    # 4. 触发启动实验故障注入
    trig_resp = client.post(f"/api/v1/chaos-engineering/experiment/{exp_id}/trigger", headers=HEADERS)
    assert trig_resp.status_code == 200
    assert trig_resp.json()["state"] == "FAULT_INJECTING"

    # 5. 写入实时指标采样并验证稳态
    sample_resp = client.post(
        f"/api/v1/chaos-engineering/experiment/{exp_id}/sample",
        json={
            "total_requests": 1000,
            "failed_requests": 5,
            "p99_latency_ms": 220.0,
            "is_probe_healthy": True,
        },
        headers=HEADERS,
    )
    assert sample_resp.status_code == 200
    assert sample_resp.json()["is_steady"] is True
    assert sample_resp.json()["state"] == "STEADY_STATE_VERIFIED"

    # 6. 停止实验并恢复现场
    stop_resp = client.post(f"/api/v1/chaos-engineering/experiment/{exp_id}/stop", headers=HEADERS)
    assert stop_resp.status_code == 200
    assert stop_resp.json()["state"] == "STOPPED"


def test_simulate_fault_inject_endpoint():
    client = TestClient(app)

    resp = client.post(
        "/api/v1/chaos-engineering/fault-inject/simulate",
        json={
            "path": "/api/v1/stock/deduct",
            "original_status_code": 200,
            "original_body": {"stock": 100},
            "fault_id": "fault_stock_500_error",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    sim = resp.json()["simulation_result"]
    assert sim["is_fault_injected"] is True
    assert sim["effective_status_code"] == 500


def test_experiment_not_found():
    client = TestClient(app)
    resp = client.get("/api/v1/chaos-engineering/experiment/exp_non_existent", headers=HEADERS)
    assert resp.status_code == 404
