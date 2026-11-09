import asyncio
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceLease, DeviceStatus
from app.services.adb_service import AdbDeviceInfo
from app.services.device_sync import (
    _build_upsert_stmt,
    _reconcile_busy_stmts,
    sync_devices_to_db_async,
    sync_devices_to_db_sync,
)

load_all_models()


def test_build_upsert_stmt_uses_postgres_on_conflict():
    info = AdbDeviceInfo(serial="emulator-5554", status="device", model="Pixel")
    stmt = _build_upsert_stmt(info, datetime.now(timezone.utc))
    sql = str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    sql_upper = sql.upper()

    assert "ON CONFLICT (SERIAL) DO UPDATE" in sql_upper
    assert "COALESCE" in sql_upper
    assert "CASE WHEN" in sql_upper


def test_build_upsert_stmt_uses_sqlite_on_conflict():
    info = AdbDeviceInfo(serial="emulator-5554", status="device", model="Pixel")
    stmt = _build_upsert_stmt(info, datetime.now(timezone.utc), "sqlite")
    sql = str(stmt.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True})).upper()

    assert "ON CONFLICT (SERIAL) DO UPDATE" in sql
    assert "COALESCE" in sql


def test_busy_reconcile_subquery_is_correlated_to_the_updated_device():
    # 放进 ON CONFLICT DO UPDATE 的子查询不会关联，会变成“任意设备有租约”；这里守住 UPDATE 的写法。
    for stmt in _reconcile_busy_stmts({"emulator-5554"}, datetime.now(timezone.utc)):
        for dialect in (postgresql.dialect(), sqlite.dialect()):
            sql = " ".join(str(stmt.compile(dialect=dialect)).split())
            assert "device_leases.device_id = devices.id" in sql
            assert "FROM device_leases WHERE" in sql
            assert "FROM device_leases, devices" not in sql


OLD = "2020-01-01 00:00:00.000000"
# serial、初始状态、租约（active / expired / None）、本次扫描的 adb 状态（None 表示未扫到）、期望状态
SCENARIOS = [
    ("busy-offline", "busy", "active", "offline", DeviceStatus.offline),
    ("busy-unauthorized", "busy", "active", "unauthorized", DeviceStatus.offline),
    ("busy-leased", "busy", "active", "device", DeviceStatus.busy),
    ("busy-expired", "busy", "expired", "device", DeviceStatus.online),
    ("busy-no-lease", "busy", None, "device", DeviceStatus.online),
    ("back-leased", "offline", "active", "device", DeviceStatus.busy),
    ("online-leased", "online", "active", "device", DeviceStatus.busy),
    ("free", "online", None, "device", DeviceStatus.online),
    ("back-free", "offline", None, "device", DeviceStatus.online),
    ("absent-busy", "busy", "active", None, DeviceStatus.offline),
    # 过期但尚未回收的租约不算占用。
    ("online-expired", "online", "expired", "device", DeviceStatus.online),
    ("back-expired", "offline", "expired", "device", DeviceStatus.online),
    ("absent-offline-expired", "offline", "expired", None, DeviceStatus.offline),
]
# 状态不变的行不应被纠正语句改写（updated_at 保持种子值）。
UNCHANGED = {"busy-leased", "free", "online-expired", "absent-offline-expired"}


def _fmt(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S.%f")


def _configure_sqlite(engine) -> None:
    # 与 app/core/database.py 本地模式一致：WAL + 外键，保留 pysqlite 默认的旧式事务。
    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def _prepare(path: Path, now: datetime) -> list[AdbDeviceInfo]:
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["users"], Device.__table__, DeviceLease.__table__])
    engine.dispose()
    con = sqlite3.connect(path)
    try:
        for index, (serial, status, lease, _scan, _expected) in enumerate(SCENARIOS, start=1):
            con.execute(
                "INSERT INTO devices (id, serial, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (index, serial, status, OLD, OLD),
            )
            if lease:
                expires = now + timedelta(minutes=10) if lease == "active" else now - timedelta(seconds=10)
                con.execute(
                    "INSERT INTO device_leases (device_id, lease_token, owner_label, acquired_at, heartbeat_at, "
                    "expires_at) VALUES (?, ?, 'x', ?, ?, ?)",
                    (index, f"token-{index}", _fmt(now), _fmt(now), _fmt(expires)),
                )
        con.commit()
    finally:
        con.close()
    scanned = [AdbDeviceInfo(serial=serial, status=scan) for serial, _, _, scan, _ in SCENARIOS if scan]
    return [*scanned, AdbDeviceInfo(serial="fresh", status="device")]


def _run_async_sync(path: Path, scanned: list[AdbDeviceInfo]) -> None:
    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{path.as_posix()}", connect_args={"timeout": 5})
        _configure_sqlite(engine.sync_engine)
        try:
            async with async_sessionmaker(engine)() as db:
                await sync_devices_to_db_async(db, scanned)
                await db.commit()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def _run_sync_sync(path: Path, scanned: list[AdbDeviceInfo]) -> None:
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"timeout": 5})
    _configure_sqlite(engine)
    try:
        with Session(engine) as session:
            sync_devices_to_db_sync(session, scanned)
            session.commit()
    finally:
        engine.dispose()


@pytest.mark.parametrize("runner", [_run_async_sync, _run_sync_sync], ids=["async", "sync"])
def test_sqlite_sync_derives_status_from_adb_state_and_active_leases(tmp_path, runner):
    path = tmp_path / "devices.sqlite3"
    scanned = _prepare(path, datetime.now(timezone.utc))

    runner(path, scanned)

    rows, lease_count = _read(path)
    expected = {serial: wanted.value for serial, _, _, _, wanted in SCENARIOS} | {"fresh": DeviceStatus.online.value}
    assert {serial: status for serial, (status, _) in rows.items()} == expected
    assert {serial: rows[serial][1] for serial in UNCHANGED} == {serial: OLD for serial in UNCHANGED}
    # 同步只改设备状态，租约的增删由租约服务负责。
    assert lease_count == sum(1 for scenario in SCENARIOS if scenario[2])


@pytest.mark.parametrize("runner", [_run_async_sync, _run_sync_sync], ids=["async", "sync"])
def test_sqlite_sync_with_no_adb_devices_marks_every_device_offline(tmp_path, runner):
    # 用户报告的场景：adb devices 为空（扫描返回 []），之前连过的设备必须全部离线，占用中的也一样。
    path = tmp_path / "empty.sqlite3"
    _prepare(path, datetime.now(timezone.utc))

    runner(path, [])

    rows, lease_count = _read(path)
    assert {status for status, _ in rows.values()} == {DeviceStatus.offline.value}
    assert len(rows) == len(SCENARIOS)
    assert lease_count == sum(1 for scenario in SCENARIOS if scenario[2])


def _read(path: Path):
    con = sqlite3.connect(path)
    try:
        rows = {
            serial: (status, updated)
            for serial, status, updated in con.execute("SELECT serial, status, updated_at FROM devices")
        }
        lease_count = con.execute("SELECT COUNT(*) FROM device_leases").fetchone()[0]
    finally:
        con.close()
    return rows, lease_count
