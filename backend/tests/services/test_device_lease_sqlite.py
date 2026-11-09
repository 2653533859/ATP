"""设备租约在本地 SQLite 下的并发与事务语义测试。

引擎配置与 app/core/database.py 本地模式一致：WAL、外键、pysqlite 旧式事务。
竞态由第二个连接在指定语句之前抢先提交来构造，不使用替身数据库。
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceLease, DeviceStatus
from app.services.device_leases import (
    DeviceLeaseConflict,
    acquire_device_lease,
    get_active_device_lease,
    heartbeat_device_lease,
    reclaim_expired_device_leases,
    reclaim_expired_device_leases_sync,
    release_device_lease,
)

load_all_models()


async def _sqlite(path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{path.as_posix()}", connect_args={"timeout": 5})

    # 与 app/core/database.py 本地模式一致：WAL + 外键，且保留 pysqlite 默认的旧式事务。
    @event.listens_for(engine.sync_engine, "connect")
    def _configure(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    tables = [Base.metadata.tables["users"], Device.__table__, DeviceLease.__table__]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add(Device(id=1, serial="s", status=DeviceStatus.online))
        await db.commit()
    return engine, factory


async def _contend(factory, count):
    async def one(index):
        async with factory() as db:
            try:
                await acquire_device_lease(db, 1, owner_id=None, owner_label=f"w{index}")
                await db.commit()
                return "won"
            except DeviceLeaseConflict:
                await db.rollback()
                return "conflict"

    return await asyncio.gather(*(one(i) for i in range(count)))


def test_sqlite_concurrent_acquire_has_one_winner_and_clean_conflicts(tmp_path):
    async def scenario():
        engine, factory = await _sqlite(tmp_path / "lease.sqlite3")
        try:
            return await _contend(factory, 8)
        finally:
            await engine.dispose()

    assert sorted(asyncio.run(scenario())) == ["conflict"] * 7 + ["won"]


def test_sqlite_expired_lease_takeover_has_one_winner(tmp_path):
    async def scenario():
        engine, factory = await _sqlite(tmp_path / "expired.sqlite3")
        try:
            old = datetime.now(timezone.utc) - timedelta(seconds=5)
            async with factory() as db:
                db.add(
                    DeviceLease(
                        device_id=1,
                        lease_token="old",
                        owner_label="x",
                        acquired_at=old,
                        heartbeat_at=old,
                        expires_at=old,
                    )
                )
                await db.commit()
            return await _contend(factory, 8)
        finally:
            await engine.dispose()

    assert sorted(asyncio.run(scenario())) == ["conflict"] * 7 + ["won"]


def test_sqlite_acquire_commits_nothing_until_caller_commits(tmp_path):
    async def scenario():
        engine, factory = await _sqlite(tmp_path / "rollback.sqlite3")
        try:
            async with factory() as db:
                await acquire_device_lease(db, 1, owner_id=None, owner_label="x")
                await db.rollback()
            async with factory() as db:
                leases = (await db.execute(select(DeviceLease))).scalars().all()
                status = (await db.get(Device, 1)).status
            return leases, status
        finally:
            await engine.dispose()

    leases, status = asyncio.run(scenario())
    assert leases == []
    assert status is DeviceStatus.online


def test_sqlite_unique_conflict_keeps_caller_transaction_usable(tmp_path):
    path = tmp_path / "race.sqlite3"

    async def scenario():
        engine, factory = await _sqlite(path)
        injected = []

        # 本会话读到“无租约”后、首次写设备前，另一连接抢先提交租约，迫使 INSERT 撞唯一约束。
        @event.listens_for(engine.sync_engine, "before_cursor_execute")
        def _race(_conn, _cursor, statement, *_):
            if statement.startswith("UPDATE devices") and not injected:
                injected.append(True)
                future = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S.%f")
                other = sqlite3.connect(path, timeout=5)
                try:
                    other.execute(
                        "INSERT INTO device_leases (device_id, lease_token, owner_label, acquired_at, heartbeat_at, "
                        "expires_at) VALUES (1, 'other', 'y', ?, ?, ?)",
                        (future, future, future),
                    )
                    other.commit()
                finally:
                    other.close()

        try:
            async with factory() as db:
                with pytest.raises(DeviceLeaseConflict):
                    await acquire_device_lease(db, 1, owner_id=None, owner_label="x")
                await db.commit()
            async with factory() as db:
                tokens = (await db.execute(select(DeviceLease.lease_token))).scalars().all()
            return injected, tokens
        finally:
            await engine.dispose()

    injected, tokens = asyncio.run(scenario())
    assert injected == [True]
    assert tokens == ["other"]


def _other_connection(path: Path, sql: str, *params) -> None:
    other = sqlite3.connect(path, timeout=5)
    try:
        other.execute(sql, params)
        other.commit()
    finally:
        other.close()


def _inject_before(engine, prefix: str, path: Path, sql: str, *params) -> list:
    """在本会话首次执行 prefix 语句之前，由另一连接抢先提交一次写入。"""
    fired = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _race(_conn, _cursor, statement, *_):
        if statement.startswith(prefix) and not fired:
            fired.append(True)
            _other_connection(path, sql, *params)

    return fired


def _sqlite_time(delta_seconds: int) -> str:
    moment = datetime.now(timezone.utc) + timedelta(seconds=delta_seconds)
    return moment.strftime("%Y-%m-%d %H:%M:%S.%f")


async def _seed_lease(factory, token: str = "old", delta_seconds: int = -5) -> None:
    moment = datetime.now(timezone.utc) + timedelta(seconds=delta_seconds)
    async with factory() as db:
        (await db.get(Device, 1)).status = DeviceStatus.busy
        db.add(
            DeviceLease(
                device_id=1,
                lease_token=token,
                owner_label="x",
                acquired_at=moment,
                heartbeat_at=moment,
                expires_at=moment,
            )
        )
        await db.commit()


async def _state(factory):
    async with factory() as db:
        tokens = (await db.execute(select(DeviceLease.lease_token))).scalars().all()
        status = (await db.execute(select(Device.status).where(Device.id == 1))).scalar_one_or_none()
    return tokens, status


def test_sqlite_naive_read_back_is_treated_as_utc(tmp_path):
    path = tmp_path / "naive.sqlite3"

    async def scenario():
        engine, factory = await _sqlite(path)
        try:
            async with factory() as db:
                lease = await acquire_device_lease(db, 1, owner_id=None, owner_label="first")
                token = lease.lease_token
                await db.commit()
            # 新会话读回的是无时区时间：有效租约不能被当成已过期而被接管。
            async with factory() as db:
                with pytest.raises(DeviceLeaseConflict):
                    await acquire_device_lease(db, 1, owner_id=None, owner_label="second")
                await db.rollback()
            async with factory() as db:
                assert (await get_active_device_lease(db, 1, token)) is not None
                await heartbeat_device_lease(db, 1, token, ttl_seconds=60)
                await db.commit()
            assert (await _state(factory))[0] == [token]
            _other_connection(path, "UPDATE device_leases SET expires_at = ?", _sqlite_time(-5))
            async with factory() as db:
                assert (await get_active_device_lease(db, 1, token)) is None
                with pytest.raises(DeviceLeaseConflict):
                    await heartbeat_device_lease(db, 1, token)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["release", "reclaim"])
def test_sqlite_stale_cleanup_does_not_delete_takeover_lease(tmp_path, operation):
    """接管者未提交时清理方阻塞在写锁上；提交后新租约复用了同一 id，也不能被删。"""

    async def scenario():
        engine, factory = await _sqlite(tmp_path / "stale.sqlite3")
        try:
            await _seed_lease(factory)
            async with factory() as taker, factory() as cleaner:
                lease = await acquire_device_lease(taker, 1, owner_id=None, owner_label="taker")
                assert lease.id == 1  # 前提：SQLite 确实复用了 id。
                if operation == "release":
                    pending = asyncio.create_task(release_device_lease(cleaner, 1, "old"))
                else:
                    pending = asyncio.create_task(reclaim_expired_device_leases(cleaner))
                await asyncio.sleep(0.5)
                assert not pending.done()
                await taker.commit()
                result = await pending
                await cleaner.commit()
            return result, lease.lease_token, await _state(factory)
        finally:
            await engine.dispose()

    result, token, state = asyncio.run(scenario())
    assert not result
    assert state == ([token], DeviceStatus.busy)


@pytest.mark.parametrize("reuse_id", [True, False])
def test_sqlite_heartbeat_after_takeover_raises_conflict(tmp_path, reuse_id):
    path = tmp_path / "heartbeat.sqlite3"

    async def scenario():
        engine, factory = await _sqlite(path)
        try:
            await _seed_lease(factory, token="mine", delta_seconds=60)
            future = _sqlite_time(600)
            fired = _inject_before(
                engine,
                "UPDATE device_leases",
                path,
                "UPDATE device_leases SET id = ?, lease_token = 'other', expires_at = ?",
                1 if reuse_id else 2,
                future,
            )
            async with factory() as db:
                with pytest.raises(DeviceLeaseConflict):
                    await heartbeat_device_lease(db, 1, "mine", ttl_seconds=60)
                await db.rollback()
            other = sqlite3.connect(path)
            try:
                row = other.execute("SELECT lease_token, expires_at FROM device_leases").fetchone()
            finally:
                other.close()
            return fired, row, future
        finally:
            await engine.dispose()

    fired, row, future = asyncio.run(scenario())
    assert fired == [True]
    assert row == ("other", future)


def test_sqlite_takeover_keeps_lease_renewed_before_delete(tmp_path):
    path = tmp_path / "renewed.sqlite3"

    async def scenario():
        engine, factory = await _sqlite(path)
        try:
            await _seed_lease(factory)
            fired = _inject_before(
                engine, "DELETE FROM device_leases", path, "UPDATE device_leases SET expires_at = ?", _sqlite_time(600)
            )
            async with factory() as db:
                with pytest.raises(DeviceLeaseConflict):
                    await acquire_device_lease(db, 1, owner_id=None, owner_label="x")
                await db.commit()
            return fired, await _state(factory)
        finally:
            await engine.dispose()

    fired, state = asyncio.run(scenario())
    assert fired == [True]
    assert state == (["old"], DeviceStatus.busy)


def test_sqlite_takeover_proceeds_when_expired_lease_was_reclaimed(tmp_path):
    path = tmp_path / "reclaimed.sqlite3"

    async def scenario():
        engine, factory = await _sqlite(path)
        try:
            await _seed_lease(factory)
            fired = _inject_before(engine, "DELETE FROM device_leases", path, "DELETE FROM device_leases")
            async with factory() as db:
                lease = await acquire_device_lease(db, 1, owner_id=None, owner_label="x")
                await db.commit()
            return fired, lease.lease_token, await _state(factory)
        finally:
            await engine.dispose()

    fired, token, state = asyncio.run(scenario())
    assert fired == [True]
    assert state == ([token], DeviceStatus.busy)


def test_sqlite_device_going_offline_during_acquire_is_not_overwritten(tmp_path):
    path = tmp_path / "offline.sqlite3"

    async def scenario():
        engine, factory = await _sqlite(path)
        try:
            fired = _inject_before(engine, "UPDATE devices", path, "UPDATE devices SET status = 'offline'")
            async with factory() as db:
                with pytest.raises(DeviceLeaseConflict):
                    await acquire_device_lease(db, 1, owner_id=None, owner_label="x")
                await db.commit()
            return fired, await _state(factory)
        finally:
            await engine.dispose()

    fired, state = asyncio.run(scenario())
    assert fired == [True]
    assert state == ([], DeviceStatus.offline)


def test_sqlite_device_deleted_during_acquire_raises_lookup_error(tmp_path):
    path = tmp_path / "deleted.sqlite3"

    async def scenario():
        engine, factory = await _sqlite(path)
        try:
            fired = _inject_before(engine, "UPDATE devices", path, "DELETE FROM devices")
            async with factory() as db:
                with pytest.raises(LookupError):
                    await acquire_device_lease(db, 1, owner_id=None, owner_label="x")
            return fired
        finally:
            await engine.dispose()

    assert asyncio.run(scenario()) == [True]


def test_sqlite_unrelated_integrity_error_is_not_reported_as_occupied(tmp_path):
    async def scenario():
        engine, factory = await _sqlite(tmp_path / "fk.sqlite3")
        try:
            async with factory() as db:
                with pytest.raises(IntegrityError):
                    await acquire_device_lease(db, 1, owner_id=999, owner_label="x")
                await db.rollback()
            return await _state(factory)
        finally:
            await engine.dispose()

    assert asyncio.run(scenario()) == ([], DeviceStatus.online)


def test_sqlite_status_drift_acquire_still_rolls_back(tmp_path):
    """设备已是 busy 但没有租约时，保存点同样不能成为最外层事务。"""
    path = tmp_path / "drift.sqlite3"

    async def scenario():
        engine, factory = await _sqlite(path)
        try:
            _other_connection(path, "UPDATE devices SET status = 'busy'")
            async with factory() as db:
                await acquire_device_lease(db, 1, owner_id=None, owner_label="x")
                await db.rollback()
            return await _state(factory)
        finally:
            await engine.dispose()

    assert asyncio.run(scenario()) == ([], DeviceStatus.busy)


def _seed_expired_busy_lease(path: Path) -> None:
    async def seed():
        engine, factory = await _sqlite(path)
        try:
            await _seed_lease(factory)
        finally:
            await engine.dispose()

    asyncio.run(seed())


def _rows(path: Path):
    con = sqlite3.connect(path)
    try:
        tokens = [row[0] for row in con.execute("SELECT lease_token FROM device_leases")]
        status = con.execute("SELECT status FROM devices WHERE id = 1").fetchone()[0]
    finally:
        con.close()
    return tokens, status


@pytest.mark.parametrize("renewed_before_delete", [False, True])
def test_sqlite_sync_reclaim_matches_the_async_rules(tmp_path, renewed_before_delete):
    # 本地设备巡检在工作线程里用同步版回收：过期才删、删掉才改在线；删除前被续期的租约要保留。
    path = tmp_path / "sync-reclaim.sqlite3"
    _seed_expired_busy_lease(path)
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"timeout": 5})
    fired = []

    @event.listens_for(engine, "before_cursor_execute")
    def _renew(_conn, _cursor, statement, *_):
        if renewed_before_delete and statement.startswith("DELETE FROM device_leases") and not fired:
            fired.append(True)
            _other_connection(path, "UPDATE device_leases SET expires_at = ?", _sqlite_time(600))

    try:
        with Session(engine) as session:
            reclaimed = reclaim_expired_device_leases_sync(session)
            session.commit()
    finally:
        engine.dispose()

    if renewed_before_delete:
        assert fired == [True]
        assert (reclaimed, _rows(path)) == (0, (["old"], DeviceStatus.busy.value))
    else:
        assert (reclaimed, _rows(path)) == (1, ([], DeviceStatus.online.value))
