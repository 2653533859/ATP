"""本地设备巡检：扫描写库、与手动扫描串行、失败退避与停止。"""

import asyncio
import logging
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceLease
from app.services import local_device_monitor as monitor
from app.services.adb_service import AdbDeviceInfo

load_all_models()


def _fmt(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S.%f")


def _prepare(path: Path) -> sessionmaker:
    """按本地模式配置建库：WAL + 外键，pysqlite 旧式事务。三台设备，两条租约（一条已过期）。"""
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"timeout": 5})

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    Base.metadata.create_all(engine, tables=[Base.metadata.tables["users"], Device.__table__, DeviceLease.__table__])
    now = datetime.now(timezone.utc)
    con = sqlite3.connect(path)
    try:
        con.executemany(
            "INSERT INTO devices (id, serial, status) VALUES (?, ?, ?)",
            [(1, "expired-busy", "busy"), (2, "unplugged", "online"), (3, "leased", "online")],
        )
        for device_id, expires in ((1, now - timedelta(seconds=10)), (3, now + timedelta(minutes=10))):
            con.execute(
                "INSERT INTO device_leases (device_id, lease_token, owner_label, acquired_at, heartbeat_at, expires_at)"
                " VALUES (?, ?, 'x', ?, ?, ?)",
                (device_id, f"token-{device_id}", _fmt(now), _fmt(now), _fmt(expires)),
            )
        con.commit()
    finally:
        con.close()
    return sessionmaker(bind=engine, expire_on_commit=False)


def _read(path: Path):
    con = sqlite3.connect(path)
    try:
        statuses = dict(con.execute("SELECT serial, status FROM devices"))
        leases = sorted(row[0] for row in con.execute("SELECT lease_token FROM device_leases"))
    finally:
        con.close()
    return statuses, leases


def test_scan_and_sync_once_reclaims_expired_leases_and_syncs_status(tmp_path):
    path = tmp_path / "monitor.sqlite3"
    factory = _prepare(path)

    async def scanner():
        return [AdbDeviceInfo(serial="expired-busy", status="device"), AdbDeviceInfo(serial="leased", status="device")]

    try:
        assert asyncio.run(monitor.scan_and_sync_once(factory, scanner)) == 2
    finally:
        factory.kw["bind"].dispose()
    assert _read(path) == ({"expired-busy": "online", "unplugged": "offline", "leased": "busy"}, ["token-3"])


def test_scan_and_sync_once_marks_every_device_offline_when_adb_lists_none(tmp_path):
    # 用户报告的场景：adb devices 为空（返回 []，不是 None），之前连过的设备必须全部离线。
    path = tmp_path / "empty.sqlite3"
    factory = _prepare(path)

    async def scanner():
        return []

    try:
        assert asyncio.run(monitor.scan_and_sync_once(factory, scanner)) == 0
    finally:
        factory.kw["bind"].dispose()
    assert _read(path) == ({"expired-busy": "offline", "unplugged": "offline", "leased": "offline"}, ["token-3"])


def test_scan_and_sync_once_writes_from_a_worker_thread(monkeypatch):
    # 写事务不能开在主事件循环上，否则会和循环线程上的同步写库互相卡到忙超时。
    seen = {}

    def fake_apply(factory, scanned):
        seen["thread"] = threading.current_thread()
        seen["args"] = (factory, scanned)

    async def scanner():
        return [AdbDeviceInfo(serial="a", status="device")]

    async def scenario():
        seen["loop_thread"] = threading.current_thread()
        return await monitor.scan_and_sync_once("factory", scanner)

    monkeypatch.setattr(monitor, "_apply_scan", fake_apply)
    assert asyncio.run(scenario()) == 1
    assert seen["thread"] is not seen["loop_thread"]
    assert seen["args"] == ("factory", [AdbDeviceInfo(serial="a", status="device")])


def test_scan_and_sync_once_leaves_state_alone_when_adb_is_unavailable():
    def factory():
        raise AssertionError("ADB 不可用时不应打开数据库会话")

    async def scanner():
        return None

    assert asyncio.run(monitor.scan_and_sync_once(factory, scanner)) is None


