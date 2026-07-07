"""ADB 自愈指标埋点单测（Q7 A.3.2）。

验证：
- ensure_reachable 各路径分别 inc ADB_RECONNECT_TOTAL 对应 label
- ensure_reachable 始终 observe ADB_ENSURE_REACHABLE_DURATION
- HeartbeatMonitor 触发 on_lost 时 inc ADB_HEARTBEAT_LOST_TOTAL 并带 executor label
- 指标埋点失败不影响主流程
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services import adb_resilience as adb_r
from app.core import metrics


class _FakeProc:
    def __init__(self, returncode=0, stdout="device", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# ---------- helpers ----------


class _CallCounter:
    """记录 labels(...).inc() 调用，便于断言。"""

    def __init__(self):
        self.calls: list[dict] = []

    def labels(self, **kwargs):
        self.calls.append(kwargs)
        return self

    def inc(self, _amount: float = 1) -> None:
        pass

    def observe(self, _amount: float) -> None:
        pass


class _ObserveTracker:
    """记录 observe(x) 调用。"""

    def __init__(self):
        self.observations: list[float] = []

    def labels(self, **_kwargs):
        return self

    def inc(self, _amount: float = 1) -> None:
        pass

    def observe(self, value: float) -> None:
        self.observations.append(value)


# ---------- ensure_reachable 埋点 ----------


def test_ensure_reachable_success_inc_success_label(monkeypatch):
    counter = _CallCounter()
    observer = _ObserveTracker()
    monkeypatch.setattr(adb_r, "ADB_RECONNECT_TOTAL", counter)
    monkeypatch.setattr(adb_r, "ADB_ENSURE_REACHABLE_DURATION", observer)
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        lambda *a, **kw: _FakeProc(returncode=0, stdout="device"),
    )
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    ok, _ = adb_r.ensure_reachable("192.168.1.10:5555")

    assert ok is True
    assert counter.calls == [{"result": "success"}]
    assert len(observer.observations) == 1
    assert observer.observations[0] >= 0


def test_ensure_reachable_failure_inc_failure_label(monkeypatch):
    counter = _CallCounter()
    observer = _ObserveTracker()
    monkeypatch.setattr(adb_r, "ADB_RECONNECT_TOTAL", counter)
    monkeypatch.setattr(adb_r, "ADB_ENSURE_REACHABLE_DURATION", observer)
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        lambda *a, **kw: _FakeProc(returncode=0, stdout="offline"),
    )
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    ok, _ = adb_r.ensure_reachable("192.168.1.10:5555", max_attempts=2, reconnect=False)

    assert ok is False
    assert counter.calls == [{"result": "failure"}]
    assert len(observer.observations) == 1


def test_ensure_reachable_adb_not_found_label(monkeypatch):
    counter = _CallCounter()
    monkeypatch.setattr(adb_r, "ADB_RECONNECT_TOTAL", counter)
    monkeypatch.setattr(adb_r, "ADB_ENSURE_REACHABLE_DURATION", _ObserveTracker())

    def _raise(*_a, **_kw):
        raise FileNotFoundError("adb missing")

    monkeypatch.setattr(adb_r.subprocess, "run", _raise)
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    ok, _ = adb_r.ensure_reachable("192.168.1.10:5555")

    assert ok is False
    assert counter.calls == [{"result": "adb_not_found"}]


def test_ensure_reachable_usb_serial_marks_not_tcp(monkeypatch):
    """USB serial 无法 reconnect 时，应标记 not_tcp_serial。"""
    counter = _CallCounter()
    monkeypatch.setattr(adb_r, "ADB_RECONNECT_TOTAL", counter)
    monkeypatch.setattr(adb_r, "ADB_ENSURE_REACHABLE_DURATION", _ObserveTracker())
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        lambda *a, **kw: _FakeProc(returncode=0, stdout="offline"),
    )
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    ok, _ = adb_r.ensure_reachable("ABCDEF1234", max_attempts=2)

    assert ok is False
    # USB serial 进入循环时设置了 not_tcp_serial 标签
    assert counter.calls == [{"result": "not_tcp_serial"}]


def test_ensure_reachable_metric_emit_failure_does_not_propagate(monkeypatch):
    """埋点失败不应影响主流程。"""

    class _BrokenCounter:
        def labels(self, **_kwargs):
            raise RuntimeError("metric boom")

        def inc(self, _amount: float = 1) -> None:
            pass

        def observe(self, _amount: float) -> None:
            pass

    monkeypatch.setattr(adb_r, "ADB_RECONNECT_TOTAL", _BrokenCounter())
    monkeypatch.setattr(adb_r, "ADB_ENSURE_REACHABLE_DURATION", _ObserveTracker())
    monkeypatch.setattr(
        adb_r.subprocess,
        "run",
        lambda *a, **kw: _FakeProc(returncode=0, stdout="device"),
    )
    monkeypatch.setattr(adb_r.time, "sleep", lambda *_: None)

    # 不应抛
    ok, _ = adb_r.ensure_reachable("192.168.1.10:5555")
    assert ok is True


# ---------- HeartbeatMonitor 埋点 ----------


def _run_async(coro):
    return asyncio.run(coro)


def test_heartbeat_lost_increments_executor_label(monkeypatch):
    counter = _CallCounter()
    monkeypatch.setattr(adb_r, "ADB_HEARTBEAT_LOST_TOTAL", counter)
    monkeypatch.setattr(adb_r, "ensure_reachable", lambda *a, **kw: (False, "offline"))

    async def _scenario():
        async with adb_r.HeartbeatMonitor(
            "192.168.1.10:5555",
            interval_sec=0,
            failure_threshold=1,
            enabled=True,
            executor_label="perf",
        ) as hb:
            for _ in range(50):
                await asyncio.sleep(0.01)
                if hb.lost:
                    break
        return hb

    hb = _run_async(_scenario())

    assert hb.lost is True
    assert counter.calls == [{"executor": "perf"}]


def test_heartbeat_metric_emit_failure_does_not_skip_callback(monkeypatch):
    """埋点失败时回调仍应正常触发。"""

    class _BrokenCounter:
        def labels(self, **_kwargs):
            raise RuntimeError("metric boom")

        def inc(self, _amount: float = 1) -> None:
            pass

    monkeypatch.setattr(adb_r, "ADB_HEARTBEAT_LOST_TOTAL", _BrokenCounter())
    monkeypatch.setattr(adb_r, "ensure_reachable", lambda *a, **kw: (False, "offline"))

    triggered: list[str] = []

    async def _scenario():
        async with adb_r.HeartbeatMonitor(
            "192.168.1.10:5555",
            on_lost=lambda reason: triggered.append(reason),
            interval_sec=0,
            failure_threshold=1,
            enabled=True,
            executor_label="stability",
        ) as hb:
            for _ in range(50):
                await asyncio.sleep(0.01)
                if hb.lost:
                    break
        return hb

    hb = _run_async(_scenario())

    assert hb.lost is True
    assert triggered == ["offline"]  # 埋点 fail 不影响 callback


# ---------- metrics module 导出 ----------


def test_metrics_module_exposes_adb_symbols():
    """A.3.2 新增指标必须可 import。"""
    assert hasattr(metrics, "ADB_RECONNECT_TOTAL")
    assert hasattr(metrics, "ADB_HEARTBEAT_LOST_TOTAL")
    assert hasattr(metrics, "ADB_ENSURE_REACHABLE_DURATION")


def test_adb_counter_inc_is_safe():
    metrics.ADB_RECONNECT_TOTAL.labels(result="success").inc()
    metrics.ADB_RECONNECT_TOTAL.labels(result="failure").inc()
    metrics.ADB_RECONNECT_TOTAL.labels(result="not_tcp_serial").inc()
    metrics.ADB_RECONNECT_TOTAL.labels(result="adb_not_found").inc()
    metrics.ADB_HEARTBEAT_LOST_TOTAL.labels(executor="android").inc()
    metrics.ADB_HEARTBEAT_LOST_TOTAL.labels(executor="perf").inc()
    metrics.ADB_HEARTBEAT_LOST_TOTAL.labels(executor="stability").inc()
    metrics.ADB_HEARTBEAT_LOST_TOTAL.labels(executor="fluency").inc()
    metrics.ADB_ENSURE_REACHABLE_DURATION.observe(0.123)
