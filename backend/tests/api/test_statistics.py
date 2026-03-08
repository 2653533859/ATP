import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(get_current_user=lambda: None)

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

    monkeypatch.setattr(statistics, "_since", fake_since)

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


def test_get_failure_top_includes_project_and_module_ids(monkeypatch):
    fixed_since = datetime(2026, 3, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(statistics, "_since", lambda _days: fixed_since)

    row = types.SimpleNamespace(
        case_id=8,
        project_id=3,
        module_id=5,
        case_name="登录失败",
        case_type="api",
        failure_count=4,
    )
    db = _FakeDB(results=[_FakeExecuteResult.with_all([row])])

    result = asyncio.run(statistics.get_failure_top(project_id=None, days=30, top=10, db=db, _=None))

    assert len(result) == 1
    assert result[0].project_id == 3
    assert result[0].module_id == 5
