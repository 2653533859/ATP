"""Scrcpy 实时视频流与控制协议单元测试。"""

import struct
from unittest.mock import MagicMock

from app.device_stream.manager import (
    ANDROID_MOTION_EVENT_ACTION_DOWN,
    ANDROID_MOTION_EVENT_ACTION_MOVE,
    ANDROID_MOTION_EVENT_ACTION_UP,
    SCRCPY_CONTROL_MSG_TYPE_INJECT_KEYCODE,
    SCRCPY_CONTROL_MSG_TYPE_INJECT_TEXT,
    SCRCPY_CONTROL_MSG_TYPE_INJECT_TOUCH_EVENT,
    ClientStream,
    ClientStreamQueue,
    DeviceInfo,
    ScrcpyDeviceManager,
    _broadcast_video_packet,
    _build_keycode_control_packet,
    _build_text_control_packet,
    _build_touch_control_packet,
    _collect_h264_nal_types,
    _sanitize_adb_input_text,
)


def test_build_touch_control_packet_binary_layout():
    """验证 Scrcpy v3.3.4 触控包 32 字节布局与压力值。"""
    pkt_down = _build_touch_control_packet(
        action=ANDROID_MOTION_EVENT_ACTION_DOWN,
        x=300,
        y=480,
        screen_width=600,
        screen_height=960,
        pressure=1.0,
    )
    assert len(pkt_down) == 32
    msg_type, action, pointer_id, x, y, w, h, pressure, _action_btn, _buttons = struct.unpack(">BBqIIHHHII", pkt_down)
    assert msg_type == SCRCPY_CONTROL_MSG_TYPE_INJECT_TOUCH_EVENT
    assert action == ANDROID_MOTION_EVENT_ACTION_DOWN
    assert pointer_id == -2
    assert (x, y, w, h) == (300, 480, 600, 960)
    assert pressure == 0xFFFF

    pkt_up = _build_touch_control_packet(
        action=ANDROID_MOTION_EVENT_ACTION_UP,
        x=300,
        y=480,
        screen_width=600,
        screen_height=960,
        pressure=0.0,
    )
    _, up_action, _, _, _, _, _, up_pressure, _, _ = struct.unpack(">BBqIIHHHII", pkt_up)
    assert up_action == ANDROID_MOTION_EVENT_ACTION_UP
    assert up_pressure == 0


def test_send_touch_event_uses_client_canvas_dimensions_and_zero_up_pressure():
    """验证 send_touch_event 使用前端传入的画布分辨率并在抬起时将压力置 0。"""
    mgr = ScrcpyDeviceManager()
    dev = DeviceInfo("TEST_SERIAL", 27183)
    dev.ready = True
    dev.running = True
    dev.screen_width = 1600
    dev.screen_height = 2560
    mock_sock = MagicMock()
    dev.control_socket = mock_sock
    mgr._devices["TEST_SERIAL"] = dev

    mgr.send_touch_event("TEST_SERIAL", ANDROID_MOTION_EVENT_ACTION_DOWN, 300, 480, width=600, height=960)
    sent_down = mock_sock.sendall.call_args[0][0]
    _, act, _, x, y, w, h, pressure, _, _ = struct.unpack(">BBqIIHHHII", sent_down)
    assert act == ANDROID_MOTION_EVENT_ACTION_DOWN
    assert (x, y, w, h) == (300, 480, 600, 960)
    assert pressure == 0xFFFF

    mgr.send_touch_event("TEST_SERIAL", ANDROID_MOTION_EVENT_ACTION_MOVE, 320, 500, width=600, height=960)
    sent_move = mock_sock.sendall.call_args[0][0]
    _, act_m, _, xm, ym, wm, hm, pressure_m, _, _ = struct.unpack(">BBqIIHHHII", sent_move)
    assert act_m == ANDROID_MOTION_EVENT_ACTION_MOVE
    assert (xm, ym, wm, hm) == (320, 500, 600, 960)
    assert pressure_m == 0xFFFF

    mgr.send_touch_event("TEST_SERIAL", ANDROID_MOTION_EVENT_ACTION_UP, 320, 500, width=600, height=960)
    sent_up = mock_sock.sendall.call_args[0][0]
    _, act_u, _, _, _, _, _, pressure_u, _, _ = struct.unpack(">BBqIIHHHII", sent_up)
    assert act_u == ANDROID_MOTION_EVENT_ACTION_UP
    assert pressure_u == 0