def test_scan_lock_covers_the_database_write_not_just_the_adb_call(tmp_path):
    # 先开始的扫描写库较慢时，后一次扫描必须等它提交后才开始，不能先写、再被旧结果覆盖。
    path = tmp_path / "lock.sqlite3"
    factory = _prepare(path)
    engine = factory.kw["bind"]
    events = []
    delayed = []

    @event.listens_for(engine, "before_cursor_execute")
    def _slow_first_write(_conn, _cursor, statement, *_):
        if statement.startswith("INSERT INTO devices") and not delayed:
            delayed.append(True)
            time.sleep(0.2)

    @event.listens_for(factory, "after_commit")
    def _committed(_session):
        events.append("commit")

    async def first_scanner():
        events.append("first-scan")
        return [AdbDeviceInfo(serial="unplugged", status="device")]

    async def second_scanner():
        events.append("second-scan")
        return []

    async def scenario():
        first = asyncio.create_task(monitor.scan_and_sync_once(factory, first_scanner))
        await asyncio.sleep(0.05)
        await asyncio.gather(first, monitor.scan_and_sync_once(factory, second_scanner))

    try:
        asyncio.run(scenario())
    finally:
        engine.dispose()
    assert delayed == [True]
    assert events == ["first-scan", "commit", "second-scan", "commit"]
    assert _read(path)[0]["unplugged"] == "offline"


def test_monitor_uses_the_sync_session_factory_by_default(monkeypatch):
    sentinel = object()
    captured = []
    monkeypatch.setattr(sys.modules["app.core.database"], "sync_session_factory", sentinel, raising=False)

    async def scenario():
        stop = asyncio.Event()

        async def fake_once(factory, _scanner):
            captured.append(factory)
            stop.set()
            return 0

        monkeypatch.setattr(monitor, "scan_and_sync_once", fake_once)
        await asyncio.wait_for(monitor.run_local_device_monitor(stop), timeout=5)

    asyncio.run(scenario())
    assert captured == [sentinel]


def test_monitor_warns_once_backs_off_and_recovers(monkeypatch, caplog):
    outcomes = [None, RuntimeError("db unavailable"), 3, 2]
    delays = []

    async def scenario():
        stop = asyncio.Event()

        async def fake_once(_factory, _scanner):
            outcome = outcomes.pop(0)
            if not outcomes:
                stop.set()
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(monitor, "scan_and_sync_once", fake_once)
        monkeypatch.setattr(monitor, "_next_delay", lambda _base, failures: delays.append(failures) or 0)
        await asyncio.wait_for(monitor.run_local_device_monitor(stop, session_factory=object), timeout=5)

    with caplog.at_level(logging.INFO, logger=monitor.__name__):
        asyncio.run(scenario())

    assert delays == [1, 2, 0, 0]
    levels = [record.levelno for record in caplog.records if record.name == monitor.__name__]
    assert levels == [logging.WARNING, logging.INFO]


def test_monitor_waits_the_backoff_delay_between_failed_scans(monkeypatch):
    monkeypatch.setattr(monitor, "settings", SimpleNamespace(ADB_SCAN_INTERVAL=15))
    waits = []

    async def scenario():
        stop = asyncio.Event()
        calls = []

        async def fake_once(_factory, _scanner):
            calls.append(1)
            if len(calls) == 4:
                stop.set()
            return None

        async def fake_wait_for(awaitable, timeout):
            waits.append(timeout)
            awaitable.close()
            if stop.is_set():
                return True
            raise asyncio.TimeoutError

        monkeypatch.setattr(monitor, "scan_and_sync_once", fake_once)
        monkeypatch.setattr(monitor.asyncio, "wait_for", fake_wait_for)
        await monitor.run_local_device_monitor(stop, session_factory=object)

    asyncio.run(scenario())
    assert waits == [15, 30, 60, 120]


