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

from app.models.bootstrap import load_all_models


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


def test_invalidate_stats_cache_deletes_stats_pattern(monkeypatch):
    deleted_patterns = []

    async def fake_delete_json_cache_pattern(pattern: str):
        deleted_patterns.append(pattern)

    monkeypatch.setattr(statistics, "delete_json_cache_pattern", fake_delete_json_cache_pattern)

    asyncio.run(statistics.invalidate_stats_cache())

    assert deleted_patterns == ["atp:stats:*"]


def test_invalidate_stats_cache_swallows_delete_failure(monkeypatch):
    async def fake_delete_json_cache_pattern(_pattern: str):
        raise RuntimeError("redis delete failed")

    monkeypatch.setattr(statistics, "delete_json_cache_pattern", fake_delete_json_cache_pattern)

    asyncio.run(statistics.invalidate_stats_cache())


async def _read_streaming_response_text(response) -> str:
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
    return "".join(chunks)


def test_statistics_csv_response_writes_header_and_rows():
    response = statistics._csv_response(
        "sample.csv",
        [{"date": "2026-05-27", "total": 2, "rate": 50.0}],
    )

    body = asyncio.run(_read_streaming_response_text(response))

    assert response.headers["content-disposition"] == 'attachment; filename="sample.csv"'
    assert "date,total,rate" in body
    assert "2026-05-27,2,50.0" in body


def test_export_statistics_csv_routes_to_selected_chart(monkeypatch):
    called = {}

    async def fake_pass_rate_trend(project_id, days, case_type, aggregate, db, user):
        called.update(
            {
                "project_id": project_id,
                "days": days,
                "case_type": case_type,
                "aggregate": aggregate,
                "db": db,
                "user": user,
            }
        )
        return [statistics.PassRateTrendItem(date="2026-05-27", total=4, passed=3, rate=75.0)]

    monkeypatch.setattr(statistics, "get_pass_rate_trend", fake_pass_rate_trend)

    db = object()
    user = object()
    response = asyncio.run(
        statistics.export_statistics_csv(
            chart="pass_rate_trend",
            project_id=9,
            days=7,
            aggregate="daily",
            case_type=None,
            top=10,
            db=db,
            _=user,
        )
    )
    body = asyncio.run(_read_streaming_response_text(response))

    assert called["project_id"] == 9
    assert called["days"] == 7
    assert called["db"] is db
    assert called["user"] is user
    assert "date,total,passed,rate" in body
    assert "2026-05-27,4,3,75.0" in body


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


def test_get_overview_survives_cache_read_failure(monkeypatch):
    async def fake_get_json_cache(*_args, **_kwargs):
        raise RuntimeError("redis read failed")

    async def fake_set_json_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(statistics, "get_json_cache", fake_get_json_cache)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set_json_cache)
    monkeypatch.setattr(statistics, "_since", lambda _days: datetime(2026, 3, 1, tzinfo=timezone.utc))

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

    async def fake_get_json_cache(*_args, **_kwargs):
        return {"total_cases": 5, "total_runs": 3, "pass_rate": 66.7, "recent_runs_7d": 2}

    monkeypatch.setattr(statistics, "get_json_cache", fake_get_json_cache)

    db = _FakeDB(results=[])
    result = asyncio.run(statistics.get_overview(project_id=1, days=7, db=db, _=None))

    assert result.total_cases == 5
    assert result.total_runs == 3
    assert db.statements == []


def test_get_overview_survives_cache_write_failure(monkeypatch):
    async def fake_get_json_cache(*_args, **_kwargs):
        return None

    async def fake_set_json_cache(*_args, **_kwargs):
        raise RuntimeError("redis write failed")

    monkeypatch.setattr(statistics, "get_json_cache", fake_get_json_cache)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set_json_cache)
    monkeypatch.setattr(statistics, "_since", lambda _days: datetime(2026, 3, 1, tzinfo=timezone.utc))

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


