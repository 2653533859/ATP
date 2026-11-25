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


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_engineer=lambda: None,
    require_admin=_p3c_noop,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)
sys.modules["app.api.v1.statistics"] = types.SimpleNamespace(invalidate_stats_cache=_noop_invalidate_stats_cache)
sys.modules["app.core.tracing"] = types.SimpleNamespace(
    get_trace_id=lambda: None,
    generate_trace_id=lambda: "trace-test",
    set_trace_id=lambda value: value,
    reset_trace_id=lambda _token: None,
    # api_executor / graphql_executor 在 import 期就需要它；直接复用真实实现，避免单文件运行时 ImportError
    inject_w3c_trace_headers=_REAL_TRACING.inject_w3c_trace_headers,
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
        types.SimpleNamespace(
            delay=lambda run_id, extra_vars, trace_id: delayed.update(
                run_id=run_id, extra_vars=extra_vars, trace_id=trace_id
            )
        ),
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


def test_trigger_run_merges_global_project_env_and_extra_vars(monkeypatch):
    from app.api.v1.cases import runs as case_runs
    from app.core.encryption import encrypt
    from app.models.environment import Environment
    from app.models.global_variable import GlobalVariable, ScopeType
    from app.models.project import Module

    load_all_models()
    loaded_run = types.SimpleNamespace(
        id=22,
        case_id=5,
        triggered_by=9,
        trace_id="trace-case-22",
        status=RunStatus.pending,
        environment="staging",
        duration_ms=None,
        error_message=None,
        result_summary={},
        created_at=datetime.now(timezone.utc),
        steps=[],
    )

    class _VarTriggerDB(_TriggerRunDB):
        async def get(self, model, pk):
            name = getattr(model, "__name__", "")
            if name == "TestCase":
                return self.case_obj
            if name == "Module":
                return Module(id=pk, project_id=7, name="M")
            if name == "Environment":
                return Environment(id=pk, project_id=7, name="staging")
            return None

        async def execute(self, stmt):
            sql_text = str(stmt)
            if "global_variables" in sql_text:
                rows = [
                    GlobalVariable(
                        scope_type=ScopeType.global_scope, project_id=None, key="g", value_encrypted=encrypt("1")
                    ),
                    GlobalVariable(
                        scope_type=ScopeType.global_scope,
                        project_id=None,
                        key="shared",
                        value_encrypted=encrypt("global"),
                    ),
                    GlobalVariable(
                        scope_type=ScopeType.project, project_id=7, key="shared", value_encrypted=encrypt("project")
                    ),
                ]
                return types.SimpleNamespace(scalars=lambda: types.SimpleNamespace(all=lambda: rows))
            return await super().execute(stmt)

    async def fake_env_vars(_db, env_id):
        assert env_id == 3
        return {"shared": "env", "env_only": "yes"}

    db = _VarTriggerDB(case_obj=_case(CaseStatus.active, "approved", "auto"), loaded_run=loaded_run)
    delayed = {}
    monkeypatch.setattr(case_runs, "load_environment_variables_map", fake_env_vars)
    monkeypatch.setattr(cases, "get_trace_id", lambda: "trace-case-22")
    monkeypatch.setattr(
        cases,
        "run_test_case",
        types.SimpleNamespace(
            delay=lambda run_id, extra_vars, trace_id: delayed.update(
                run_id=run_id, extra_vars=extra_vars, trace_id=trace_id
            )
        ),
    )

    asyncio.run(
        cases.trigger_run(
            case_id=5,
            body=RunTriggerRequest(env_id=3, extra_vars={"shared": "extra", "override": "1"}),
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    assert delayed["extra_vars"] == {"g": "1", "shared": "extra", "env_only": "yes", "override": "1"}