def test_monitor_logs_the_first_exception_with_traceback(monkeypatch, caplog):
    async def scenario():
        stop = asyncio.Event()

        async def failing_once(_factory, _scanner):
            stop.set()
            raise RuntimeError("db unavailable")

        monkeypatch.setattr(monitor, "scan_and_sync_once", failing_once)
        await asyncio.wait_for(monitor.run_local_device_monitor(stop, session_factory=object), timeout=5)

    with caplog.at_level(logging.WARNING, logger=monitor.__name__):
        asyncio.run(scenario())

    (record,) = [record for record in caplog.records if record.name == monitor.__name__]
    assert record.exc_info is not None and record.exc_info[0] is RuntimeError


def test_monitor_scans_immediately_and_stops_without_waiting_for_the_interval(monkeypatch):
    monkeypatch.setattr(monitor, "settings", SimpleNamespace(ADB_SCAN_INTERVAL=15))

    async def scenario():
        stop = asyncio.Event()
        first_call = asyncio.Event()
        calls = []

        async def fake_once(_factory, _scanner):
            calls.append(time.monotonic())
            first_call.set()
            return 0

        monkeypatch.setattr(monitor, "scan_and_sync_once", fake_once)
        started = time.monotonic()
        task = asyncio.create_task(monitor.run_local_device_monitor(stop, session_factory=object))
        await asyncio.wait_for(first_call.wait(), timeout=2)
        await asyncio.sleep(0.05)
        stop.set()
        await asyncio.wait_for(task, timeout=5)
        return calls, started

    calls, started = asyncio.run(scenario())
    # 间隔是 15 秒：只扫了一次，且设置停止后没有等满间隔就退出。
    assert len(calls) == 1 and calls[0] - started < 1


def test_monitor_cancellation_is_not_swallowed(monkeypatch):
    monkeypatch.setattr(monitor, "settings", SimpleNamespace(ADB_SCAN_INTERVAL=15))

    async def scenario():
        first_call = asyncio.Event()

        async def fake_once(_factory, _scanner):
            first_call.set()
            return 0

        monkeypatch.setattr(monitor, "scan_and_sync_once", fake_once)
        task = asyncio.create_task(monitor.run_local_device_monitor(asyncio.Event(), session_factory=object))
        await asyncio.wait_for(first_call.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


def test_next_delay_backs_off_exponentially_up_to_the_cap():
    assert [monitor._next_delay(15, failures) for failures in range(7)] == [15, 15, 30, 60, 120, 120, 120]


@pytest.mark.parametrize(("raw", "expected"), [(1, 5), (15, 15), (60, 60)])
def test_base_interval_is_clamped_to_the_minimum(monkeypatch, raw, expected):
    monkeypatch.setattr(monitor, "settings", SimpleNamespace(ADB_SCAN_INTERVAL=raw))
    assert monitor._base_interval() == expected


@pytest.mark.parametrize(
    ("local_mode", "enabled", "expected"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
def test_monitor_runs_only_in_local_mode_unless_switched_off(monkeypatch, local_mode, enabled, expected):
    # 不看 ADB_SCAN_ENABLED：已有本地档案里它是 false，不能让巡检因此永远不启动。
    monkeypatch.setattr(
        monitor,
        "settings",
        SimpleNamespace(ATP_LOCAL_MODE=local_mode, LOCAL_DEVICE_MONITOR_ENABLED=enabled, ADB_SCAN_ENABLED=False),
    )
    assert monitor.local_device_monitor_enabled() is expected


def test_local_profile_can_switch_the_monitor_off(monkeypatch):
    from app.core.config import get_settings

    profile = {
        "ATP_LOCAL_MODE": "true",
        "APP_ENV": "local",
        "APP_SECRET_KEY": "local-private-test-secret",
        "FIRST_ADMIN_PASSWORD": "local-private-test-password",
        "ADB_SCAN_ENABLED": "false",
    }
    for key, value in profile.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("LOCAL_DEVICE_MONITOR_ENABLED", raising=False)
    # 已有本地档案没有这一项：默认开启，不受 ADB_SCAN_ENABLED=false 影响。
    assert get_settings.__wrapped__().LOCAL_DEVICE_MONITOR_ENABLED is True

    monkeypatch.setenv("LOCAL_DEVICE_MONITOR_ENABLED", "false")
    configured = get_settings.__wrapped__()
    assert configured.LOCAL_DEVICE_MONITOR_ENABLED is False
    assert configured.ADB_SCAN_ENABLED is False
