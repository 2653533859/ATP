"""Scrcpy 实时视频流与控制协议单元测试。

覆盖 backend/app/device_stream/manager.py：
- H.264 NAL 解析与初始化包缓存；
- ClientStreamQueue / ClientStream 队列与优雅退出逻辑；
- 触控/按键/文本控制包二进制构造与 adb 文本清洗；
- 端口池、_recv_exactly、_deploy_scrcpy_server；
- ensure_device_stream / _connect_device_sync / _start_video_reader；
- create_client_stream / get_video_generator 与事件下发、资源清理。

所有涉及 socket / adbutils / subprocess / time.sleep 的路径均使用本地垫片（shim）
替换 manager 模块内的同名引用，保证用例完全确定、不依赖真实设备与真实等待。
"""

import io
import queue
import socket
import struct
import subprocess
import threading
import time
import types
from unittest.mock import MagicMock

import pytest

from app.device_stream import manager as device_stream_manager
from app.device_stream.manager import (
    ANDROID_MOTION_EVENT_ACTION_DOWN,
    ANDROID_MOTION_EVENT_ACTION_MOVE,
    ANDROID_MOTION_EVENT_ACTION_UP,
    DEVICE_JAR_PATH,
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
    _get_h264_init_packets,
    _sanitize_adb_input_text,
    _update_h264_init_cache,
)


# ---------------------------------------------------------------------------
# 测试脚手架：假 socket / 假 adb / 假 subprocess / 假时间
# ---------------------------------------------------------------------------


class _ScriptSocket:
    """按脚本逐块返回数据的假 socket；脚本元素可以是异常实例以模拟超时/断开。"""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.timeouts = []
        self.closed = False
        self.connected = None
        self.sent = []
        self.setsockopt_args = None

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def setsockopt(self, *args):
        self.setsockopt_args = args

    def connect(self, addr):
        self.connected = addr

    def recv(self, n):
        if not self._chunks:
            return b""
        item = self._chunks.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


class _RefusingSocket:
    """connect 一律失败的假 socket（模拟端口不通）。"""

    def __init__(self):
        self.closed = False

    def settimeout(self, timeout):
        pass

    def connect(self, addr):
        raise ConnectionRefusedError("模拟拒绝连接")

    def close(self):
        # close 自身也失败：覆盖 _connect_device_sync 中关闭失败被吞掉的防御分支
        self.closed = True
        raise OSError("close 失败")


class _FakeSocketFactory:
    """替换 manager.socket 的垫片：提供最小常量集与可编排的 socket() 工厂。"""

    AF_INET = socket.AF_INET
    SOCK_STREAM = socket.SOCK_STREAM
    IPPROTO_TCP = socket.IPPROTO_TCP
    TCP_NODELAY = socket.TCP_NODELAY
    timeout = socket.timeout

    def __init__(self, factory):
        self._factory = factory
        self.created = []

    def socket(self, *args):
        sock = self._factory()
        self.created.append(sock)
        return sock


class _FakeProc:
    """假 scrcpy 子进程。poll 返回 None 表示仍在运行。"""

    def __init__(self, poll_result=None, stderr=None):
        self._poll_result = poll_result
        self.stderr = stderr
        self.terminate_calls = 0

    def poll(self):
        return self._poll_result

    def terminate(self):
        self.terminate_calls += 1


class _FakeDevice:
    """假 adb 设备：记录 shell / forward / forward_remove 调用。"""

    def __init__(self, serial="FAKE_SERIAL", pkill_raises=False):
        self.serial = serial
        self.shell_calls = []
        self.forwarded = []
        self.forward_removed = []
        self._pkill_raises = pkill_raises

    def shell(self, command):
        self.shell_calls.append(command)
        if self._pkill_raises and "pkill" in command:
            raise RuntimeError("设备不支持 pkill")
        return "0"

    def forward(self, local, remote):
        self.forwarded.append((local, remote))

    def forward_remove(self, spec):
        self.forward_removed.append(spec)


def _make_adbutils_shim(device_obj=None, client_raises=None):
    """构造替换 manager.adbutils 的垫片；client_raises 非空时 AdbClient() 直接抛错。"""

    class _Client:
        def __init__(self):
            if client_raises is not None:
                raise client_raises

        def device(self, serial=None):
            return device_obj

    return types.SimpleNamespace(AdbClient=_Client)


class _RecordingSubprocess:
    """记录 subprocess.Popen / run 调用的垫片，不执行任何真实命令。"""

    PIPE = subprocess.PIPE

    def __init__(self, proc=None):
        self.proc = proc
        self.popen_calls = []
        self.run_calls = []

    def Popen(self, cmd, **kwargs):
        self.popen_calls.append((cmd, kwargs))
        return self.proc

    def run(self, args, **kwargs):
        self.run_calls.append((args, kwargs))
        return types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")


def _make_time_shim():
    """禁用真实 sleep 的 time 垫片（monotonic 保留真实实现）。"""
    return types.SimpleNamespace(sleep=lambda seconds: None, monotonic=time.monotonic)


def _socket_sequence(*socks):
    """按顺序返回预置假 socket 的工厂闭包。"""
    pending = list(socks)

    def _factory():
        return pending.pop(0)

    return _factory


def _packet_header(pkt_len: int) -> bytes:
    """构造非 raw 模式的 12 字节长度前缀包头（仅 [8:12] 存放包长）。"""
    return b"\x00" * 8 + struct.pack(">I", pkt_len)


def _register_ready_device(mgr: ScrcpyDeviceManager, serial: str, local_port: int = 0) -> DeviceInfo:
    """注册一个 ready+running 的设备，避免 ensure_device_stream 启动真实连接线程。"""
    dev = DeviceInfo(serial, local_port)
    dev.ready = True
    dev.running = True
    mgr._devices[serial] = dev
    return dev


def _prepare_connect_success_env(monkeypatch, mgr, serial, codec_header, name=b"PIXEL-7", leading_fakes=()):
    """为 _connect_device_sync 成功路径搭建全垫片环境并返回关键对象。

    leading_fakes 会被 socket 工厂先于正式 video socket 消费，用于构造多轮重试场景。
    """
    name_bytes = name + b"\x00" * (64 - len(name))
    video_fake = _ScriptSocket([b"D", name_bytes, codec_header])
    ctrl_fake = _ScriptSocket([])
    fake_socket = _FakeSocketFactory(_socket_sequence(*leading_fakes, video_fake, ctrl_fake))
    monkeypatch.setattr(device_stream_manager, "socket", fake_socket)

    device = _FakeDevice(serial=serial, pkill_raises=True)
    monkeypatch.setattr(device_stream_manager, "adbutils", _make_adbutils_shim(device))

    proc = _FakeProc()
    fake_subprocess = _RecordingSubprocess(proc)
    monkeypatch.setattr(device_stream_manager, "subprocess", fake_subprocess)

    monkeypatch.setattr(device_stream_manager, "time", _make_time_shim())
    monkeypatch.setattr(mgr, "_deploy_scrcpy_server", lambda dev: True)
    reader_calls = []
    monkeypatch.setattr(mgr, "_start_video_reader", lambda info: reader_calls.append(info))
    return types.SimpleNamespace(
        device=device,
        video_fake=video_fake,
        ctrl_fake=ctrl_fake,
        proc=proc,
        subprocess=fake_subprocess,
        reader_calls=reader_calls,
        socket_factory=fake_socket,
    )