def test_build_keycode_and_text_packets():
    """验证按键与文本控制包的二进制格式。"""
    key_pkt = _build_keycode_control_packet(0, 4)
    assert len(key_pkt) == 14
    msg_type, action, keycode, repeat, meta = struct.unpack(">BBiii", key_pkt)
    assert msg_type == SCRCPY_CONTROL_MSG_TYPE_INJECT_KEYCODE
    assert action == 0
    assert keycode == 4
    assert repeat == 0
    assert meta == 0

    text_pkt = _build_text_control_packet("你好ATP")
    expected_bytes = "你好ATP".encode("utf-8")
    assert text_pkt[0] == SCRCPY_CONTROL_MSG_TYPE_INJECT_TEXT
    length = struct.unpack(">I", text_pkt[1:5])[0]
    assert length == len(expected_bytes)
    assert text_pkt[5:] == expected_bytes


def test_h264_init_cache_and_broadcast():
    """验证 SPS/PPS 与 IDR 关键帧缓存及客户端队列分发。"""
    dev = DeviceInfo("TEST_SERIAL", 27183)
    q = ClientStreamQueue(maxsize=10)
    dev.input_queues.append(q)

    sps_pps = b"\x00\x00\x00\x01\x67\x42\x00\x1f\x00\x00\x00\x01\x68\xce\x3c\x80"
    idr = b"\x00\x00\x00\x01\x65\x88\x84\x21"
    p_frame = b"\x00\x00\x00\x01\x41\x9a\x24"

    assert _collect_h264_nal_types(sps_pps) == {7, 8}
    assert _collect_h264_nal_types(idr) == {5}
    assert _collect_h264_nal_types(p_frame) == {1}

    _broadcast_video_packet(dev, sps_pps)
    _broadcast_video_packet(dev, idr)
    _broadcast_video_packet(dev, p_frame)

    assert len(dev.sps_pps_packets) == 1
    assert dev.last_keyframe_packet == idr
    assert q.qsize() == 3


def test_sanitize_adb_input_text_escapes_shell_meta_and_converts_spaces():
    """验证 adb shell input text 安全过滤防范命令注入并将空格转换为 %s。"""
    raw_plain = "hello world"
    assert _sanitize_adb_input_text(raw_plain) == "hello%sworld"

    raw_injection = "test; rm -rf /sdcard/* && echo $(whoami)"
    sanitized = _sanitize_adb_input_text(raw_injection)
    assert "; " not in sanitized
    assert "\\;" in sanitized
    assert "\\&\\&" in sanitized
    assert "\\$" in sanitized
    assert "%s" in sanitized


def test_client_stream_graceful_close():
    """验证 ClientStream 优雅关闭并从 dev_info 队列中解挂。"""
    dev = DeviceInfo("TEST_SERIAL", 27183)
    dev.ready = True
    dev.running = True
    client_q = ClientStreamQueue(maxsize=10)
    dev.input_queues.append(client_q)
    stream = ClientStream(dev, client_q)

    client_q.queue.put(b"packet_1")
    assert stream.get_chunk(timeout=0.1) == b"packet_1"

    stream.close()
    assert not client_q.active
    assert client_q not in dev.input_queues
    assert stream.get_chunk(timeout=0.1) is None


def test_device_cleanup_releases_port():
    """验证 _cleanup_device 彻底释放占用的端口。"""
    mgr = ScrcpyDeviceManager()
    dev = DeviceInfo("DEV_01", 27184)
    dev.ready = True
    dev.running = True
    mock_proc = MagicMock()
    mock_sock = MagicMock()
    dev.scrcpy_process = mock_proc
    dev.video_socket = mock_sock
    mgr._used_ports.add(27184)
    mgr._devices["DEV_01"] = dev

    mgr._cleanup_device("DEV_01")
    assert "DEV_01" not in mgr._devices
    assert 27184 not in mgr._used_ports
    mock_proc.terminate.assert_called_once()
    mock_sock.close.assert_called_once()
