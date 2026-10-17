"""生产流量录制集管理与回放检索 REST API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.traffic_mirror_sampler import get_global_mirror_buffer

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_app_and_buffer():
    buf = get_global_mirror_buffer()
    buf.clear()
    mock_user = User(id=1, email="replay_qa@example.com", username="replay_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    yield
    app.dependency_overrides.clear()
    buf.clear()


def test_sanitize_endpoint():
    client = TestClient(app)
    resp = client.post(
        "/api/v1/traffic-replay/sanitize",
        json={
            "payload": {
                "mobile": "13812345678",
                "password": "ClearTextPassword!",
                "note": "测试用户",
            },
            "mode": "MASK",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sanitized_payload"]["mobile"] == "138****5678"
    assert data["sanitized_payload"]["password"] == "[MASKED_PASSWORD]"
    assert data["sanitized_payload"]["note"] == "测试用户"
    assert data["audit_trail"]["masked_field_count"] == 2


def test_mirror_ingest_and_records_lifecycle():
    client = TestClient(app)

    # 1. 尝试推送探针流量 (自动被剔除)
    probe_resp = client.post(
        "/api/v1/traffic-replay/mirror/ingest",
        json={
            "raw_traffic": {
                "method": "GET",
                "path": "/healthz",
                "status_code": 200,
            }
        },
        headers=HEADERS,
    )
    assert probe_resp.status_code == 200
    assert probe_resp.json()["should_record"] is False
    assert "剔除健康检查探针" in probe_resp.json()["reason"]

    # 2. 推送有效业务请求 (100% 采样)
    order_raw = {
        "trace_id": "tr_order_api_001",
        "method": "POST",
        "path": "/api/v1/orders/submit",
        "status_code": 200,
        "request_body": {"phone": "13900001111", "amount": 100},
        "response_body": {"code": 200, "order_id": "OD_123"},
    }
    ingest_resp = client.post(
        "/api/v1/traffic-replay/mirror/ingest",
        json={
            "raw_traffic": order_raw,
            "criteria": {"sample_rate": 1.0, "auto_sanitize": True},
        },
        headers=HEADERS,
    )
    assert ingest_resp.status_code == 200
    ingest_data = ingest_resp.json()
    assert ingest_data["should_record"] is True
    rec_id = ingest_data["item"]["record_id"]
    assert rec_id.startswith("trf_")

    # 3. 查询流量录制列表
    list_resp = client.get("/api/v1/traffic-replay/records", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
    assert list_resp.json()["records"][0]["record_id"] == rec_id

    # 4. 获取单条流量详情
    get_resp = client.get(f"/api/v1/traffic-replay/record/{rec_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["record"]["record_id"] == rec_id
    assert get_resp.json()["record"]["request_body"]["phone"] == "139****1111"

    # 5. 查验监控指标
    metrics_resp = client.get("/api/v1/traffic-replay/metrics", headers=HEADERS)
    assert metrics_resp.status_code == 200
    assert metrics_resp.json()["metrics"]["total_received"] == 2
    assert metrics_resp.json()["metrics"]["probes_filtered"] == 1
    assert metrics_resp.json()["metrics"]["recorded_count"] == 1

    # 6. 批量调度回放
    replay_resp = client.post(
        "/api/v1/traffic-replay/batch-replay",
        json={
            "record_ids": [rec_id, "non_existent_rec"],
            "target_host": "http://127.0.0.1:8000",
            "concurrency": 2,
        },
        headers=HEADERS,
    )
    assert replay_resp.status_code == 200
    tasks = replay_resp.json()["dispatched_tasks"]
    assert len(tasks) == 2
    assert tasks[0]["status"] == "DISPATCHED"
    assert tasks[1]["status"] == "RECORD_NOT_FOUND"

    # 7. 清空缓冲区
    clear_resp = client.post("/api/v1/traffic-replay/clear", headers=HEADERS)
    assert clear_resp.status_code == 200
    assert client.get("/api/v1/traffic-replay/records", headers=HEADERS).json()["total"] == 0


def test_record_not_found():
    client = TestClient(app)
    resp = client.get("/api/v1/traffic-replay/record/trf_non_existent", headers=HEADERS)
    assert resp.status_code == 404


def test_noise_rule_and_diff_evaluate_endpoints():
    client = TestClient(app)

    # 1. 测试在线规则命中
    rule_resp = client.post(
        "/api/v1/traffic-replay/noise-rule/test",
        json={
            "rule": {
                "name": "忽略时间戳",
                "noise_type": "TIMESTAMP",
                "path_pattern": "*.created_at",
            },
            "test_json_path": "$.data.created_at",
            "test_baseline_value": "2026-10-17T10:00:00Z",
            "test_replayed_value": "2026-10-17T10:00:01Z",
        },
        headers=HEADERS,
    )
    assert rule_resp.status_code == 200
    assert rule_resp.json()["matched"] is True

    # 2. 一站式比对与裁决
    base_body = {"order_id": "OD_1", "created_at": "12:00:00", "amount": 100}
    replayed_body = {"order_id": "OD_1", "created_at": "12:00:05", "amount": 105}

    eval_resp = client.post(
        "/api/v1/traffic-replay/diff-evaluate",
        json={
            "record_id": "rec_eval_test",
            "baseline_status_code": 200,
            "baseline_body": base_body,
            "replayed_status_code": 200,
            "replayed_body": replayed_body,
            "custom_rules": [
                {
                    "name": "忽略时间戳",
                    "path_pattern": "*.created_at",
                }
            ],
        },
        headers=HEADERS,
    )
    assert eval_resp.status_code == 200
    data = eval_resp.json()
    assert data["suppressed_report"]["effective_diff_count"] == 1
    assert data["evaluation_result"]["consistency_score"] == 95.0
    assert data["evaluation_result"]["verdict"] == "WARN_PERMISSIVE"