@pytest.fixture(autouse=True)
def _join_leaked_reader_threads():
    """autouse：用例结束后回收可能残留的 ScrcpyReader 线程，保证逐文件独立运行稳定。"""
    yield
    for thread in threading.enumerate():
        if thread.name.startswith("ScrcpyReader-"):
            thread.join(timeout=5)
            assert not thread.is_alive(), f"读流线程未退出: {thread.name}"


# ---------------------------------------------------------------------------
# 原有用例（保留）
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# H.264 NAL 解析与初始化缓存
# ---------------------------------------------------------------------------


def test_collect_h264_nal_types_handles_start_code_variants_and_fallbacks():
    """验证 3/4 字节起始码、多 NAL、无起始码回退与空数据等边界。"""
    # 单个 3 字节起始码
    assert _collect_h264_nal_types(b"\x00\x00\x01\x65") == {5}
    # 完全没有起始码时回退取首字节 NAL 类型
    assert _collect_h264_nal_types(b"\x41\x9a\x24\x99") == {1}
    # 空数据返回空集合
    assert _collect_h264_nal_types(b"") == set()
    # 仅以起始码结尾：nal_index 越界被跳过，最终走首字节回退
    assert _collect_h264_nal_types(b"\x00\x00\x00\x01") == {0}
    # 混合 4 字节与 3 字节起始码的多 NAL 数据
    multi = b"\x00\x00\x00\x01\x67" + b"\x00\x00\x00\x01\x68" + b"\x00\x00\x01\x65"
    assert _collect_h264_nal_types(multi) == {7, 8, 5}


def test_update_h264_init_cache_resets_on_sps_and_dedupes():
    """验证 SPS 到来时清空旧缓存、PPS 追加去重、IDR 记录关键帧。"""
    dev = DeviceInfo("S1", 0)
    sps_pps = b"\x00\x00\x00\x01\x67\x42\x00\x1f\x00\x00\x00\x01\x68\xce\x3c\x80"
    idr = b"\x00\x00\x00\x01\x65\x88\x84\x21"

    assert _update_h264_init_cache(dev, sps_pps) == {7, 8}
    assert dev.sps_pps_packets == [sps_pps]

    assert _update_h264_init_cache(dev, idr) == {5}
    assert dev.last_keyframe_packet == idr
    assert dev.sps_pps_packets == [sps_pps]  # IDR 不进入 SPS/PPS 缓存

    # 重复的同一 SPS/PPS 包不重复追加
    _update_h264_init_cache(dev, sps_pps)
    assert dev.sps_pps_packets == [sps_pps]

    # 新 SPS 到来重置 sps_pps 与关键帧缓存
    new_sps = b"\x00\x00\x00\x01\x67\x64\x00\x28"
    _update_h264_init_cache(dev, new_sps)
    assert dev.sps_pps_packets == [new_sps]
    assert dev.last_keyframe_packet is None

    # 纯 P 帧不改变任何缓存
    assert _update_h264_init_cache(dev, b"\x00\x00\x00\x01\x41\x9a\x24") == {1}
    assert dev.sps_pps_packets == [new_sps]

    # SPS 与 IDR 合并在同一包：既进 sps_pps 又成为关键帧
    comb = b"\x00\x00\x00\x01\x67\x42\x00\x1f\x00\x00\x00\x01\x65\x22"
    assert _update_h264_init_cache(dev, comb) == {7, 5}
    assert dev.sps_pps_packets == [comb]
    assert dev.last_keyframe_packet == comb

    # 纯 PPS 包（不含 SPS）重复到达：命中"已存在则不重复追加"分支
    dev2 = DeviceInfo("S2", 0)
    pps_only = b"\x00\x00\x00\x01\x68\xce\x3c\x80"
    _update_h264_init_cache(dev2, pps_only)
    _update_h264_init_cache(dev2, pps_only)
    assert dev2.sps_pps_packets == [pps_only]
    assert dev2.last_keyframe_packet is None


def test_get_h264_init_packets_dedupes_and_skips_empty():
    """验证初始化包去重、跳过空包且关键帧排在最后。"""
    dev = DeviceInfo("S1", 0)
    sps = b"\x00\x00\x00\x01\x67\x42\x00\x1f"
    idr = b"\x00\x00\x00\x01\x65\x88\x84\x21"

    # 空包被跳过、重复包只保留一份、空关键帧不计入
    dev.sps_pps_packets = [b"", sps, sps]
    dev.last_keyframe_packet = b""
    assert _get_h264_init_packets(dev) == [sps]

    # 关键帧不在缓存中时追加在最后
    dev.last_keyframe_packet = idr
    assert _get_h264_init_packets(dev) == [sps, idr]

    # 关键帧与缓存内已有包相同时不重复追加
    dev.last_keyframe_packet = sps
    assert _get_h264_init_packets(dev) == [sps]

    # 空设备返回空列表
    assert _get_h264_init_packets(DeviceInfo("S2", 0)) == []


def test_broadcast_video_packet_ignores_empty_and_resyncs_waiting_client():
    """验证空包直接丢弃；同步包为等待关键帧的客户端排空旧包并注入初始化包。"""
    dev = DeviceInfo("S1", 0)
    empty_q = ClientStreamQueue(maxsize=10)
    dev.input_queues.append(empty_q)
    _broadcast_video_packet(dev, b"")
    assert empty_q.qsize() == 0
    assert dev.sps_pps_packets == []

    q1 = ClientStreamQueue(maxsize=10)
    q2 = ClientStreamQueue(maxsize=10)
    dev.input_queues.extend([q1, q2])
    sps = b"\x00\x00\x00\x01\x67\x42\x00\x1f\x00\x00\x00\x01\x68\xce\x3c\x80"
    p_frame = b"\x00\x00\x00\x01\x41\x9a\x24"
    idr = b"\x00\x00\x00\x01\x65\x88\x84\x21"

    # q1 模拟曾因队列满进入等待关键帧状态，并残留旧包
    q1.awaiting_keyframe = True
    q1.queue.put(b"stale_1")
    q1.queue.put(b"stale_2")

    _broadcast_video_packet(dev, sps)
    assert q1.awaiting_keyframe is False
    assert q1.get(0.1) == sps  # 旧包被排空后从关键帧重新续传
    assert q1.qsize() == 0
    assert q2.get(0.1) == sps

    _broadcast_video_packet(dev, p_frame)
    assert q1.get(0.1) == p_frame
    assert q2.get(0.1) == p_frame

    _broadcast_video_packet(dev, idr)
    assert q1.get(0.1) == idr
    assert q2.get(0.1) == idr
    assert [q1.qsize(), q2.qsize()] == [0, 0]
    assert dev.last_keyframe_packet == idr


# ---------------------------------------------------------------------------
# ClientStreamQueue / ClientStream 队列逻辑
# ---------------------------------------------------------------------------


