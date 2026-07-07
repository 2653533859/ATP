import asyncio
import base64
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 强制覆盖（不用 setdefault）：其他测试可能已把这些 stub 设成不完整版本
sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_engineer=lambda: None,
    require_admin=lambda: None,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)
sys.modules["app.worker.tasks"] = types.SimpleNamespace(
    run_test_case=types.SimpleNamespace(delay=lambda *_a, **_kw: None)
)

from fastapi import HTTPException

from app.api.v1.cases import runs as runs_module
from app.models.bootstrap import load_all_models
from app.models.case import RunStatus, TestRun
from app.schemas.case import PaginatedRunsOut, RunCursorPage


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _ExecResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _ScalarResult(self._items)


class _FakeDB:
    def __init__(self, items, count=None):
        self.items = items
        self.count = count if count is not None else len(items)
        self.statements = []
        self.scalar_calls = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _ExecResult(self.items)

    async def scalar(self, stmt):
        self.scalar_calls.append(stmt)
        return self.count


def _make_run(id_: int, case_id: int = 1, created_at: datetime | None = None) -> TestRun:
    return TestRun(
        id=id_,
        case_id=case_id,
        triggered_by=1,
        trace_id=None,
        status=RunStatus.passed,
        environment=None,
        duration_ms=100,
        error_message=None,
        result_summary={},
        created_at=created_at or datetime.now(timezone.utc),
    )


def test_offset_pagination_returns_paginated_shape():
    load_all_models()
    runs = [_make_run(i) for i in (3, 2, 1)]
    db = _FakeDB(items=runs, count=3)

    result = asyncio.run(
        runs_module.list_runs(
            case_id=1,
            page=1,
            page_size=20,
            cursor=None,
            limit=20,
            db=db,
            _=None,
        )
    )

    assert isinstance(result, PaginatedRunsOut)
    assert result.total == 3
    assert result.page == 1
    assert result.page_size == 20
    assert len(result.items) == 3
    # 列表项 schema 已收敛为不含 steps 的 TestRunListItem
    assert not hasattr(result.items[0], "steps")


def test_cursor_pagination_returns_cursor_shape_with_has_more():
    load_all_models()
    runs = [
        _make_run(5, created_at=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)),
        _make_run(4, created_at=datetime(2026, 5, 20, 11, 0, 0, tzinfo=timezone.utc)),
        _make_run(3, created_at=datetime(2026, 5, 20, 10, 0, 0, tzinfo=timezone.utc)),
    ]
    db = _FakeDB(items=runs)

    cursor = base64.urlsafe_b64encode(b"2026-05-20T13:00:00+00:00|9").decode()
    result = asyncio.run(
        runs_module.list_runs(
            case_id=None,
            page=1,
            page_size=20,
            cursor=cursor,
            limit=2,
            db=db,
            _=None,
        )
    )

    assert isinstance(result, RunCursorPage)
    assert result.has_more is True
    assert len(result.items) == 2
    assert result.next_cursor is not None
    # cursor 应可逆解码
    ts, run_id = runs_module._decode_cursor(result.next_cursor)
    assert run_id == result.items[-1].id


def test_cursor_pagination_no_more_when_under_limit():
    load_all_models()
    runs = [_make_run(2), _make_run(1)]
    db = _FakeDB(items=runs)

    cursor = base64.urlsafe_b64encode(b"2026-05-20T13:00:00+00:00|9").decode()
    result = asyncio.run(
        runs_module.list_runs(
            case_id=None,
            page=1,
            page_size=20,
            cursor=cursor,
            limit=5,
            db=db,
            _=None,
        )
    )

    assert isinstance(result, RunCursorPage)
    assert result.has_more is False
    assert result.next_cursor is None
    assert len(result.items) == 2


def test_invalid_cursor_raises_400():
    load_all_models()
    db = _FakeDB(items=[])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            runs_module.list_runs(
                case_id=None,
                page=1,
                page_size=20,
                cursor="this-is-not-valid-base64-payload!!!",
                limit=20,
                db=db,
                _=None,
            )
        )
    assert exc.value.status_code == 400


def test_cursor_encode_decode_roundtrip():
    ts = datetime(2026, 5, 20, 12, 34, 56, tzinfo=timezone.utc)
    cursor = runs_module._encode_cursor(ts, 42)
    decoded_ts, decoded_id = runs_module._decode_cursor(cursor)
    assert decoded_ts == ts
    assert decoded_id == 42
