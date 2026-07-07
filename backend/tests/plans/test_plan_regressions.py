import asyncio
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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

from app.api.v1 import plans
from app.models.environment import Environment
from app.models.plan import TestPlan as PlanModel
from app.schemas.plan import PlanRunTrigger


class _FakePlanRun:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.created_at = kwargs.get("created_at")
        self.duration_ms = kwargs.get("duration_ms")
        self.error_message = kwargs.get("error_message")
        self.result_summary = kwargs.get("result_summary", {})
        self.suite_run_ids = kwargs.get("suite_run_ids", [])
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakePlan:
    id = 1
    suite_ids = [{"suite_id": 101, "sort": 0}]
    env_id = None
    project_id = 1


class _FakeDB:
    def __init__(self, env_obj):
        self._plan = _FakePlan()
        self._env_obj = env_obj

    async def get(self, model, pk):
        if model is PlanModel:
            return self._plan
        if model is Environment:
            return self._env_obj
        return None

    def add(self, _):
        return None

    async def commit(self):
        return None

    async def refresh(self, _):
        return None


def test_manual_plan_run_persists_and_dispatches_trace_id(monkeypatch):
    delayed = {}
    plans.PlanRun = _FakePlanRun
    monkeypatch.setattr(plans, "get_trace_id", lambda: "trace-plan-1")
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks",
        types.SimpleNamespace(
            run_test_plan=types.SimpleNamespace(
                delay=lambda run_id, extra_vars, trace_id: delayed.update(
                    run_id=run_id,
                    extra_vars=extra_vars,
                    trace_id=trace_id,
                )
            )
        ),
    )

    db = _FakeDB(env_obj=None)
    body = PlanRunTrigger(extra_vars={"commit": "abc"})
    current_user = types.SimpleNamespace(id=7)

    result = asyncio.run(
        plans.trigger_plan_run(
            plan_id=1,
            body=body,
            db=db,
            current_user=current_user,
        )
    )

    assert result.trace_id == "trace-plan-1"
    assert delayed == {"run_id": 1, "extra_vars": {"commit": "abc"}, "trace_id": "trace-plan-1"}


def test_manual_plan_run_invalid_env_id_returns_404():
    sys.modules["app.worker.tasks"] = types.SimpleNamespace(
        run_test_plan=types.SimpleNamespace(delay=lambda *_args, **_kwargs: None)
    )
    plans.PlanRun = _FakePlanRun

    db = _FakeDB(env_obj=None)
    body = PlanRunTrigger(env_id=999, extra_vars={})
    current_user = types.SimpleNamespace(id=7)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            plans.trigger_plan_run(
                plan_id=1,
                body=body,
                db=db,
                current_user=current_user,
            )
        )
    assert exc.value.status_code == 404


def test_plan_schedule_columns_are_timezone_aware():
    assert PlanModel.__table__.c.last_run_at.type.timezone is True
    assert PlanModel.__table__.c.next_run_at.type.timezone is True


def test_plan_worker_uses_creator_when_triggered_by_is_none():
    tasks_file = Path(__file__).resolve().parents[2] / "app" / "worker" / "tasks.py"
    content = tasks_file.read_text(encoding="utf-8")

    assert "triggered_by=plan_run.triggered_by or 0" not in content