def test_client_stream_queue_offer_inactive_and_full():
    """验证关闭后的队列拒绝入队；满队列丢弃并进入等待关键帧状态。"""
    closed_q = ClientStreamQueue(maxsize=1)
    closed_q.close()
    assert closed_q.offer(b"a", {1}) is False
    assert closed_q.qsize() == 1  # 仅剩 close 写入的哨兵 None

    q = ClientStreamQueue(maxsize=1)
    assert q.offer(b"a", {1}) is True
    assert q.offer(b"b", {1}) is False
    assert q.awaiting_keyframe is True
    assert q.qsize() == 1
    assert q.get(timeout=0.1) == b"a"  # 第一个包保留，后续被丢弃


def test_client_stream_queue_offer_awaiting_keyframe_drops_non_sync():
    """验证等待关键帧期间非同步包被丢弃且状态保持不变。"""
    q = ClientStreamQueue(maxsize=4)
    q.queue.put(b"old")
    q.awaiting_keyframe = True
    assert q.offer(b"p", {1}) is False
    assert q.awaiting_keyframe is True
    assert q.qsize() == 1  # 旧包未被排空


def test_client_stream_queue_offer_keyframe_drains_and_injects_init_packets():
    """验证关键帧到来时排空旧包并按序注入初始化包（跳过与数据重复的包）。"""
    q = ClientStreamQueue(maxsize=10)
    for stale in (b"stale_1", b"stale_2", b"stale_3"):
        q.queue.put(stale)
    q.awaiting_keyframe = True
    sps = b"\x00\x00\x00\x01\x67\x42"
    pps = b"\x00\x00\x00\x01\x68\xce"
    keyframe = b"\x00\x00\x00\x01\x65\x88"

    assert q.offer(keyframe, {5}, init_packets=[sps, keyframe, pps]) is True
    assert q.awaiting_keyframe is False
    assert q.qsize() == 3
    assert [q.get(0.1), q.get(0.1), q.get(0.1)] == [sps, pps, keyframe]

    # 无初始化包时仅重新入队关键帧本身
    q2 = ClientStreamQueue(maxsize=4)
    q2.queue.put(b"stale")
    q2.awaiting_keyframe = True
    assert q2.offer(keyframe, {5}, init_packets=None) is True
    assert q2.qsize() == 1
    assert q2.get(0.1) == keyframe


def test_client_stream_queue_offer_init_injection_stops_when_full():
    """验证注入初始化包时队列已满则停止注入，最终数据包无法入队并重新等待关键帧。"""
    q = ClientStreamQueue(maxsize=1)
    q.awaiting_keyframe = True
    pkt_a = b"\x00\x00\x00\x01\x67\x01"
    pkt_b = b"\x00\x00\x00\x01\x68\x02"
    keyframe = b"\x00\x00\x00\x01\x65\x03"

    assert q.offer(keyframe, {5}, init_packets=[pkt_a, pkt_b]) is False
    assert q.awaiting_keyframe is True
    assert q.qsize() == 1
    assert q.get(0.1) == pkt_a  # 只注入了第一个初始化包


def test_client_stream_queue_offer_tolerates_drain_race(monkeypatch):
    """验证排空旧包时与其它线程竞争（empty 为假但 get_nowait 抛 Empty）也能安全续传。"""
    q = ClientStreamQueue(maxsize=4)
    q.queue.put(b"stale")
    q.awaiting_keyframe = True

    def _racing_get_nowait():
        raise queue.Empty

    monkeypatch.setattr(q.queue, "get_nowait", _racing_get_nowait)
    keyframe = b"\x00\x00\x00\x01\x65\x88"
    assert q.offer(keyframe, {5}) is True
    assert q.awaiting_keyframe is False
    assert q.qsize() == 2  # 竞态下未被排空的旧包 + 关键帧
    assert q.get(0.1) == b"stale"


def test_client_stream_queue_get_timeout_raises_empty():
    """验证空队列按超时抛出 queue.Empty。"""
    q = ClientStreamQueue(maxsize=2)
    with pytest.raises(queue.Empty):
        q.get(timeout=0.01)


def test_client_stream_queue_close_puts_sentinel_and_tolerates_full():
    """验证 close 写入 None 哨兵；队列已满时静默忽略。"""
    q = ClientStreamQueue(maxsize=2)
    q.close()
    assert q.active is False
    assert q.get(timeout=0.1) is None

    full_q = ClientStreamQueue(maxsize=1)
    assert full_q.offer(b"x", {1}) is True
    full_q.close()  # queue.Full 被吞掉，不应抛异常
    assert full_q.active is False
    assert full_q.get(timeout=0.1) == b"x"


def test_client_stream_get_chunk_heartbeat_and_inactive_paths():
    """验证空队列返回空滴答；队列关闭或设备停止时立即返回 None。"""
    dev = DeviceInfo("S1", 0)
    dev.ready = True
    dev.running = True
    q = ClientStreamQueue(maxsize=2)
    dev.input_queues.append(q)
    stream = ClientStream(dev, q)

    assert stream.get_chunk(timeout=0.01) == b""  # 心跳/空滴答

    q.active = False
    assert stream.get_chunk(timeout=0.01) is None

    q.active = True
    dev.running = False
    assert stream.get_chunk(timeout=0.01) is None


def test_client_stream_close_is_safe_when_queue_not_registered():
    """验证队列未挂载时 close 仍安全（不误删其他队列）。"""
    dev = DeviceInfo("S1", 0)
    other = ClientStreamQueue(maxsize=2)
    dev.input_queues.append(other)
    q = ClientStreamQueue(maxsize=2)
    stream = ClientStream(dev, q)

    stream.close()
    assert q.active is False
    assert dev.input_queues == [other]


# ---------------------------------------------------------------------------
# 控制包构造与文本清洗（扩展）
# ---------------------------------------------------------------------------


def test_build_touch_control_packet_clamps_pressure_and_bounds():
    """验证压力钳制到 [0,1]、负坐标/尺寸归零以及自定义指针与按键字段。"""
    pkt = _build_touch_control_packet(
        action=ANDROID_MOTION_EVENT_ACTION_MOVE,
        x=-10,
        y=-1,
        screen_width=-5,
        screen_height=0,
        pointer_id=42,
        pressure=5.0,
        action_button=3,
        buttons=7,
    )
    _, act, pid, x, y, w, h, pressure_u16, action_btn, buttons = struct.unpack(">BBqIIHHHII", pkt)
    assert (act, pid) == (ANDROID_MOTION_EVENT_ACTION_MOVE, 42)
    assert (x, y, w, h) == (0, 0, 0, 0)
    assert pressure_u16 == 0xFFFF
    assert (action_btn, buttons) == (3, 7)

    # 负压力钳制为 0
    _, _, _, _, _, _, _, neg_pressure, _, _ = struct.unpack(
        ">BBqIIHHHII",
        _build_touch_control_packet(0, 1, 1, 100, 100, pressure=-3.0),
    )
    assert neg_pressure == 0

    # 中间压力值：round(0.5 * 0xFFFF) 按银行家舍入取偶 => 32768
    _, _, _, _, _, _, _, mid_pressure, _, _ = struct.unpack(
        ">BBqIIHHHII",
        _build_touch_control_packet(0, 1, 1, 100, 100, pressure=0.5),
    )
    assert mid_pressure == 32768


