import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(get_current_user=lambda: None)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(
    get_json_cache=lambda *args, **kwargs: None,
    set_json_cache=lambda *args, **kwargs: None,
)

from app.api.v1 import statistics


class _FakeExecuteResult:
    def __init__(self, *, scalar_value=None, one_value=None):
        self._scalar_value = scalar_value
        self._one_value = one_value
        self._all_values = None

    @classmethod
    def with_all(cls, values):
        instance = cls()
        instance._all_values = values
        return instance

    def scalar(self):
        return self._scalar_value

    def one(self):
        return self._one_value

    def all(self):
        return self._all_values


class _FakeDB:
    def __init__(self, results):
        self._results = results
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return self._results[len(self.statements) - 1]


def test_get_overview_uses_selected_days_for_run_metrics(monkeypatch):
    since_calls = []
    fixed_since = datetime(2026, 3, 1, tzinfo=timezone.utc)

    def fake_since(days: int):
        since_calls.append(days)
        return fixed_since

    async def fake_get_json_cache(*_args, **_kwargs):
        return None

    async def fake_set_json_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(statistics, "_since", fake_since)
    monkeypatch.setattr(statistics, "get_json_cache", fake_get_json_cache)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set_json_cache)

    db = _FakeDB(
        results=[
            _FakeExecuteResult(scalar_value=12),
            _FakeExecuteResult(one_value=(8, 6)),
            _FakeExecuteResult(scalar_value=3),
        ]
    )

    result = asyncio.run(statistics.get_overview(project_id=None, days=30, db=db, _=None))

    assert result.total_cases == 12
    assert result.total_runs == 8
    assert result.pass_rate == 75.0
    assert result.recent_runs_7d == 3
    assert len(db.statements) == 3
    assert since_calls == [30, 7]


def test_get_overview_returns_cached_result(monkeypatch):
    async def fake_get_json_cache(*_args, **_kwargs):
        return {"total_cases": 5, "total_runs": 3, "pass_rate": 66.7, "recent_runs_7d": 2}

    monkeypatch.setattr(statistics, "get_json_cache", fake_get_json_cache)

    db = _FakeDB(results=[])
    result = asyncio.run(statistics.get_overview(project_id=1, days=7, db=db, _=None))

    assert result.total_cases == 5
    assert result.total_runs == 3
    assert db.statements == []


def test_get_failure_top_includes_project_and_module_ids(monkeypatch):
    fixed_since = datetime(2026, 3, 1, tzinfo=timezone.utc)

    async def fake_get_json_cache(*_args, **_kwargs):
        return None

    async def fake_set_json_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(statistics, "_since", lambda _days: fixed_since)
    monkeypatch.setattr(statistics, "get_json_cache", fake_get_json_cache)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set_json_cache)

    row = types.SimpleNamespace(
        case_id=8,
        project_id=3,
        module_id=5,
        case_name="登录失败",
        case_type="api",
        failure_count=4,
    )
    db = _FakeDB(results=[_FakeExecuteResult.with_all([row])])

    result = asyncio.run(statistics.get_failure_top(project_id=None, days=30, top=10, case_type=None, db=db, _=None))

    assert len(result) == 1
    assert result[0].project_id == 3
    assert result[0].module_id == 5


def test_get_executor_top_returns_executor_stats(monkeypatch):
    fixed_since = datetime(2026, 3, 1, tzinfo=timezone.utc)

    async def fake_get_json_cache(*_args, **_kwargs):
        return None

    async def fake_set_json_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(statistics, "_since", lambda _days: fixed_since)
    monkeypatch.setattr(statistics, "get_json_cache", fake_get_json_cache)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set_json_cache)

    row = types.SimpleNamespace(user_id=7, username="alice", run_count=12)
    db = _FakeDB(results=[_FakeExecuteResult.with_all([row])])

    result = asyncio.run(statistics.get_executor_top(project_id=None, days=30, top=10, case_type=None, db=db, _=None))

    assert len(result) == 1
    assert result[0].user_id == 7
    assert result[0].username == "alice"
    assert result[0].run_count == 12


def test_get_trigger_type_stats_returns_distribution(monkeypatch):
    fixed_since = datetime(2026, 3, 1, tzinfo=timezone.utc)

    async def fake_get_json_cache(*_args, **_kwargs):
        return None

    async def fake_set_json_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(statistics, "_since", lambda _days: fixed_since)
    monkeypatch.setattr(statistics, "get_json_cache", fake_get_json_cache)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set_json_cache)

    rows = [
        types.SimpleNamespace(trigger_type="manual", count=3),
        types.SimpleNamespace(trigger_type="cron", count=5),
    ]
    db = _FakeDB(results=[_FakeExecuteResult.with_all(rows)])

    result = asyncio.run(statistics.get_trigger_type_stats(project_id=None, days=30, db=db, _=None))

    assert [item.trigger_type for item in result] == ["manual", "cron"]
    assert [item.count for item in result] == [3, 5]


def test_get_plan_trend_returns_daily_aggregate(monkeypatch):
    fixed_since = datetime(2026, 3, 1, tzinfo=timezone.utc)

    async def fake_get_json_cache(*_args, **_kwargs):
        return None

    async def fake_set_json_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(statistics, "_since", lambda _days: fixed_since)
    monkeypatch.setattr(statistics, "get_json_cache", fake_get_json_cache)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set_json_cache)

    row = types.SimpleNamespace(date="2026-03-20", total=4, passed=3)
    db = _FakeDB(results=[_FakeExecuteResult.with_all([row])])

    result = asyncio.run(statistics.get_plan_trend(project_id=None, days=30, db=db, _=None))

    assert len(result) == 1
    assert result[0].date == "2026-03-20"
    assert result[0].total == 4
    assert result[0].passed == 3
    assert result[0].rate == 75.0


def test_get_suite_trend_returns_cached_result(monkeypatch):
    async def fake_get_json_cache(*_args, **_kwargs):
        return [{"date": "2026-03-21", "total": 2, "passed": 2, "rate": 100.0}]

    monkeypatch.setattr(statistics, "get_json_cache", fake_get_json_cache)

    db = _FakeDB(results=[])
    result = asyncio.run(statistics.get_suite_trend(project_id=1, days=7, db=db, _=None))

    assert len(result) == 1
    assert result[0].date == "2026-03-21"
    assert result[0].rate == 100.0
    assert db.statements == []