def test_get_pass_rate_trend_returns_daily_aggregate(monkeypatch):
    load_all_models()
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

    result = asyncio.run(
        statistics.get_pass_rate_trend(
            project_id=2,
            days=30,
            case_type=statistics.CaseType.api,
            db=db,
            _=None,
        )
    )

    assert len(result) == 1
    assert result[0].date == "2026-03-20"
    assert result[0].total == 4
    assert result[0].passed == 3
    assert result[0].rate == 75.0
    stmt = db.statements[0]
    froms = str(stmt.get_final_froms())
    assert "test_cases" in froms
    assert "modules" in froms
    where_parts = [str(clause) for clause in stmt._where_criteria]
    assert any("project_id" in clause for clause in where_parts)
    assert any("case_type" in clause for clause in where_parts)


def test_get_duration_trend_returns_duration_aggregate(monkeypatch):
    load_all_models()
    fixed_since = datetime(2026, 3, 1, tzinfo=timezone.utc)

    async def fake_get_json_cache(*_args, **_kwargs):
        return None

    async def fake_set_json_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(statistics, "_since", lambda _days: fixed_since)
    monkeypatch.setattr(statistics, "get_json_cache", fake_get_json_cache)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set_json_cache)

    row = types.SimpleNamespace(date="2026-03-20", avg_ms=125.6, max_ms=320, cnt=4)
    db = _FakeDB(results=[_FakeExecuteResult.with_all([row])])

    result = asyncio.run(
        statistics.get_duration_trend(
            project_id=2,
            days=30,
            case_type=statistics.CaseType.api,
            db=db,
            _=None,
        )
    )

    assert len(result) == 1
    assert result[0].date == "2026-03-20"
    assert result[0].avg_duration_ms == 126
    assert result[0].max_duration_ms == 320
    assert result[0].run_count == 4
    stmt = db.statements[0]
    froms = str(stmt.get_final_froms())
    assert "test_cases" in froms
    assert "modules" in froms
    where_parts = [str(clause) for clause in stmt._where_criteria]
    assert any("duration_ms" in clause for clause in where_parts)
    assert any("project_id" in clause for clause in where_parts)
    assert any("case_type" in clause for clause in where_parts)


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
    load_all_models()
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

    result = asyncio.run(statistics.get_plan_trend(project_id=9, days=30, db=db, _=None))

    assert len(result) == 1
    assert result[0].date == "2026-03-20"
    assert result[0].total == 4
    assert result[0].passed == 3
    assert result[0].rate == 75.0
    stmt = db.statements[0]
    assert "test_plans" in str(stmt.get_final_froms())
    where_parts = [str(clause) for clause in stmt._where_criteria]
    assert any("project_id" in clause for clause in where_parts)


def test_get_suite_trend_returns_daily_aggregate(monkeypatch):
    load_all_models()
    fixed_since = datetime(2026, 3, 1, tzinfo=timezone.utc)

    async def fake_get_json_cache(*_args, **_kwargs):
        return None

    async def fake_set_json_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(statistics, "_since", lambda _days: fixed_since)
    monkeypatch.setattr(statistics, "get_json_cache", fake_get_json_cache)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set_json_cache)

    row = types.SimpleNamespace(date="2026-03-21", total=2, passed=None)
    db = _FakeDB(results=[_FakeExecuteResult.with_all([row])])

    result = asyncio.run(statistics.get_suite_trend(project_id=1, days=7, db=db, _=None))

    assert len(result) == 1
    assert result[0].date == "2026-03-21"
    assert result[0].total == 2
    assert result[0].passed == 0
    assert result[0].rate == 0.0
    stmt = db.statements[0]
    assert "test_suites" in str(stmt.get_final_froms())
    where_parts = [str(clause) for clause in stmt._where_criteria]
    assert any("project_id" in clause for clause in where_parts)


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


def test_stats_cache_ttl_is_five_minutes():
    assert statistics._STATS_CACHE_TTL == 300