def test_build_keycode_control_packet_with_repeat_and_meta():
    """验证按键包的 repeat 与 meta_state 字段按大端有符号整型编码。"""
    pkt = _build_keycode_control_packet(1, 24, repeat=2, meta_state=0x1000)
    assert struct.unpack(">BBiii", pkt) == (SCRCPY_CONTROL_MSG_TYPE_INJECT_KEYCODE, 1, 24, 2, 0x1000)


def test_build_text_control_packet_empty_text():
    """验证空文本仅产生 5 字节包头（长度 0）。"""
    pkt = _build_text_control_packet("")
    assert pkt == struct.pack(">BI", SCRCPY_CONTROL_MSG_TYPE_INJECT_TEXT, 0)


def test_sanitize_adb_input_text_filters_non_printable_and_escapes_all_meta():
    """验证不可打印字符被剔除、制表符保留、全部 Shell 元字符转义。"""
    assert _sanitize_adb_input_text("") == ""
    assert _sanitize_adb_input_text("\x00\x1f\n\r") == ""
    assert _sanitize_adb_input_text("a\tb") == "a\tb"
    assert _sanitize_adb_input_text("hi 你好") == "hi%s你好"

    meta = "\\'\"$&;|<>()`~*?[]{}!^"
    assert _sanitize_adb_input_text(meta) == "".join("\\" + ch for ch in meta)


# ---------------------------------------------------------------------------
# 端口池与 _recv_exactly
# ---------------------------------------------------------------------------


def test_allocate_and_release_port_within_patched_range(monkeypatch):
    """验证端口按范围顺序分配、耗尽返回 None、释放后可复用。"""
    monkeypatch.setattr(device_stream_manager, "PORT_RANGE_START", 61000)
    monkeypatch.setattr(device_stream_manager, "PORT_RANGE_END", 61002)
    mgr = ScrcpyDeviceManager()

    assert mgr._allocate_port() == 61000
    assert mgr._allocate_port() == 61001
    assert mgr._allocate_port() is None  # 范围耗尽

    mgr._release_port(61000)
    assert mgr._allocate_port() == 61000
    mgr._release_port(99999)  # 释放从未占用的端口不应报错
    assert mgr._used_ports == {61000, 61001}


def test_recv_exactly_reads_across_chunks_and_detects_disconnect():
    """验证 _recv_exactly 跨多次 recv 收满指定字节数，断开时抛 ConnectionError。"""
    mgr = ScrcpyDeviceManager()
    server, client = socket.socketpair()
    server.settimeout(2)
    try:
        client.sendall(b"abc")
        client.sendall(b"de")
        assert mgr._recv_exactly(server, 5) == b"abcde"

        client.close()
        with pytest.raises(ConnectionError, match="Socket 连接已断开"):
            mgr._recv_exactly(server, 3)
    finally:
        server.close()
        client.close()


# ---------------------------------------------------------------------------
# _deploy_scrcpy_server
# ---------------------------------------------------------------------------


def test_deploy_scrcpy_server_missing_jar_returns_false(monkeypatch, tmp_path):
    """验证本地 jar 不存在时直接失败且不访问设备。"""
    monkeypatch.setattr(device_stream_manager, "SCRCPY_SERVER_PATH", tmp_path / "missing.jar")
    device = MagicMock()
    mgr = ScrcpyDeviceManager()
    assert mgr._deploy_scrcpy_server(device) is False
    device.shell.assert_not_called()


def test_deploy_scrcpy_server_skips_push_when_size_matches(monkeypatch, tmp_path):
    """验证设备端大小与本地一致时跳过推送。"""
    jar = tmp_path / "scrcpy-server.jar"
    jar.write_bytes(b"\x00" * 16)
    monkeypatch.setattr(device_stream_manager, "SCRCPY_SERVER_PATH", jar)
    device = MagicMock()
    device.shell.return_value = "16\n"
    mgr = ScrcpyDeviceManager()

    assert mgr._deploy_scrcpy_server(device) is True
    device.sync.push.assert_not_called()


def test_deploy_scrcpy_server_pushes_on_size_mismatch(monkeypatch, tmp_path):
    """验证设备端大小不一致时推送 jar 到设备。"""
    jar = tmp_path / "scrcpy-server.jar"
    jar.write_bytes(b"\x00" * 32)
    monkeypatch.setattr(device_stream_manager, "SCRCPY_SERVER_PATH", jar)
    device = MagicMock()
    device.shell.return_value = "0"
    mgr = ScrcpyDeviceManager()

    assert mgr._deploy_scrcpy_server(device) is True
    device.sync.push.assert_called_once_with(str(jar), DEVICE_JAR_PATH)


def test_deploy_scrcpy_server_returns_false_on_exception(monkeypatch, tmp_path):
    """验证设备 shell 异常时部署失败且不抛出。"""
    jar = tmp_path / "scrcpy-server.jar"
    jar.write_bytes(b"\x00" * 8)
    monkeypatch.setattr(device_stream_manager, "SCRCPY_SERVER_PATH", jar)
    device = MagicMock()
    device.shell.side_effect = RuntimeError("adb 挂死")
    mgr = ScrcpyDeviceManager()

    assert mgr._deploy_scrcpy_server(device) is False


# ---------------------------------------------------------------------------
# ensure_device_stream
# ---------------------------------------------------------------------------


