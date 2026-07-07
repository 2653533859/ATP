"""adb_resilience 抽象层单测。

覆盖：
  - ensure_reachable 一次成功 / 二次成功 / 三次仍失败 / 非 TCP serial 不调 connect / reconnect=False 不重连
  - safe_run_adb 成功 / 非零重试 / TimeoutExpired 重试 / adb 不存在
  - HeartbeatMonitor 健康 / 连续失败触发 callback / async callback / callback 异常不冒泡 / 上下文退出取消 task
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services import adb_resilience as adb_r


# ---------- helpers ----------


class _FakeProc:
    def __init__(self, returncode=0, stdout="device", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_subprocess_run(scripted: list):
    """根据 scripted 列表逐次返回 _FakeProc 或 raise"""
    iterator = iter(scripted)

    def _runner(*args, **kwargs):
        try:
            item = next(iterator)
        except StopIteration:  # pragma: no cover
            raise AssertionError("subprocess.run called more times than scripted")
        if isinstance(item, BaseException):
            raise item
        return item

    return _runner


# ---------- ensure_reachable ----------


def test_ensure_reachable_first_attempt_success(monkeypatch):
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        _make_subprocess_run([_FakeProc(returncode=0, stdout="device")]),
    )
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    ok, message = adb_r.ensure_reachable("192.168.1.10:5555")

    assert ok is True
    assert "在线" in message


def test_ensure_reachable_recovers_on_second_attempt(monkeypatch):
    # 1: offline → 触发重连
    # 2: connect 返回 connected
    # 3: get-state -> device
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        _make_subprocess_run(
            [
                _FakeProc(returncode=0, stdout="offline"),
                _FakeProc(returncode=0, stdout=""),  # disconnect
                _FakeProc(returncode=0, stdout="connected to 192.168.1.10:5555"),
                _FakeProc(returncode=0, stdout="device"),
            ]
        ),
    )
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    ok, message = adb_r.ensure_reachable("192.168.1.10:5555", max_attempts=3)

    assert ok is True
    assert "重连后恢复" in message


def test_ensure_reachable_exhausts_attempts(monkeypatch):
    # 3 次全部 offline
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        _make_subprocess_run(
            [
                _FakeProc(returncode=0, stdout="offline"),
                _FakeProc(returncode=0, stdout=""),  # disconnect
                _FakeProc(returncode=1, stdout="", stderr="cannot connect"),  # connect failed
                _FakeProc(returncode=0, stdout="offline"),
                _FakeProc(returncode=0, stdout=""),
                _FakeProc(returncode=1, stdout="", stderr="cannot connect"),
                _FakeProc(returncode=0, stdout="offline"),
            ]
        ),
    )
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    ok, message = adb_r.ensure_reachable("192.168.1.10:5555", max_attempts=3)

    assert ok is False
    assert "共尝试 3 次" in message


def test_ensure_reachable_usb_serial_skips_reconnect(monkeypatch):
    calls: list[list] = []

    def _runner(args, **kwargs):
        calls.append(list(args))
        if args[0] == "adb" and len(args) >= 3 and args[2] == "-s":
            return _FakeProc(returncode=0, stdout="offline")
        return _FakeProc(returncode=0, stdout="offline")

    # 简化：直接捕获所有 adb 调用
    captured: list[tuple] = []

    def _capture(cmd, *args, **kwargs):
        captured.append(tuple(cmd))
        return _FakeProc(returncode=0, stdout="offline")

    monkeypatch.setattr(adb_r.subprocess, "run", _capture)
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    ok, _ = adb_r.ensure_reachable("ABC123USB", max_attempts=3)

    assert ok is False
    # USB serial 不应触发 connect/disconnect
    assert all("connect" not in cmd and "disconnect" not in cmd for cmd in captured)


def test_ensure_reachable_unauthorized_no_retry(monkeypatch):
    runs: list = []

    def _capture(cmd, *args, **kwargs):
        runs.append(tuple(cmd))
        return _FakeProc(returncode=0, stdout="unauthorized")

    monkeypatch.setattr(adb_r.subprocess, "run", _capture)
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    ok, message = adb_r.ensure_reachable("192.168.1.10:5555", max_attempts=3)

    assert ok is False
    assert "未授权" in message
    # 未授权不应触发后续重试
    assert len(runs) == 1


def test_ensure_reachable_reconnect_disabled(monkeypatch):
    captured: list[tuple] = []

    def _capture(cmd, *args, **kwargs):
        captured.append(tuple(cmd))
        return _FakeProc(returncode=0, stdout="offline")

    monkeypatch.setattr(adb_r.subprocess, "run", _capture)
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    ok, _ = adb_r.ensure_reachable("192.168.1.10:5555", max_attempts=3, reconnect=False)

    assert ok is False
    # reconnect=False 时不应有 disconnect/connect
    assert all("connect" not in cmd and "disconnect" not in cmd for cmd in captured)


def test_ensure_reachable_adb_not_found(monkeypatch):
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        _make_subprocess_run([FileNotFoundError("no adb")]),
    )
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    ok, message = adb_r.ensure_reachable("192.168.1.10:5555", max_attempts=3)

    assert ok is False
    assert "adb" in message


# ---------- safe_run_adb ----------


def test_safe_run_adb_success_first_try(monkeypatch):
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        _make_subprocess_run([_FakeProc(returncode=0, stdout="ok")]),
    )

    proc = adb_r.safe_run_adb("192.168.1.10:5555", ["shell", "echo", "ok"], retries=1)

    assert proc is not None
    assert proc.returncode == 0
    assert proc.stdout == "ok"


def test_safe_run_adb_retries_after_failure(monkeypatch):
    # 第一次失败，ensure_reachable 成功，第二次成功
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        _make_subprocess_run(
            [
                _FakeProc(returncode=1, stdout="", stderr="error"),
                _FakeProc(returncode=0, stdout="device"),  # ensure_reachable
                _FakeProc(returncode=0, stdout="ok"),
            ]
        ),
    )
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    proc = adb_r.safe_run_adb("192.168.1.10:5555", ["shell", "echo", "ok"], retries=1)

    assert proc is not None
    assert proc.returncode == 0


def test_safe_run_adb_timeout_retries(monkeypatch):
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        _make_subprocess_run(
            [
                subprocess.TimeoutExpired(cmd="adb", timeout=10),
                _FakeProc(returncode=0, stdout="device"),
                _FakeProc(returncode=0, stdout="ok"),
            ]
        ),
    )
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    proc = adb_r.safe_run_adb("192.168.1.10:5555", ["shell", "echo"], retries=1)

    assert proc is not None
    assert proc.returncode == 0


def test_safe_run_adb_timeout_sentinel(monkeypatch):
    """超时占位 CompletedProcess 应能被 is_adb_timeout 识别。"""
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        _make_subprocess_run(
            [
                subprocess.TimeoutExpired(cmd="adb", timeout=10),
            ]
        ),
    )
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    proc = adb_r.safe_run_adb("192.168.1.10:5555", ["shell", "echo"], retries=0)

    assert proc is not None
    assert adb_r.is_adb_timeout(proc) is True
    assert proc.returncode == adb_r.ADB_TIMEOUT_RETURNCODE
    assert proc.stderr == adb_r.ADB_TIMEOUT_SENTINEL


def test_safe_run_adb_returns_none_when_adb_missing(monkeypatch):
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        _make_subprocess_run([FileNotFoundError("no adb")]),
    )

    proc = adb_r.safe_run_adb("192.168.1.10:5555", ["shell", "echo"], retries=2)

    assert proc is None


# ---------- HeartbeatMonitor ----------


def _run_async(coro):
    """同步运行协程；不依赖 pytest-asyncio（环境未必安装）"""
    return asyncio.run(coro)


def test_heartbeat_no_failure_does_not_trigger(monkeypatch):
    monkeypatch.setattr(adb_r, "ensure_reachable", lambda *a, **kw: (True, "ok"))

    triggered = []

    async def _scenario():
        async with adb_r.HeartbeatMonitor(
            "192.168.1.10:5555",
            on_lost=lambda reason: triggered.append(reason),
            interval_sec=0,
            failure_threshold=2,
            enabled=True,
        ) as hb:
            await asyncio.sleep(0.05)
        return hb

    hb = _run_async(_scenario())

    assert hb.lost is False
    assert not triggered


def test_heartbeat_triggers_after_threshold(monkeypatch):
    monkeypatch.setattr(adb_r, "ensure_reachable", lambda *a, **kw: (False, "offline"))

    triggered: list[str] = []

    async def _scenario():
        async with adb_r.HeartbeatMonitor(
            "192.168.1.10:5555",
            on_lost=lambda reason: triggered.append(reason),
            interval_sec=0,
            failure_threshold=2,
            enabled=True,
        ) as hb:
            for _ in range(50):
                await asyncio.sleep(0.01)
                if hb.lost:
                    break
        return hb

    hb = _run_async(_scenario())

    assert hb.lost is True
    assert hb.lost_reason == "offline"
    assert triggered == ["offline"]


def test_heartbeat_async_callback(monkeypatch):
    monkeypatch.setattr(adb_r, "ensure_reachable", lambda *a, **kw: (False, "offline"))

    triggered: list[str] = []

    async def _async_cb(reason: str):
        await asyncio.sleep(0)
        triggered.append(reason)

    async def _scenario():
        async with adb_r.HeartbeatMonitor(
            "192.168.1.10:5555",
            on_lost=_async_cb,
            interval_sec=0,
            failure_threshold=1,
            enabled=True,
        ) as hb:
            for _ in range(50):
                await asyncio.sleep(0.01)
                if hb.lost:
                    break
        return hb

    hb = _run_async(_scenario())

    assert hb.lost is True
    assert triggered == ["offline"]


def test_heartbeat_callback_exception_swallowed(monkeypatch):
    monkeypatch.setattr(adb_r, "ensure_reachable", lambda *a, **kw: (False, "offline"))

    def _bad_cb(reason: str):
        raise RuntimeError("boom")

    async def _scenario():
        async with adb_r.HeartbeatMonitor(
            "192.168.1.10:5555",
            on_lost=_bad_cb,
            interval_sec=0,
            failure_threshold=1,
            enabled=True,
        ) as hb:
            for _ in range(50):
                await asyncio.sleep(0.01)
                if hb.lost:
                    break
        return hb

    hb = _run_async(_scenario())

    assert hb.lost is True  # 异常被吞，状态仍然标记


def test_heartbeat_disabled_does_not_start():
    triggered = []

    async def _scenario():
        async with adb_r.HeartbeatMonitor(
            "192.168.1.10:5555",
            on_lost=lambda reason: triggered.append(reason),
            interval_sec=0,
            failure_threshold=1,
            enabled=False,
        ) as hb:
            await asyncio.sleep(0.05)
        return hb

    hb = _run_async(_scenario())

    assert hb.lost is False
    assert not triggered