def test_set_json_cache_called_exactly_once_per_request(monkeypatch):
    """回归：去除函数体内冗余缓存逻辑后，单次请求只写一次 cache（装饰器内）。"""
    set_calls = []
    fixed_since = datetime(2026, 3, 1, tzinfo=timezone.utc)

    async def fake_get(*_a, **_kw):
        return None

    async def fake_set(key, *_a, **_kw):
        set_calls.append(key)

    monkeypatch.setattr(statistics, "_since", lambda _: fixed_since)
    monkeypatch.setattr(statistics, "get_json_cache", fake_get)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set)

    db = _FakeDB(
        results=[
            _FakeExecuteResult(scalar_value=12),
            _FakeExecuteResult(one_value=(8, 6)),
            _FakeExecuteResult(scalar_value=3),
        ]
    )
    asyncio.run(statistics.get_overview(project_id=None, days=30, db=db, _=None))

    assert len(set_calls) == 1, f"Expected 1 cache write, got {len(set_calls)}: {set_calls}"


def test_pass_rate_trend_weekly_uses_date_trunc(monkeypatch):
    load_all_models()
    fixed_since = datetime(2026, 3, 1, tzinfo=timezone.utc)

    async def fake_get(*_a, **_kw):
        return None

    async def fake_set(*_a, **_kw):
        return None

    monkeypatch.setattr(statistics, "_since", lambda _: fixed_since)
    monkeypatch.setattr(statistics, "get_json_cache", fake_get)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set)

    db = _FakeDB(results=[_FakeExecuteResult.with_all([])])
    asyncio.run(
        statistics.get_pass_rate_trend(project_id=None, days=180, case_type=None, aggregate="weekly", db=db, _=None)
    )
    sql = str(db.statements[0]).lower()
    assert "date_trunc" in sql


def test_pass_rate_trend_daily_does_not_use_date_trunc(monkeypatch):
    load_all_models()
    fixed_since = datetime(2026, 3, 1, tzinfo=timezone.utc)

    async def fake_get(*_a, **_kw):
        return None

    async def fake_set(*_a, **_kw):
        return None

    monkeypatch.setattr(statistics, "_since", lambda _: fixed_since)
    monkeypatch.setattr(statistics, "get_json_cache", fake_get)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set)

    db = _FakeDB(results=[_FakeExecuteResult.with_all([])])
    asyncio.run(
        statistics.get_pass_rate_trend(project_id=None, days=30, case_type=None, aggregate="daily", db=db, _=None)
    )
    sql = str(db.statements[0]).lower()
    assert "date_trunc" not in sql


def test_aggregate_in_cache_key_isolates_daily_and_weekly(monkeypatch):
    """同一组 project/days/case_type 下，daily 与 weekly 应写到不同的 cache key。"""
    writes = []

    async def fake_get(*_a, **_kw):
        return None

    async def fake_set(key, *_a, **_kw):
        writes.append(key)

    fixed_since = datetime(2026, 3, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(statistics, "_since", lambda _: fixed_since)
    monkeypatch.setattr(statistics, "get_json_cache", fake_get)
    monkeypatch.setattr(statistics, "set_json_cache", fake_set)

    db1 = _FakeDB(results=[_FakeExecuteResult.with_all([])])
    db2 = _FakeDB(results=[_FakeExecuteResult.with_all([])])
    asyncio.run(
        statistics.get_pass_rate_trend(project_id=1, days=30, case_type=None, aggregate="daily", db=db1, _=None)
    )
    asyncio.run(
        statistics.get_pass_rate_trend(project_id=1, days=30, case_type=None, aggregate="weekly", db=db2, _=None)
    )
    assert len(writes) == 2
    assert writes[0] != writes[1]
    assert "aggregate=daily" in writes[0]
    assert "aggregate=weekly" in writes[1]


def test_stats_cache_key_isolated_by_user_even_with_explicit_project():
    builder = statistics._build_stats_cache_key("overview", "project_id", "days")

    first = builder(project_id=3, days=14, _=types.SimpleNamespace(id=8))
    second = builder(project_id=3, days=14, _=types.SimpleNamespace(id=9))

    assert first != second
    assert "user_id=8" in first