def test_ensure_device_stream_returns_existing_ready_device(monkeypatch):
    """验证已就绪设备被直接返回且不触发后台连接。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    connect_mock = MagicMock()
    monkeypatch.setattr(mgr, "_connect_device_sync", connect_mock)

    assert mgr.ensure_device_stream("S1", timeout=0.5) is dev
    connect_mock.assert_not_called()


def test_ensure_device_stream_times_out_when_connecting_never_finishes():
    """验证串口标记为连接中且设备始终不就绪时抛出 TimeoutError。"""
    mgr = ScrcpyDeviceManager()
    mgr._connecting.add("S1")  # 预置连接中状态，避免启动真实连接线程

    with pytest.raises(TimeoutError, match="等待设备 S1 视频流就绪超时"):
        mgr.ensure_device_stream("S1", timeout=0.15)


def test_ensure_device_stream_waits_for_background_connect_success(monkeypatch):
    """验证后台连接成功后 ensure 轮询返回设备对象。"""
    mgr = ScrcpyDeviceManager()

    def _fake_connect(serial):
        info = DeviceInfo(serial, 27180)
        info.ready = True
        info.running = True
        with mgr._lock:
            mgr._devices[serial] = info
            mgr._connecting.discard(serial)

    monkeypatch.setattr(mgr, "_connect_device_sync", _fake_connect)
    dev = mgr.ensure_device_stream("S1", timeout=3.0)
    assert dev.serial == "S1"
    assert dev.ready and dev.running
    assert "S1" not in mgr._connecting


def test_ensure_device_stream_raises_when_background_connect_fails(monkeypatch):
    """验证后台连接失败后 ensure 抛出携带设备错误的 RuntimeError。"""
    mgr = ScrcpyDeviceManager()

    def _fake_connect(serial):
        info = DeviceInfo(serial, 27180)
        info.error = "模拟启动失败"
        with mgr._lock:
            mgr._devices[serial] = info
            mgr._connecting.discard(serial)

    monkeypatch.setattr(mgr, "_connect_device_sync", _fake_connect)
    with pytest.raises(RuntimeError, match="Scrcpy 启动失败: 模拟启动失败"):
        mgr.ensure_device_stream("S1", timeout=3.0)


# ---------------------------------------------------------------------------
# _connect_device_sync
# ---------------------------------------------------------------------------


def test_connect_device_sync_no_free_port_returns(monkeypatch):
    """验证端口耗尽时放弃连接并回滚 connecting 标记。"""
    mgr = ScrcpyDeviceManager()
    monkeypatch.setattr(mgr, "_allocate_port", lambda: None)
    mgr._connecting.add("FAKE_SERIAL")

    mgr._connect_device_sync("FAKE_SERIAL")
    assert "FAKE_SERIAL" not in mgr._devices
    assert "FAKE_SERIAL" not in mgr._connecting


def test_connect_device_sync_deploy_failure_records_error(monkeypatch):
    """验证推送 jar 失败时记录错误、释放端口并注册失败态设备。"""
    mgr = ScrcpyDeviceManager()
    monkeypatch.setattr(device_stream_manager, "adbutils", _make_adbutils_shim(_FakeDevice()))
    monkeypatch.setattr(mgr, "_deploy_scrcpy_server", lambda device: False)
    mgr._connecting.add("FAKE_SERIAL")

    mgr._connect_device_sync("FAKE_SERIAL")
    dev = mgr._devices["FAKE_SERIAL"]
    assert dev.error == "推送 scrcpy-server.jar 失败"
    assert dev.ready is False and dev.running is False
    assert dev.local_port not in mgr._used_ports
    assert "FAKE_SERIAL" not in mgr._connecting


def test_connect_device_sync_success_sets_up_streams(monkeypatch):
    """验证成功路径：建立 video/control socket、解析设备名与分辨率并启动读流线程。"""
    mgr = ScrcpyDeviceManager()
    codec_header = b"h264" + struct.pack(">II", 1080, 2340)
    env = _prepare_connect_success_env(monkeypatch, mgr, "FAKE_SERIAL", codec_header)
    mgr._connecting.add("FAKE_SERIAL")

    mgr._connect_device_sync("FAKE_SERIAL")

    dev = mgr._devices["FAKE_SERIAL"]
    assert dev.ready is True and dev.running is True
    assert dev.device_name == "PIXEL-7"
    assert (dev.screen_width, dev.screen_height) == (1080, 2340)
    assert dev.video_socket is env.video_fake
    assert dev.control_socket is env.ctrl_fake
    assert dev.scrcpy_process is env.proc
    assert dev.local_port in mgr._used_ports
    assert "FAKE_SERIAL" not in mgr._connecting
    assert env.device.forwarded == [(f"tcp:{dev.local_port}", "localabstract:scrcpy")]
    assert env.device.shell_calls and "pkill" in env.device.shell_calls[0]  # pkill 异常被吞掉
    assert env.reader_calls == [dev]
    assert env.ctrl_fake.setsockopt_args == (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    assert env.subprocess.popen_calls[0][0][0] == "adb"
    assert "com.genymobile.scrcpy.Server" in env.subprocess.popen_calls[0][0]
    assert env.video_fake.connected == ("127.0.0.1", dev.local_port)


def test_connect_device_sync_unknown_codec_header_uses_default_resolution(monkeypatch):
    """验证未识别 Codec Header 时回退默认 600x960 分辨率。"""
    mgr = ScrcpyDeviceManager()
    codec_header = b"vp09" + struct.pack(">II", 720, 1280)
    env = _prepare_connect_success_env(monkeypatch, mgr, "FAKE_SERIAL", codec_header)

    mgr._connect_device_sync("FAKE_SERIAL")

    dev = mgr._devices["FAKE_SERIAL"]
    assert (dev.screen_width, dev.screen_height) == (600, 960)
    assert dev.ready is True
    assert env.reader_calls == [dev]


def test_connect_device_sync_aborts_when_process_exits(monkeypatch):
    """验证 scrcpy 子进程提前退出时记录 stderr 并释放端口。"""
    mgr = ScrcpyDeviceManager()
    monkeypatch.setattr(device_stream_manager, "adbutils", _make_adbutils_shim(_FakeDevice()))
    monkeypatch.setattr(device_stream_manager, "time", _make_time_shim())
    monkeypatch.setattr(mgr, "_deploy_scrcpy_server", lambda device: True)
    proc = _FakeProc(poll_result=1, stderr=io.BytesIO(b"fatal boom"))
    monkeypatch.setattr(device_stream_manager, "subprocess", _RecordingSubprocess(proc))
    mgr._connecting.add("FAKE_SERIAL")

    mgr._connect_device_sync("FAKE_SERIAL")

    dev = mgr._devices["FAKE_SERIAL"]
    assert dev.error == "scrcpy 进程已退出: fatal boom"
    assert dev.ready is False
    assert dev.local_port not in mgr._used_ports
    assert "FAKE_SERIAL" not in mgr._connecting


def test_connect_device_sync_video_socket_timeout(monkeypatch):
    """验证重试 12 次仍无法建立视频连接时终止进程并记录超时错误。"""
    mgr = ScrcpyDeviceManager()
    fake_socket = _FakeSocketFactory(lambda: _RefusingSocket())
    monkeypatch.setattr(device_stream_manager, "socket", fake_socket)
    monkeypatch.setattr(device_stream_manager, "adbutils", _make_adbutils_shim(_FakeDevice()))
    monkeypatch.setattr(device_stream_manager, "time", _make_time_shim())
    monkeypatch.setattr(device_stream_manager, "subprocess", _RecordingSubprocess(_FakeProc()))
    monkeypatch.setattr(mgr, "_deploy_scrcpy_server", lambda device: True)
    mgr._connecting.add("FAKE_SERIAL")

    mgr._connect_device_sync("FAKE_SERIAL")

    dev = mgr._devices["FAKE_SERIAL"]
    assert dev.error == "Video socket 连接超时"
    assert len(fake_socket.created) == 12
    assert all(sock.closed for sock in fake_socket.created)
    assert dev.scrcpy_process is None or dev.scrcpy_process.terminate_calls == 1
    assert dev.local_port not in mgr._used_ports
    assert "FAKE_SERIAL" not in mgr._connecting


def test_connect_device_sync_generic_exception_marks_device_error(monkeypatch):
    """验证 adb 初始化抛出任意异常时设备标记错误并释放端口。"""
    mgr = ScrcpyDeviceManager()
    monkeypatch.setattr(
        device_stream_manager,
        "adbutils",
        _make_adbutils_shim(client_raises=RuntimeError("adb 不可用")),
    )
    mgr._connecting.add("FAKE_SERIAL")

    mgr._connect_device_sync("FAKE_SERIAL")

    dev = mgr._devices["FAKE_SERIAL"]
    assert dev.error == "adb 不可用"
    assert dev.ready is False and dev.running is False
    assert dev.local_port not in mgr._used_ports
    assert "FAKE_SERIAL" not in mgr._connecting


def test_connect_device_sync_retries_when_dummy_probe_is_empty(monkeypatch):
    """验证 dummy 校验读到空数据（防御分支）时不视为打通，换 socket 重试直至成功。"""
    mgr = ScrcpyDeviceManager()
    codec_header = b"h264" + struct.pack(">II", 720, 1280)
    env = _prepare_connect_success_env(monkeypatch, mgr, "FAKE_SERIAL", codec_header, leading_fakes=[_ScriptSocket([])])
    real_recv = ScrcpyDeviceManager._recv_exactly
    dummy_probe = []

    def _recv_sequence(sock, n):
        if n == 1 and not dummy_probe:
            dummy_probe.append(sock)
            return b""  # 第一次探测拿到空数据
        return real_recv(mgr, sock, n)

    monkeypatch.setattr(mgr, "_recv_exactly", _recv_sequence)

    mgr._connect_device_sync("FAKE_SERIAL")

    dev = mgr._devices["FAKE_SERIAL"]
    assert dev.ready is True
    assert (dev.screen_width, dev.screen_height) == (720, 1280)
    assert len(dummy_probe) == 1
    assert len(env.socket_factory.created) == 3
    assert env.reader_calls == [dev]


def test_connect_device_sync_socket_creation_failure_times_out(monkeypatch):
    """验证 socket() 创建即失败（video_sock 保持 None）时按超时处理且不尝试关闭。"""
    mgr = ScrcpyDeviceManager()

    def _raising_factory():
        raise OSError("socket 创建失败")

    monkeypatch.setattr(device_stream_manager, "socket", _FakeSocketFactory(_raising_factory))
    monkeypatch.setattr(device_stream_manager, "adbutils", _make_adbutils_shim(_FakeDevice()))
    monkeypatch.setattr(device_stream_manager, "time", _make_time_shim())
    proc = _FakeProc()
    monkeypatch.setattr(device_stream_manager, "subprocess", _RecordingSubprocess(proc))
    monkeypatch.setattr(mgr, "_deploy_scrcpy_server", lambda device: True)

    mgr._connect_device_sync("FAKE_SERIAL")

    dev = mgr._devices["FAKE_SERIAL"]
    assert dev.error == "Video socket 连接超时"
    assert proc.terminate_calls == 1
    assert dev.local_port not in mgr._used_ports


def test_connect_device_sync_closes_sockets_when_handshake_fails(monkeypatch):
    """验证视频握手（读取设备名）失败时关闭两端 socket、终止进程并释放端口。"""
    mgr = ScrcpyDeviceManager()
    env = _prepare_connect_success_env(monkeypatch, mgr, "FAKE_SERIAL", b"h264" + struct.pack(">II", 1080, 2340))
    env.video_fake._chunks[:] = [b"D"]  # 仅够 dummy 校验，读取设备名时立即断开

    mgr._connect_device_sync("FAKE_SERIAL")

    dev = mgr._devices["FAKE_SERIAL"]
    assert dev.error == "Socket 连接已断开"
    assert dev.ready is False
    assert env.video_fake.closed is True
    assert env.ctrl_fake.closed is True
    assert env.proc.terminate_calls == 1
    assert dev.local_port not in mgr._used_ports


def test_connect_device_sync_swallows_cleanup_errors_on_handshake_failure(monkeypatch):
    """验证握手失败收尾阶段：socket 关闭与进程终止异常均被吞掉，不影响错误记录。"""
    mgr = ScrcpyDeviceManager()
    env = _prepare_connect_success_env(monkeypatch, mgr, "FAKE_SERIAL", b"h264" + struct.pack(">II", 1080, 2340))
    env.video_fake._chunks[:] = [b"D"]  # 仅够 dummy 校验，读取设备名时立即断开

    def _failing_close():
        env.video_fake.closed = True
        raise OSError("close 失败")

    def _failing_terminate():
        env.proc.terminate_calls += 1
        raise RuntimeError("kill 失败")

    env.video_fake.close = _failing_close
    env.proc.terminate = _failing_terminate

    mgr._connect_device_sync("FAKE_SERIAL")

    dev = mgr._devices["FAKE_SERIAL"]
    assert dev.error == "Socket 连接已断开"
    assert env.video_fake.closed is True
    assert env.proc.terminate_calls == 1
    assert dev.local_port not in mgr._used_ports


def test_connect_device_sync_skips_terminate_for_falsy_process(monkeypatch):
    """验证进程对象为假值时超时收尾跳过 terminate（防御分支）。"""
    mgr = ScrcpyDeviceManager()

    class _FalsyProc(_FakeProc):
        """恒为假值的假进程。"""

        def __bool__(self):
            return False

    proc = _FalsyProc()
    monkeypatch.setattr(device_stream_manager, "socket", _FakeSocketFactory(lambda: _RefusingSocket()))
    monkeypatch.setattr(device_stream_manager, "adbutils", _make_adbutils_shim(_FakeDevice()))
    monkeypatch.setattr(device_stream_manager, "time", _make_time_shim())
    monkeypatch.setattr(device_stream_manager, "subprocess", _RecordingSubprocess(proc))
    monkeypatch.setattr(mgr, "_deploy_scrcpy_server", lambda device: True)

    mgr._connect_device_sync("FAKE_SERIAL")

    dev = mgr._devices["FAKE_SERIAL"]
    assert dev.error == "Video socket 连接超时"
    assert proc.terminate_calls == 0
    assert dev.local_port not in mgr._used_ports


# ---------------------------------------------------------------------------
# _start_video_reader（全部使用假 socket，线程带超时 join，保证确定性）
# ---------------------------------------------------------------------------


def test_video_reader_without_socket_cleans_up():
    """验证 video_socket 为空时读流线程直接清理设备。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")

    mgr._start_video_reader(dev)
    dev.reader_thread.join(timeout=5)
    assert not dev.reader_thread.is_alive()
    assert "S1" not in mgr._devices


