"""物理真机集群调度与容量预测 REST API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.fleet_concurrency_router import clear_routing_state
from app.services.fleet_health_telemetry import clear_fleet_telemetry

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_app_and_state():
    clear_fleet_telemetry()
    clear_routing_state()
    mock_user = User(id=1, email="sched_qa@example.com", username="sched_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    yield
    app.dependency_overrides.clear()
    clear_fleet_telemetry()
    clear_routing_state()


def test_telemetry_reporting_and_listing():
    client = TestClient(app)

    # 1. 上报 iOS 真机遥测
    rep_resp = client.post(
        "/api/v1/scheduler/telemetry/report",
        json={
            "device_id": "00008101-IPHONE-API-01",
            "platform": "ios",
            "battery_temperature_c": 32.5,
            "battery_level_percent": 85,
            "battery_state": "CHARGING",
            "cpu_usage_percent": 18.0,
            "current_concurrency": 0,
            "max_concurrency": 2,
            "tunnel_rtt_ms": 12.0,
        },
        headers=HEADERS,
    )
    assert rep_resp.status_code == 200
    telemetry = rep_resp.json()["telemetry"]
    assert telemetry["device_id"] == "00008101-IPHONE-API-01"
    assert telemetry["health_score"] >= 90.0
    assert telemetry["health_status"] == "HEALTHY"

    # 2. 查询设备列表
    list_resp = client.get("/api/v1/scheduler/devices/telemetry", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 按平台过滤
    ios_resp = client.get("/api/v1/scheduler/devices/telemetry?platform=ios", headers=HEADERS)
    assert ios_resp.status_code == 200
    assert len(ios_resp.json()["devices"]) == 1

    and_resp = client.get("/api/v1/scheduler/devices/telemetry?platform=android", headers=HEADERS)
    assert and_resp.status_code == 200
    assert len(and_resp.json()["devices"]) == 0


def test_dispatch_and_release_flow():
    client = TestClient(app)

    # 准备一台健康设备
    client.post(
        "/api/v1/scheduler/telemetry/report",
        json={
            "device_id": "00008101-IPHONE-AUTO-02",
            "platform": "ios",
            "battery_temperature_c": 31.0,
            "battery_level_percent": 90,
            "current_concurrency": 0,
            "max_concurrency": 2,
        },
        headers=HEADERS,
    )

    # 1. 提交调度请求
    dispatch_resp = client.post(
        "/api/v1/scheduler/route/dispatch",
        json={
            "task_id": "task_checkout_ios_101",
            "target_platform": "ios",
            "task_name": "收银台支付测试",
            "priority": "HIGH",
        },
        headers=HEADERS,
    )
    assert dispatch_resp.status_code == 200
    assert dispatch_resp.json()["is_allocated"] is True
    decision = dispatch_resp.json()["decision"]
    assert decision["selected_device_id"] == "00008101-IPHONE-AUTO-02"
    assert decision["status"] == "ROUTED"
    decision_id = decision["decision_id"]

    # 2. 释放租约
    rel_resp = client.post(
        "/api/v1/scheduler/route/release",
        json={
            "device_id": "00008101-IPHONE-AUTO-02",
            "task_id": "task_checkout_ios_101",
        },
        headers=HEADERS,
    )
    assert rel_resp.status_code == 200
    assert rel_resp.json()["released"] is True

    # 3. 查验单条决策记录与历史
    get_dec_resp = client.get(f"/api/v1/scheduler/routing/{decision_id}", headers=HEADERS)
    assert get_dec_resp.status_code == 200
    assert get_dec_resp.json()["decision"]["decision_id"] == decision_id

    hist_resp = client.get("/api/v1/scheduler/routing/history", headers=HEADERS)
    assert hist_resp.status_code == 200
    assert hist_resp.json()["total"] >= 1


def test_capacity_summary():
    client = TestClient(app)

    # 上报一台健康设备和一台过热设备
    client.post(
        "/api/v1/scheduler/telemetry/report",
        json={
            "device_id": "dev_healthy_ios",
            "platform": "ios",
            "battery_temperature_c": 30.0,
            "battery_level_percent": 80,
            "current_concurrency": 1,
            "max_concurrency": 2,
            "tunnel_rtt_ms": 15.0,
        },
        headers=HEADERS,
    )
    client.post(
        "/api/v1/scheduler/telemetry/report",
        json={
            "device_id": "dev_hot_and",
            "platform": "android",
            "battery_temperature_c": 44.0,
            "battery_level_percent": 70,
            "current_concurrency": 0,
            "max_concurrency": 2,
            "tunnel_rtt_ms": 25.0,
        },
        headers=HEADERS,
    )

    cap_resp = client.get("/api/v1/scheduler/capacity/summary", headers=HEADERS)
    assert cap_resp.status_code == 200
    cap = cap_resp.json()
    assert cap["total_devices"] == 2
    assert cap["healthy_count"] == 1
    assert cap["overheated_count"] == 1
    assert cap["total_capacity"] == 4
    assert cap["used_concurrency"] == 1
    assert cap["available_capacity"] == 3
    assert cap["cluster_averages"]["avg_temperature_c"] == 37.0


def test_routing_not_found():
    client = TestClient(app)
    resp = client.get("/api/v1/scheduler/routing/non_existent_id", headers=HEADERS)
    assert resp.status_code == 404


def test_backpressure_endpoints():
    client = TestClient(app)

    # 1. 触发自适应并发窗口计算
    adj_resp = client.post(
        "/api/v1/scheduler/backpressure/adjust",
        json={
            "queue_depth": 10,
            "average_wait_latency_ms": 120.0,
        },
        headers=HEADERS,
    )
    assert adj_resp.status_code == 200
    snap = adj_resp.json()["snapshot"]
    assert "current_window_size" in snap
    assert snap["level"] in ("NORMAL", "LIGHT_THROTTLING", "HEAVY_BACKPRESSURE", "OVERFLOW_REJECTION")

    # 2. 查询当前流控状态
    status_resp = client.get("/api/v1/scheduler/backpressure/status", headers=HEADERS)
    assert status_resp.status_code == 200
    assert "current_window_size" in status_resp.json()["status"]

    # 3. 查询快照历史
    snap_list_resp = client.get("/api/v1/scheduler/backpressure/snapshots", headers=HEADERS)
    assert snap_list_resp.status_code == 200
    assert snap_list_resp.json()["total"] >= 1


def test_storm_guard_endpoints():
    client = TestClient(app)

    # 1. 正常评估通过
    eval_resp = client.post(
        "/api/v1/scheduler/storm/evaluate",
        json={"task_id": "task_eval_101"},
        headers=HEADERS,
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()["is_allowed"] is True
    assert eval_resp.json()["verdict"] == "ALLOW"

    # 2. 查询断路器状态
    status_resp = client.get("/api/v1/scheduler/storm/status", headers=HEADERS)
    assert status_resp.status_code == 200
    assert status_resp.json()["status"]["state"] == "CLOSED"

    # 3. 手动复位断路器
    reset_resp = client.post("/api/v1/scheduler/storm/reset", headers=HEADERS)
    assert reset_resp.status_code == 200
    assert "复位至正常" in reset_resp.json()["message"]


def test_scheduler_evidence_endpoints():
    client = TestClient(app)

    # 1. 签发容量快照存证证书
    sign_resp = client.post(
        "/api/v1/scheduler/evidence/sign",
        json={
            "artifact_type": "CAPACITY_SNAPSHOT",
            "artifact_id": "snap_test_cap_01",
        },
        headers=HEADERS,
    )
    assert sign_resp.status_code == 200
    cert = sign_resp.json()["certificate"]
    cert_id = cert["certificate_id"]
    assert len(cert["evidence_sha256"]) == 64
    assert len(cert["hmac_signature"]) == 64

    # 2. 在线验签
    verify_resp = client.post(
        "/api/v1/scheduler/evidence/verify",
        json={"certificate_id": cert_id},
        headers=HEADERS,
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["is_valid"] is True
    assert verify_resp.json()["verdict"] == "VALID"

    # 3. 证书列表与单张详情
    get_cert_resp = client.get(f"/api/v1/scheduler/evidence/{cert_id}", headers=HEADERS)
    assert get_cert_resp.status_code == 200
    assert get_cert_resp.json()["certificate"]["certificate_id"] == cert_id

    list_certs_resp = client.get("/api/v1/scheduler/evidence/list", headers=HEADERS)
    assert list_certs_resp.status_code == 200
    assert list_certs_resp.json()["total"] >= 1
