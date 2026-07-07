"""Q5 长尾 #1 — /statistics/case-type-distribution 测试。"""

import asyncio
import importlib
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_admin=_p3c_noop,
    require_engineer=_p3c_noop,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(
    delete_json_cache_pattern=lambda *args, **kwargs: None,
    get_json_cache=lambda *args, **kwargs: None,
    set_json_cache=lambda *args, **kwargs: None,
)
sys.modules.pop("app.api.v1.statistics", None)
statistics = importlib.import_module("app.api.v1.statistics")

from app.models.bootstrap import load_all_models  # noqa: F401


class _Row:
    def __init__(self, case_type, total, passed, failed, error):
        self.case_type = case_type
        self.total = total
        self.passed = passed
        self.failed = failed
        self.error = error


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _FakeResult(self._rows)


def _stub_cache(monkeypatch):
    async def fake_get(*_a, **_kw):
        return None

    async def fake_set(*_a, **_kw):
        return None

    monkeypatch.setattr(statistics, "get_json_cache", fake_get)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set)
    monkeypatch.setattr(statistics, "_since", lambda _days: datetime(2026, 5, 1, tzinfo=timezone.utc))


def test_case_type_distribution_basic(monkeypatch):
    _stub_cache(monkeypatch)

    from app.models.case import CaseType

    rows = [
        _Row(CaseType.api, total=20, passed=15, failed=4, error=1),
        _Row(CaseType.web, total=10, passed=7, failed=2, error=1),
    ]
    db = _FakeDB(rows)

    result = asyncio.run(statistics.get_case_type_distribution(project_id=None, days=30, db=db, _=None))

    assert len(result) == 2
    assert result[0].case_type == "api"
    assert result[0].total == 20
    assert result[0].passed == 15
    assert result[0].failed == 4
    assert result[0].error == 1
    assert result[0].pass_rate == 75.0

    assert result[1].case_type == "web"
    assert result[1].pass_rate == 70.0
    assert len(db.statements) == 1


def test_case_type_distribution_filters_by_project(monkeypatch):
    _stub_cache(monkeypatch)

    from app.models.case import CaseType

    rows = [_Row(CaseType.android, total=5, passed=5, failed=0, error=0)]
    db = _FakeDB(rows)

    result = asyncio.run(statistics.get_case_type_distribution(project_id=42, days=7, db=db, _=None))

    assert len(result) == 1
    assert result[0].case_type == "android"
    assert result[0].pass_rate == 100.0
    # 带 project_id 时 SQL 多一层 join Module —— 仅断言执行一次
    assert len(db.statements) == 1


def test_case_type_distribution_empty(monkeypatch):
    _stub_cache(monkeypatch)

    db = _FakeDB([])
    result = asyncio.run(statistics.get_case_type_distribution(project_id=None, days=30, db=db, _=None))
    assert result == []


def test_case_type_distribution_handles_zero_total(monkeypatch):
    """异常防御：total=0 时 pass_rate 应为 0.0 而不是 ZeroDivisionError。"""
    _stub_cache(monkeypatch)

    from app.models.case import CaseType

    rows = [_Row(CaseType.api, total=0, passed=0, failed=0, error=0)]
    db = _FakeDB(rows)

    result = asyncio.run(statistics.get_case_type_distribution(project_id=None, days=30, db=db, _=None))
    assert len(result) == 1
    assert result[0].pass_rate == 0.0