def test_video_reader_parses_length_prefixed_packets_and_exits():
    """验证非 raw 模式：长度前缀拆包、长度非法跳过、超时继续、断开后清理。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    q = ClientStreamQueue(maxsize=10)
    dev.input_queues.append(q)
    payload = b"\x65\x88\x84\x21\x00\x01\x02\x03"
    chunks = [
        _packet_header(len(payload)),
        payload,
        socket.timeout(),  # 读包头超时 -> continue
        _packet_header(0),  # 长度 0 -> continue
        _packet_header(5 * 1024 * 1024 + 1),  # 超长 -> continue
        b"",  # 断开 -> ConnectionError -> break
    ]
    fake = _ScriptSocket(chunks)
    dev.video_socket = fake

    mgr._start_video_reader(dev)
    dev.reader_thread.join(timeout=5)
    assert not dev.reader_thread.is_alive()

    assert q.qsize() == 1
    assert q.get(0.1) == payload
    assert fake.closed is True
    assert dev.ready is False and dev.running is False
    assert "S1" not in mgr._devices


def test_video_reader_raw_mode_splits_on_start_codes():
    """验证 raw 模式：按起始码切分 NAL、超时继续、收流结束退出。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    q = ClientStreamQueue(maxsize=10)
    dev.input_queues.append(q)
    first_12 = b"\x00\x00\x00\x01\x65" + b"\x00" * 7
    chunk_a = b"\x00\x00\x00\x01\x41\x9a\x24" + b"\x00\x00\x00\x01\x65\x88"
    fake = _ScriptSocket([first_12, chunk_a, socket.timeout(), b""])
    dev.video_socket = fake

    mgr._start_video_reader(dev)
    dev.reader_thread.join(timeout=5)
    assert not dev.reader_thread.is_alive()

    assert q.qsize() == 2
    assert q.get(0.1) == first_12
    assert q.get(0.1) == chunk_a[:7]
    assert "S1" not in mgr._devices


