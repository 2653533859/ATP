"""iOS WDA 反向隧道桥接服务单测 (T1.1)"""

from __future__ import annotations

import pytest

from app.services.ios_tunnel_bridge import (
    clear_ios_tunnels,
    get_ios_tunnel,
    list_active_ios_tunnels,
    register_ios_tunnel,
    release_ios_tunnel,
    simulate_forward_wda_command,
)


def test_register_and_release_ios_tunnel():
    clear_ios_tunnels()

    udid_1 = "00008101-001234567890001E"
    session_1 = register_ios_tunnel(
        udid=udid_1,
        device_name="iPhone 15 Pro",
        model="iPhone16,1",
        ios_version="17.4.1",
        agent_id="agent_mac_mini_01",
        agent_name="Mac-Mini-M2-Lab",
    )

    assert session_1.udid == udid_1
    assert session_1.device_name == "iPhone 15 Pro"
    assert 8200 <= session_1.local_tunnel_port <= 8299
    assert session_1.status == "CONNECTED"

    # 重复注册同一台设备应当复用端口并更新元数据
    session_re = register_ios_tunnel(
        udid=udid_1,
        device_name="iPhone 15 Pro (Updated)",
        model="iPhone16,1",
        ios_version="17.5.0",
        agent_id="agent_mac_mini_01",
        agent_name="Mac-Mini-M2-Lab",
    )
    assert session_re.local_tunnel_port == session_1.local_tunnel_port
    assert session_re.ios_version == "17.5.0"

    # 查验列表
    tunnels = list_active_ios_tunnels()
    assert len(tunnels) == 1
    assert tunnels[0]["udid"] == udid_1

    # 释放设备
    released = release_ios_tunnel(udid_1)
    assert released is True
    assert get_ios_tunnel(udid_1) is None
    assert len(list_active_ios_tunnels()) == 0


def test_forward_wda_command():
    clear_ios_tunnels()

    udid = "00008101-009988776655001E"
    register_ios_tunnel(
        udid=udid,
        device_name="iPhone 14",
        model="iPhone15,2",
        ios_version="16.6",
        agent_id="agent_mac_studio",
        agent_name="Studio-Lab-02",
    )

    # 1. 验证 /status 指令
    status_resp = simulate_forward_wda_command(udid, "/status")
    assert status_resp["value"]["ready"] is True
    assert status_resp["value"]["os"]["name"] == "iOS"

    # 2. 验证 /screenshot 指令
    shot_resp = simulate_forward_wda_command(udid, "/screenshot")
    assert "value" in shot_resp
    assert len(shot_resp["value"]) > 20

    # 3. 验证设备释放后抛出异常
    release_ios_tunnel(udid)
    with pytest.raises(ValueError, match="未找到设备 UDID"):
        simulate_forward_wda_command(udid, "/status")
