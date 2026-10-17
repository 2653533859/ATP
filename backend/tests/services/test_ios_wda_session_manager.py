"""WDA 会话代理与生命周期初始化预热服务单测 (T2.2)"""

from __future__ import annotations

import pytest

from app.services.ios_device_heartbeat_keeper import (
    clear_heartbeat_records,
    record_ios_heartbeat,
)
from app.services.ios_lease_scheduler import (
    acquire_ios_lease,
    clear_ios_leases,
)
from app.services.ios_tunnel_bridge import (
    clear_ios_tunnels,
    register_ios_tunnel,
)
from app.services.ios_wda_session_manager import (
    capture_wda_screenshot,
    clear_wda_sessions,
    create_or_warmup_wda_session,
    dispatch_touch_gesture,
    get_wda_session,
    list_wda_sessions,
    teardown_wda_session,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_ios_tunnels()
    clear_heartbeat_records()
    clear_ios_leases()
    clear_wda_sessions()
    yield
    clear_ios_tunnels()
    clear_heartbeat_records()
    clear_ios_leases()
    clear_wda_sessions()


def test_wda_session_lifecycle():
    udid = "00008101-WDA-SESSION-01"
    register_ios_tunnel(
        udid=udid,
        device_name="iPhone 15",
        model="iPhone15,4",
        ios_version="17.0",
        agent_id="agent_mac_01",
        agent_name="Mac-Mini",
    )
    record_ios_heartbeat(udid=udid, agent_id="agent_mac_01", wda_alive=True)

    # 1. 无租约时尝试创建 WDA 会话应当被拒绝
    with pytest.raises(PermissionError, match="租约凭据无效"):
        create_or_warmup_wda_session(udid=udid, lease_token="invalid_token")

    # 2. 正常申请租约后初始化 WDA 会话
    lease = acquire_ios_lease(udid=udid, owner_id="user_1", owner_label="Tester-1")
    sess = create_or_warmup_wda_session(
        udid=udid,
        lease_token=lease.lease_token,
        bundle_id="com.example.demoapp",
    )
    assert sess.udid == udid
    assert sess.bundle_id == "com.example.demoapp"
    assert sess.status == "ACTIVE"
    assert get_wda_session(udid) is not None
    assert len(list_wda_sessions()) == 1

    # 3. 屏幕截图
    shot_b64 = capture_wda_screenshot(udid=udid, session_id=sess.session_id)
    assert len(shot_b64) > 10

    # 4. 触控手势 (Tap, Swipe, Home)
    tap_res = dispatch_touch_gesture(udid=udid, session_id=sess.session_id, action="tap", x=120, y=240)
    assert tap_res["status"] == "SUCCESS"
    assert tap_res["coords"] == [120, 240]

    swipe_res = dispatch_touch_gesture(
        udid=udid,
        session_id=sess.session_id,
        action="swipe",
        x=200,
        y=600,
        end_x=200,
        end_y=200,
        duration_ms=400,
    )
    assert swipe_res["status"] == "SUCCESS"

    home_res = dispatch_touch_gesture(udid=udid, session_id=sess.session_id, action="home")
    assert home_res["status"] == "SUCCESS"

    # 非法动作
    with pytest.raises(ValueError, match="不支持的手势动作类型"):
        dispatch_touch_gesture(udid=udid, session_id=sess.session_id, action="invalid_action")

    # 5. 优雅关闭会话
    closed = teardown_wda_session(udid=udid, session_id=sess.session_id)
    assert closed is True
    assert get_wda_session(udid) is None
    assert len(list_wda_sessions()) == 0
