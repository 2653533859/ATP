import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(get_current_user=lambda: None)

from app.api.v1 import traces
from app.models.case import RunStatus
from app.models.plan import PlanRunStatus, TriggerType
from app.models.suite import SuiteRunStatus


class _FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _FakeExecuteResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _FakeScalarResult(self._values)


class _FakeDB:
    def __init__(self, results):
        self._results = results
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return self._results[len(self.statements) - 1]


def test_get_trace_returns_aggregated_run_timeline():
    start = datetime(2026, 4, 4, 8, 0, tzinfo=timezone.utc)
    middle = datetime(2026, 4, 4, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 4, 4, 8, 2, tzinfo=timezone.utc)
    db = _FakeDB(
        [
            _FakeExecuteResult(
                [
                    types.SimpleNamespace(
                        id=11,
                        case_id=101,
                        triggered_by=7,
                        trace_id="trace-xyz",
                        status=RunStatus.passed,
                        environment="daily",
                        duration_ms=1500,
                        error_message=None,
                        result_summary={"steps": 1},
                        created_at=start,
                        steps=[],
                    )
                ]
            ),
            _FakeExecuteResult(
                [
                    types.SimpleNamespace(
                        id=22,
                        suite_id=202,
                        triggered_by=7,
                        trace_id="trace-xyz",
                        status=SuiteRunStatus.running,
                        environment="daily",
                        duration_ms=None,
                        error_message=None,
                        result_summary={"total": 1},
                        case_run_ids=[],
                        created_at=middle,
                    )
                ]
            ),
            _FakeExecuteResult(
                [
                    types.SimpleNamespace(
                        id=33,
                        plan_id=303,
                        triggered_by=None,
                        trace_id="trace-xyz",
                        trigger_type=TriggerType.webhook,
                        status=PlanRunStatus.pending,
                        duration_ms=None,
                        error_message=None,
                        suite_run_ids=[],
                        result_summary={"total": 1},
                        created_at=end,
                    )
                ]
            ),
        ]
    )

    result = asyncio.run(traces.get_trace(trace_id="trace-xyz", db=db, _=None))

    assert result.trace_id == "trace-xyz"
    assert result.total_runs == 3
    assert result.created_at == start
    assert result.last_seen_at == end
    assert [item.id for item in result.case_runs] == [11]
    assert [item.id for item in result.suite_runs] == [22]
    assert [item.id for item in result.plan_runs] == [33]
    assert len(db.statements) == 3


def test_get_trace_returns_404_when_trace_not_found():
    db = _FakeDB([
        _FakeExecuteResult([]),
        _FakeExecuteResult([]),
        _FakeExecuteResult([]),
    ])

    with pytest.raises(traces.HTTPException) as exc:
        asyncio.run(traces.get_trace(trace_id="missing-trace", db=db, _=None))

    assert exc.value.status_code == 404
    assert exc.value.detail == "Trace 不存在"


def test_router_registers_trace_endpoint():
    router_file = Path(__file__).resolve().parents[2] / "app" / "api" / "v1" / "router.py"
    content = router_file.read_text(encoding="utf-8")

    assert "traces" in content
    assert "router.include_router(traces.router)" in content
