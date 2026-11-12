"""设备包名快照服务：序列化、stale 判定与历史裁剪。"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models import load_all_models
from app.services.device_packages import (
    SNAPSHOT_STALE_SECONDS,
    list_snapshots,
    save_snapshot,
    serialize_snapshot,
)

load_all_models()


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))


class _DB:
    def __init__(self, select_rows=()):
        self.added = []
        self.flushed = 0
        self.statements = []
        self._select_rows = list(select_rows)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushed += 1

    async def execute(self, statement):
        self.statements.append(statement)
        if statement.is_select:
            return _Result(self._select_rows)
        return _Result([])


def _snapshot(read_at, packages=("com.demo.app",), current_package="com.demo.app"):
    return SimpleNamespace(
        device_id=3,
        serial="172.16.101.11:5555",
        current_package=current_package,
        current_activity=".MainActivity",
        packages=list(packages),
        source="refresh",
        triggered_by=7,
        read_at=read_at,
    )


def test_serialize_marks_recent_snapshot_fresh():
    payload = serialize_snapshot(_snapshot(datetime.now(timezone.utc) - timedelta(seconds=30)))
    assert payload["stale"] is False
    assert payload["packages"] == ["com.demo.app"]
    assert payload["source"] == "refresh"


def test_serialize_marks_old_or_naive_snapshot_stale():
    old = serialize_snapshot(_snapshot(datetime.now(timezone.utc) - timedelta(seconds=SNAPSHOT_STALE_SECONDS + 5)))
    assert old["stale"] is True

    # SQLite 读出的 naive datetime 按 UTC 解释，避免被误判为“未来时间”
    naive = serialize_snapshot(_snapshot(datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)))
    assert naive["stale"] is False


def test_save_snapshot_normalizes_payload_and_keeps_history():
    db = _DB()
    snapshot = asyncio.run(
        save_snapshot(
            db,
            device_id=3,
            serial="172.16.101.11:5555",
            payload={
                "current_package": "com.demo.app",
                "current_activity": ".MainActivity",
                "packages": ["com.demo.app", 42],
            },
            source="refresh",
            triggered_by=7,
        )
    )

    assert snapshot.device_id == 3
    assert snapshot.packages == ["com.demo.app", "42"]
    assert snapshot.source == "refresh"
    assert snapshot.triggered_by == 7
    assert snapshot.read_at is not None
    assert db.added == [snapshot]
    assert db.flushed == 1
    assert len(db.statements) == 1


def test_save_snapshot_prunes_beyond_history_limit():
    db = _DB(select_rows=[101, 102])
    asyncio.run(
        save_snapshot(
            db,
            device_id=3,
            serial="SERIAL",
            payload={"packages": []},
        )
    )

    assert any(statement.is_delete for statement in db.statements)


def test_list_snapshots_clamps_limit_and_returns_rows():
    db = _DB(select_rows=[_snapshot(datetime.now(timezone.utc))])
    rows = asyncio.run(list_snapshots(db, 3, limit=0))
    assert len(rows) == 1
    assert "LIMIT" in str(db.statements[0]).upper()
