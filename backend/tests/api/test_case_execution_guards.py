import asyncio
import importlib
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

_REAL_TRACING = importlib.import_module("app.core.tracing")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


async def _noop_invalidate_stats_cache():
    return None


sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(get_current_user=lambda: None, require_engineer=lambda: None)
sys.modules["app.api.v1.statistics"] = types.SimpleNamespace(invalidate_stats_cache=_noop_invalidate_stats_cache)
sys.modules["app.core.tracing"] = types.SimpleNamespace(
    get_trace_id=lambda: None,
    generate_trace_id=lambda: "trace-test",
    set_trace_id=lambda value: value,
    reset_trace_id=lambda _token: None,
)
sys.modules["app.worker.tasks"] = types.SimpleNamespace(
    run_test_case=types.SimpleNamespace(delay=lambda *_args, **_kwargs: None)
)

from app.api.v1 import cases
sys.modules["app.core.tracing"] = _REAL_TRACING
from app.models.bootstrap import load_all_models
from app.models.case import CaseStatus, CaseType, RunStatus, TestCase
from app.schemas.case import RunTriggerRequest, TestRunOut


def _case(status: CaseStatus, review_status: str, automation_status: str) -> TestCase:
    case = TestCase(
        id=5,
        name="Execution Case",
        description=None,
        case_code="ATP-EXEC-API-0001",
        summary="execute",
        case_type=CaseType.api,
        status=status,
        priority="P1",
        case_level="core",
        review_status=review_status,
        automation_status=automation_status,
        tags=[],
        module_id=2,
        creator_id=9,
        owner_id=9,
        preconditions=[],
        postconditions=[],
        config={},
    )
    case.created_at = datetime.now(timezone.utc)
    case.updated_at = datetime.now(timezone.utc)
    case.steps = []
    return case


class _RunQueryResult:
    def __init__(self, run_obj):
        self.run_obj = run_obj

    def scalar_one(self):
        return self.run_obj


class _TriggerRunDB:
    def __init__(self, case_obj=None, loaded_run=None):
        self.case_obj = case_obj
        self.loaded_run = loaded_run
        self.added = []

    async def get(self, model, _pk):
        if getattr(model, "__name__", "") == "TestCase":
            return self.case_obj
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        if self.added:
            self.added[0].id = 21
            self.added[0].created_at = datetime.now(timezone.utc)

    async def refresh(self, _obj):
        return None

    async def execute(self, _stmt):
        return _RunQueryResult(self.loaded_run)


def test_trigger_run_blocks_unapproved_case():
    load_all_models()
    db = _TriggerRunDB(case_obj=_case(CaseStatus.draft, "pending", "auto"))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            cases.trigger_run(
                case_id=5,
                body=RunTriggerRequest(extra_vars={}),
                db=db,
                current_user=types.SimpleNamespace(id=9),
            )
        )

    assert exc_info.value.status_code == 409


def test_trigger_run_blocks_manual_only_case():
    load_all_models()
    db = _TriggerRunDB(case_obj=_case(CaseStatus.active, "approved", "manual"))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            cases.trigger_run(
                case_id=5,
                body=RunTriggerRequest(extra_vars={}),
                db=db,
                current_user=types.SimpleNamespace(id=9),
            )
        )

    assert exc_info.value.status_code == 409


def test_trigger_run_accepts_ready_case_and_dispatches_worker(monkeypatch):
    load_all_models()
    loaded_run = types.SimpleNamespace(
        id=21,
        case_id=5,
        triggered_by=9,
        trace_id="trace-case-21",
        status=RunStatus.pending,
        environment=None,
        duration_ms=None,
        error_message=None,
        result_summary={},
        created_at=datetime.now(timezone.utc),
        steps=[],
    )
    db = _TriggerRunDB(case_obj=_case(CaseStatus.active, "approved", "auto"), loaded_run=loaded_run)
    delayed = {}

    monkeypatch.setattr(
        cases,
        "get_trace_id",
        lambda: "trace-case-21",
    )

    monkeypatch.setattr(
        cases,
        "run_test_case",
        types.SimpleNamespace(delay=lambda run_id, extra_vars, trace_id: delayed.update(run_id=run_id, extra_vars=extra_vars, trace_id=trace_id)),
    )

    result = asyncio.run(
        cases.trigger_run(
            case_id=5,
            body=RunTriggerRequest(extra_vars={"base_url": "http://backend:8000"}),
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    assert isinstance(result, TestRunOut)
    assert result.id == 21
    assert result.trace_id == "trace-case-21"
    assert delayed == {"run_id": 21, "extra_vars": {"base_url": "http://backend:8000"}, "trace_id": "trace-case-21"}
