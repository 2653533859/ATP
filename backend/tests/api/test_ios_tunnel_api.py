"""iOS 设备反向 WebSocket 隧道与状态管理 API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User
from app.services.ios_device_heartbeat_keeper import clear_heartbeat_records
from app.services.ios_tunnel_bridge import clear_ios_tunnels

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_app_and_state():
    clear_ios_tunnels()
    clear_heartbeat_records()

    mock_user = User(id=1, email="ios_engineer@example.com", username="ios_eng", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    yield
    app.dependency_overrides.clear()
    clear_ios_tunnels()
    clear_heartbeat_records()


def test_ios_tunnel_full_lifecycle_api():
    client = TestClient(app)

    udid = "00008101-002233445566778E"

    # 1. 注册设备反向隧道
    reg_resp = client.post(
        "/api/v1/ios/tunnel/register",
        json={
            "udid": udid,
            "device_name": "iPhone 15 Pro Max",
            "model": "iPhone16,2",
            "ios_version": "17.4",
            "agent_id": "mac_agent_01",
            "agent_name": "Mac-Studio-Rack-A",
            "remote_wda_port": 8100,
        },
        headers=HEADERS,
    )
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    assert reg_data["tunnel"]["udid"] == udid
    assert 8200 <= reg_data["tunnel"]["local_tunnel_port"] <= 8299
    assert reg_data["tunnel"]["status"] == "CONNECTED"

    # 2. 上报心跳数据
    hb_resp = client.post(
        "/api/v1/ios/tunnel/heartbeat",
        json={
            "udid": udid,
            "agent_id": "mac_agent_01",
            "battery_level": 88,
            "battery_charging": True,
            "temperature_celsius": 30.5,
            "wda_alive": True,
        },
        headers=HEADERS,
    )
    assert hb_resp.status_code == 200
    assert hb_resp.json()["heartbeat"]["battery_level"] == 88

    # 3. 查询真机列表
    list_resp = client.get("/api/v1/ios/tunnel/devices", headers=HEADERS)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
    dev = list_resp.json()["devices"][0]
    assert dev["udid"] == udid
    assert dev["battery_level"] == 88
    assert dev["health_status"] == "ONLINE"

    # 4. 查询单台设备详情
    get_resp = client.get(f"/api/v1/ios/tunnel/device/{udid}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["device"]["udid"] == udid

    # 5. 代理下发 WDA 指令 (/status)
    wda_resp = client.post(
        "/api/v1/ios/tunnel/wda/forward",
        json={
            "udid": udid,
            "command_path": "/status",
            "method": "GET",
        },
        headers=HEADERS,
    )
    assert wda_resp.status_code == 200
    assert wda_resp.json()["response"]["value"]["ready"] is True

    # 6. 自愈拉起 WDA
    heal_resp = client.post(
        "/api/v1/ios/tunnel/wda/heal",
        json={"udid": udid},
        headers=HEADERS,
    )
    assert heal_resp.status_code == 200
    assert heal_resp.json()["result"] == "SUCCESS"

    # 7. 巡检
    sweep_resp = client.post(
        "/api/v1/ios/tunnel/sweep",
        json={"timeout_seconds": 60.0},
        headers=HEADERS,
    )
    assert sweep_resp.status_code == 200
    assert isinstance(sweep_resp.json()["offline_udids"], list)

    # 8. 注销并释放设备隧道
    del_resp = client.delete(f"/api/v1/ios/tunnel/{udid}", headers=HEADERS)
    assert del_resp.status_code == 200
    empty_list = client.get("/api/v1/ios/tunnel/devices", headers=HEADERS)
    assert empty_list.json()["total"] == 0


def test_ios_tunnel_phase2_endpoints():
    client = TestClient(app)

    udid = "00008101-PHASE2-TEST-UDID"

    # 1. 前置注册设备
    client.post(
        "/api/v1/ios/tunnel/register",
        json={
            "udid": udid,
            "device_name": "iPhone 15 Pro",
            "model": "iPhone16,1",
            "ios_version": "17.4",
            "agent_id": "mac_agent_phase2",
            "agent_name": "Mac-Studio",
        },
        headers=HEADERS,
    )

    # 2. 申请独占租约
    acq_resp = client.post(
        "/api/v1/ios/tunnel/lease/acquire",
        json={
            "udid": udid,
            "purpose": "automated_integration_test",
            "ttl_seconds": 180,
        },
        headers=HEADERS,
    )
    assert acq_resp.status_code == 200
    token = acq_resp.json()["lease"]["lease_token"]
    assert token.startswith("ios_lease_")

    # 3. 租约保活续期
    hb_resp = client.post(
        "/api/v1/ios/tunnel/lease/heartbeat",
        json={"udid": udid, "lease_token": token, "additional_ttl_seconds": 300},
        headers=HEADERS,
    )
    assert hb_resp.status_code == 200

    # 4. 预热创建 WDA Session
    wda_sess_resp = client.post(
        "/api/v1/ios/tunnel/wda/session/warmup",
        json={
            "udid": udid,
            "lease_token": token,
            "bundle_id": "com.apple.Preferences",
        },
        headers=HEADERS,
    )
    assert wda_sess_resp.status_code == 200
    session_id = wda_sess_resp.json()["session"]["session_id"]

    # 5. 获取屏幕截图
    shot_resp = client.get(
        f"/api/v1/ios/tunnel/wda/screenshot/{udid}?session_id={session_id}",
        headers=HEADERS,
    )
    assert shot_resp.status_code == 200
    assert "screenshot_base64" in shot_resp.json()

    # 6. 下发手势动作
    tap_resp = client.post(
        "/api/v1/ios/tunnel/wda/gesture",
        json={
            "udid": udid,
            "session_id": session_id,
            "action": "tap",
            "x": 100.0,
            "y": 200.0,
        },
        headers=HEADERS,
    )
    assert tap_resp.status_code == 200

    # 7. 跨端池容量与自动调度
    cap_resp = client.get("/api/v1/ios/tunnel/pool/capacity", headers=HEADERS)
    assert cap_resp.status_code == 200
    assert cap_resp.json()["capacity"]["total_devices"] >= 1

    # 8. 释放租约
    rel_resp = client.post(
        "/api/v1/ios/tunnel/lease/release",
        json={"udid": udid, "lease_token": token},
        headers=HEADERS,
    )
    assert rel_resp.status_code == 200


def test_ios_tunnel_crash_and_syslog_endpoints():
    client = TestClient(app)

    udid = "00008101-CRASH-TEST-API"

    # 1. 上报 Syslog 流
    syslog_resp = client.post(
        "/api/v1/ios/tunnel/syslog/ingest",
        json={
            "udid": udid,
            "lines": [
                "[12:00:01] SpringBoard[52]: User tap home",
                "[12:00:02] TargetApp[100]: Memory warning <Error>",
            ],
        },
        headers=HEADERS,
    )
    assert syslog_resp.status_code == 200
    assert syslog_resp.json()["ingested_lines"] == 2

    # 2. 读取 Syslog 缓冲
    get_syslog_resp = client.get(f"/api/v1/ios/tunnel/syslog/{udid}", headers=HEADERS)
    assert get_syslog_resp.status_code == 200
    assert get_syslog_resp.json()["total"] == 2

    # 3. 上报 Crash 报告
    crash_text = """
    Process: MyApp [2048]
    Identifier: com.example.myapp
    Exception Type: EXC_CRASH (SIGABRT)
    Termination Reason: SIGNAL 6 Abort trap: 6
    Triggered by Thread: 0
    Thread 0 Crashed:
    0   MyApp 0x0000000100001234 main + 20
    """
    crash_resp = client.post(
        "/api/v1/ios/tunnel/crash/report",
        json={
            "udid": udid,
            "raw_crash_text": crash_text,
            "run_id": "run_test_777",
            "step_index": 2,
        },
        headers=HEADERS,
    )
    assert crash_resp.status_code == 200
    crash_id = crash_resp.json()["crash"]["crash_id"]

    # 4. 获取单条崩溃详情
    get_crash_resp = client.get(f"/api/v1/ios/tunnel/crash/{crash_id}", headers=HEADERS)
    assert get_crash_resp.status_code == 200
    assert get_crash_resp.json()["crash"]["process_name"] == "MyApp"

    # 5. 查询全量崩溃列表
    list_crashes_resp = client.get(f"/api/v1/ios/tunnel/crashes?run_id=run_test_777", headers=HEADERS)
    assert list_crashes_resp.status_code == 200
    assert list_crashes_resp.json()["total"] == 1
