"""全链路金丝雀灰度校验与流量染色 REST API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.canary_traffic_coloration_engine import get_global_canary_manager

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_api_state():
    mock_user = User(id=1, email="canary_qa@example.com", username="canary_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    mgr = get_global_canary_manager()
    mgr.clear()
    mgr._load_seed_rules()
    yield
    app.dependency_overrides.clear()
    mgr.clear()
    mgr._load_seed_rules()


def test_list_and_create_coloration_rules():
    client = TestClient(app)

    # 1. 查询默认染色规则列表
    resp = client.get("/api/v1/canary-verification/rules", headers=HEADERS)
    assert resp.status_code == 200
    rules = resp.json()
    assert len(rules) >= 2

    # 2. 注册新规则
    create_resp = client.post(
        "/api/v1/canary-verification/rule",
        json={
            "name": "测试新版本 Header 染色规则",
            "rule_type": "HTTP_HEADER",
            "target_service": "auth-service",
            "canary_version_tag": "v2.0.0-rc2",
            "match_key": "X-Beta",
            "match_value": "true",
            "weight_pct": 20.0,
        },
        headers=HEADERS,
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["canary_version_tag"] == "v2.0.0-rc2"
    assert created["target_service"] == "auth-service"

    # 3. 错误规则类型 400 校验
    err_resp = client.post(
        "/api/v1/canary-verification/rule",
        json={
            "name": "非法类型规则",
            "rule_type": "UNKNOWN_INVALID_TYPE",
            "target_service": "auth-service",
            "canary_version_tag": "v1.0",
        },
        headers=HEADERS,
    )
    assert err_resp.status_code == 400


def test_evaluate_coloration_endpoint():
    client = TestClient(app)

    # 命中种子规则 X-Canary: true
    eval_resp = client.post(
        "/api/v1/canary-verification/evaluate-coloration",
        json={
            "headers": {"X-Canary": "true"},
            "target_service": "payment-service",
        },
        headers=HEADERS,
    )
    assert eval_resp.status_code == 200
    data = eval_resp.json()
    assert data["is_canary"] is True
    assert data["color_tag"] == "v2.1.0-canary"
    assert data["headers_to_propagate"]["X-Canary-Traffic"] == "true"


def test_compare_tracks_endpoint():
    client = TestClient(app)

    resp = client.post(
        "/api/v1/canary-verification/compare-tracks",
        json={
            "baseline_metrics": {
                "total_requests": 10000,
                "error_rate_pct": 0.1,
                "p99_latency_ms": 100.0,
            },
            "canary_metrics": {
                "total_requests": 1000,
                "error_rate_pct": 0.2,
                "p99_latency_ms": 110.0,
            },
            "target_service": "order-service",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["overall_verdict"] == "CONFORMANT"
    assert report["error_rate_diff_pct"] == 0.1


def test_emergency_rollback_endpoint():
    client = TestClient(app)

    rollback_resp = client.post(
        "/api/v1/canary-verification/rollback",
        json={
            "target_service": "payment-service",
            "reason": "金丝雀 P99 响应延迟超标 200%",
        },
        headers=HEADERS,
    )
    assert rollback_resp.status_code == 200
    res = rollback_resp.json()
    assert res["status"] == "ROLLBACK_COMPLETED"
    assert res["target_service"] == "payment-service"
    assert res["canary_traffic_weight_pct"] == 0.0
    assert res["disabled_rules_count"] >= 1
