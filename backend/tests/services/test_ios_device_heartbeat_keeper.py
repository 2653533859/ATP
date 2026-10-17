"""iOS 设备心跳保活与巡检探针服务单测 (T1.2)"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.ios_device_heartbeat_keeper import (
    clear_heartbeat_records,
    get_heartbeat_record,
    list_heartbeat_records,
    record_ios_heartbeat,
    sweep_ios_heartbeats,
    trigger_wda_self_healing,
)


def test_record_and_update_heartbeat():
    clear_heartbeat_records()

    udid = "00008101-001122334455667E"
    agent_id = "agent_mac_m3"

    # 1. 初始正常心跳
    rec = record_ios_heartbeat(
        udid=udid,
        agent_id=agent_id,
        battery_level=92,
        battery_charging=True,
        temperature_celsius=29.2,
        wda_alive=True,
    )
    assert rec.status == "ONLINE"
    assert rec.battery_level == 92
    assert rec.wda_alive is True

    # 2. 上报 WDA 异常
    rec_err = record_ios_heartbeat(
        udid=udid,
        agent_id=agent_id,
        battery_level=91,
        wda_alive=False,
    )
    assert rec_err.status == "WDA_UNHEALTHY"
    assert rec_err.wda_alive is False

    records = list_heartbeat_records()
    assert len(records) == 1


def test_sweep_heartbeats_timeout():
    clear_heartbeat_records()

    udid_active = "00008101-ACTIVE-DEVICE"
    udid_stale = "00008101-STALE-DEVICE"

    now = datetime.now(timezone.utc)

    # 活跃设备
    record_ios_heartbeat(udid=udid_active, agent_id="agent_1")

    # 超时设备 (手动设置 last_heartbeat_at 为 30 秒前)
    stale_rec = record_ios_heartbeat(udid=udid_stale, agent_id="agent_1")
    stale_time = (now - timedelta(seconds=30)).isoformat()
    stale_rec.last_heartbeat_at = stale_time

    # 巡检
    offline_list = sweep_ios_heartbeats(timeout_seconds=15.0, now=now)
    assert udid_stale in offline_list
    assert udid_active not in offline_list

    stale_check = get_heartbeat_record(udid_stale)
    assert stale_check is not None and stale_check.status == "OFFLINE"
    active_check = get_heartbeat_record(udid_active)
    assert active_check is not None and active_check.status == "ONLINE"


def test_wda_self_healing():
    clear_heartbeat_records()

    udid = "00008101-HEALING-DEVICE"
    record_ios_heartbeat(udid=udid, agent_id="agent_lab", wda_alive=False)
    rec_pre = get_heartbeat_record(udid)
    assert rec_pre is not None and rec_pre.status == "WDA_UNHEALTHY"

    # 触发自愈
    heal_res = trigger_wda_self_healing(udid)
    assert heal_res["result"] == "SUCCESS"
    rec_post = get_heartbeat_record(udid)
    assert rec_post is not None and rec_post.status == "ONLINE"
    assert rec_post.wda_alive is True