def test_video_reader_returns_early_when_header_read_fails():
    """验证首个 12 字节头读取失败（连接立即断开）时仍执行清理。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    dev.video_socket = _ScriptSocket([b""])

    mgr._start_video_reader(dev)
    dev.reader_thread.join(timeout=5)
    assert not dev.reader_thread.is_alive()
    assert dev.ready is False and dev.running is False
    assert "S1" not in mgr._devices


def test_video_reader_raw_mode_exits_immediately_when_device_stopped():
    """验证 raw 模式下设备已停止时读流循环不进入循环体，直接清理退出。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    dev.running = False
    dev.video_socket = _ScriptSocket([b"\x00\x00\x00\x01\x65" + b"\x00" * 7])

    mgr._start_video_reader(dev)
    dev.reader_thread.join(timeout=5)
    assert not dev.reader_thread.is_alive()
    assert "S1" not in mgr._devices


def test_video_reader_length_mode_exits_immediately_when_manager_stopped():
    """验证长度前缀模式下管理器已停止时读流循环不进入循环体，直接清理退出。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    mgr._running = False
    dev.video_socket = _ScriptSocket([_packet_header(8)])

    mgr._start_video_reader(dev)
    dev.reader_thread.join(timeout=5)
    assert not dev.reader_thread.is_alive()
    assert "S1" not in mgr._devices


def test_video_reader_raw_mode_breaks_on_read_error():
    """验证 raw 模式收到非超时读错误时跳出循环并清理。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    dev.video_socket = _ScriptSocket([b"\x00\x00\x00\x01\x65" + b"\x00" * 7, OSError("读流失败")])

    mgr._start_video_reader(dev)
    dev.reader_thread.join(timeout=5)
    assert not dev.reader_thread.is_alive()
    assert "S1" not in mgr._devices


def test_video_reader_length_mode_tolerates_empty_reads(monkeypatch):
    """验证防御分支：包头读取返回空字节时跳出循环、负载为空时跳过当前帧。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    fake = _ScriptSocket([])
    dev.video_socket = fake
    state = {"first_header_done": False}

    def _recv_sequence(sock, n):
        if n == 12:
            if not state["first_header_done"]:
                state["first_header_done"] = True
                return _packet_header(8)
            return b""  # 包头读取返回空 -> 防御性 break
        return b""  # 负载读取返回空 -> 防御性 continue

    monkeypatch.setattr(mgr, "_recv_exactly", _recv_sequence)

    mgr._start_video_reader(dev)
    dev.reader_thread.join(timeout=5)
    assert not dev.reader_thread.is_alive()
    assert fake.closed is True
    assert "S1" not in mgr._devices


# ---------------------------------------------------------------------------
# create_client_stream / get_video_generator
# ---------------------------------------------------------------------------


def test_create_client_stream_seeds_init_packets_and_registers_queue():
    """验证创建客户端流时预置 SPS/PPS 与关键帧并挂载到设备队列。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    sps = b"\x00\x00\x00\x01\x67\x42\x00\x1f"
    idr = b"\x00\x00\x00\x01\x65\x88\x84\x21"
    dev.sps_pps_packets = [sps]
    dev.last_keyframe_packet = idr

    stream = mgr.create_client_stream("S1")

    assert isinstance(stream, ClientStream)
    assert stream.dev_info is dev
    assert stream.client_queue in dev.input_queues
    assert stream.client_queue.qsize() == 2
    assert [stream.client_queue.get(0.1), stream.client_queue.get(0.1)] == [sps, idr]


def test_create_client_stream_without_init_cache_starts_empty():
    """验证无初始化缓存时客户端队列为空但仍被挂载。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")

    stream = mgr.create_client_stream("S1")
    assert stream.client_queue.qsize() == 0
    assert stream.client_queue in dev.input_queues


def test_get_video_generator_yields_init_packet_then_stops():
    """验证生成器先吐初始化包，设备停止后结束并解挂队列。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    sps = b"\x00\x00\x00\x01\x67\x42\x00\x1f"
    dev.sps_pps_packets = [sps]

    gen = mgr.get_video_generator("S1")
    assert next(gen) == sps
    assert len(dev.input_queues) == 1

    dev.input_queues.clear()  # 模拟队列已被 ClientStream.close 提前解挂
    dev.running = False
    with pytest.raises(StopIteration):
        next(gen)
    assert dev.input_queues == []


def test_get_video_generator_breaks_on_none_sentinel(monkeypatch):
    """验证队列返回 None 哨兵时生成器立即结束并解挂队列。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    monkeypatch.setattr(ClientStreamQueue, "get", lambda self, timeout=1.0: None)

    gen = mgr.get_video_generator("S1")
    with pytest.raises(StopIteration):
        next(gen)
    assert dev.input_queues == []


def test_get_video_generator_breaks_when_device_stops_after_queue_empty(monkeypatch):
    """验证出队超时且设备不再就绪时生成器结束。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")

    def _empty_then_not_ready(self, timeout=1.0):
        dev.ready = False
        raise queue.Empty

    monkeypatch.setattr(ClientStreamQueue, "get", _empty_then_not_ready)
    gen = mgr.get_video_generator("S1")
    with pytest.raises(StopIteration):
        next(gen)
    assert dev.input_queues == []


def test_get_video_generator_exits_when_client_queue_deactivated(monkeypatch):
    """验证客户端队列被关闭后生成器退出循环并解挂队列。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")

    def _deactivate_and_timeout(self, timeout=1.0):
        self.active = False
        raise queue.Empty

    monkeypatch.setattr(ClientStreamQueue, "get", _deactivate_and_timeout)
    gen = mgr.get_video_generator("S1")
    with pytest.raises(StopIteration):
        next(gen)
    assert dev.input_queues == []


# ---------------------------------------------------------------------------
# send_touch_event / send_key_event / send_text_event
# ---------------------------------------------------------------------------


def test_send_touch_event_requires_ready_control_socket(monkeypatch):
    """验证设备缺失、未就绪或 control socket 为空时抛出 ValueError。"""
    mgr = ScrcpyDeviceManager()
    with pytest.raises(ValueError, match="scrcpy control socket 未就绪"):
        mgr.send_touch_event("S1", ANDROID_MOTION_EVENT_ACTION_DOWN, 1, 1)

    dev = _register_ready_device(mgr, "S1")  # control_socket 仍为 None
    with pytest.raises(ValueError, match="scrcpy control socket 未就绪"):
        mgr.send_touch_event("S1", ANDROID_MOTION_EVENT_ACTION_DOWN, 1, 1)

    dev.ready = False
    dev.control_socket = MagicMock()
    with pytest.raises(ValueError, match="scrcpy control socket 未就绪"):
        mgr.send_touch_event("S1", ANDROID_MOTION_EVENT_ACTION_DOWN, 1, 1)


def test_send_touch_event_clamps_and_defaults_dimensions():
    """验证坐标按屏幕尺寸钳制、宽高缺省取屏幕值、负宽高退化为 1 像素。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    dev.screen_width = 1600
    dev.screen_height = 2560
    sock = MagicMock()
    dev.control_socket = sock

    mgr.send_touch_event("S1", ANDROID_MOTION_EVENT_ACTION_DOWN, -50, 99999)
    _, act, _, x, y, w, h, pressure, _, _ = struct.unpack(">BBqIIHHHII", sock.sendall.call_args[0][0])
    assert act == ANDROID_MOTION_EVENT_ACTION_DOWN
    assert (x, y) == (0, 2559)
    assert (w, h) == (1600, 2560)
    assert pressure == 0xFFFF

    # 负宽度退化为 1，高度为 0 时回退屏幕高度，坐标被压回 0
    mgr.send_touch_event("S1", ANDROID_MOTION_EVENT_ACTION_MOVE, 5, 5, width=-10, height=0)
    _, _, _, x2, y2, w2, h2, _, _, _ = struct.unpack(">BBqIIHHHII", sock.sendall.call_args[0][0])
    assert (x2, y2, w2, h2) == (0, 5, 1, 2560)


def test_send_key_event_sends_down_and_up_via_control_socket(monkeypatch):
    """验证 control socket 可用时一次发送按下+抬起两个按键包，不走 adb 回退。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    sock = MagicMock()
    dev.control_socket = sock
    fake_subprocess = _RecordingSubprocess()
    monkeypatch.setattr(device_stream_manager, "subprocess", fake_subprocess)

    mgr.send_key_event("S1", 4)

    sock.sendall.assert_called_once()
    sent = sock.sendall.call_args[0][0]
    assert len(sent) == 28
    assert struct.unpack(">BBiii", sent[:14]) == (SCRCPY_CONTROL_MSG_TYPE_INJECT_KEYCODE, 0, 4, 0, 0)
    assert struct.unpack(">BBiii", sent[14:]) == (SCRCPY_CONTROL_MSG_TYPE_INJECT_KEYCODE, 1, 4, 0, 0)
    assert fake_subprocess.run_calls == []


def test_send_key_event_falls_back_to_adb_shell(monkeypatch):
    """验证设备缺失或未就绪时回退到 adb shell input keyevent。"""
    mgr = ScrcpyDeviceManager()
    fake_subprocess = _RecordingSubprocess()
    monkeypatch.setattr(device_stream_manager, "subprocess", fake_subprocess)

    mgr.send_key_event("S1", 26)
    not_ready = _register_ready_device(mgr, "S2")
    not_ready.ready = False
    mgr.send_key_event("S2", 26)

    assert [call[0] for call in fake_subprocess.run_calls] == [
        ["adb", "-s", "S1", "shell", "input", "keyevent", "26"],
        ["adb", "-s", "S2", "shell", "input", "keyevent", "26"],
    ]
    assert fake_subprocess.run_calls[0][1] == {"capture_output": True, "timeout": 5}


def test_send_text_event_uses_control_socket_when_ready(monkeypatch):
    """验证 control socket 可用时直接发送文本控制包。"""
    mgr = ScrcpyDeviceManager()
    dev = _register_ready_device(mgr, "S1")
    sock = MagicMock()
    dev.control_socket = sock
    fake_subprocess = _RecordingSubprocess()
    monkeypatch.setattr(device_stream_manager, "subprocess", fake_subprocess)

    mgr.send_text_event("S1", "hi 你好")

    raw = "hi 你好".encode("utf-8")
    sock.sendall.assert_called_once_with(struct.pack(">BI", SCRCPY_CONTROL_MSG_TYPE_INJECT_TEXT, len(raw)) + raw)
    assert fake_subprocess.run_calls == []


def test_send_text_event_fallback_sanitizes_and_skips_empty(monkeypatch):
    """验证回退路径先做安全转义；清洗后为空则不执行 adb 命令；空文本直接短路。"""
    mgr = ScrcpyDeviceManager()
    fake_subprocess = _RecordingSubprocess()
    monkeypatch.setattr(device_stream_manager, "subprocess", fake_subprocess)

    mgr.send_text_event("S1", "")
    mgr.send_text_event("S1", "hello world")
    mgr.send_text_event("S1", "\x00\x01\x02")

    assert len(fake_subprocess.run_calls) == 1
    assert fake_subprocess.run_calls[0][0] == ["adb", "-s", "S1", "shell", "input", "text", "hello%sworld"]


# ---------------------------------------------------------------------------
# _cleanup_device / cleanup_all
# ---------------------------------------------------------------------------


def test_cleanup_device_unknown_serial_is_noop():
    """验证清理不存在的串口不抛异常、不影响设备表。"""
    mgr = ScrcpyDeviceManager()
    mgr._cleanup_device("NOPE")
    assert mgr._devices == {}


def test_cleanup_device_swallows_close_and_kill_errors(monkeypatch):
    """验证 socket 关闭、进程终止与 adb 清理异常均被吞掉且端口一定释放。"""
    mgr = ScrcpyDeviceManager()
    dev = DeviceInfo("DEV_X", 27185)
    dev.ready = True
    dev.running = True
    mock_sock = MagicMock()
    mock_sock.close.side_effect = OSError("close 失败")
    mock_proc = MagicMock()
    mock_proc.terminate.side_effect = RuntimeError("kill 失败")
    dev.video_socket = mock_sock
    dev.control_socket = MagicMock()
    dev.scrcpy_process = mock_proc
    mgr._devices["DEV_X"] = dev
    mgr._used_ports.add(27185)
    monkeypatch.setattr(
        device_stream_manager,
        "adbutils",
        _make_adbutils_shim(client_raises=RuntimeError("adb 不可用")),
    )

    mgr._cleanup_device("DEV_X")

    assert "DEV_X" not in mgr._devices
    assert 27185 not in mgr._used_ports
    mock_sock.close.assert_called_once()
    mock_proc.terminate.assert_called_once()


def test_cleanup_device_removes_adb_forward(monkeypatch):
    """验证清理时移除 adb 端口转发。"""
    mgr = ScrcpyDeviceManager()
    dev = DeviceInfo("DEV_Y", 27186)
    mgr._devices["DEV_Y"] = dev
    mgr._used_ports.add(27186)
    fake_device = _FakeDevice(serial="DEV_Y")
    monkeypatch.setattr(device_stream_manager, "adbutils", _make_adbutils_shim(fake_device))

    mgr._cleanup_device("DEV_Y")

    assert fake_device.forward_removed == ["tcp:27186"]
    assert 27186 not in mgr._used_ports


def test_cleanup_all_stops_manager_and_clears_devices(monkeypatch):
    """验证 cleanup_all 停止管理器、清空设备表并释放全部端口。"""
    mgr = ScrcpyDeviceManager()
    monkeypatch.setattr(device_stream_manager, "adbutils", _make_adbutils_shim(_FakeDevice()))
    for serial, port in (("DEV_A", 27187), ("DEV_B", 27188)):
        dev = DeviceInfo(serial, port)
        dev.ready = True
        dev.running = True
        dev.scrcpy_process = MagicMock()
        dev.video_socket = MagicMock()
        mgr._devices[serial] = dev
        mgr._used_ports.add(port)

    mgr.cleanup_all()

    assert mgr._running is False
    assert mgr._devices == {}
    assert mgr._used_ports == set()
    assert mgr._connecting == set()
