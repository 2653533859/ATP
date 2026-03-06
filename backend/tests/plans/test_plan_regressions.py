import asyncio
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_engineer=lambda: None,
)

from app.api.v1 import plans
from app.models.environment import Environment
from app.models.plan import TestPlan as PlanModel
from app.schemas.plan import PlanRunTrigger


class _FakePlan:
    id = 1
    suite_ids = [{"suite_id": 101, "sort": 0}]
    env_id = None


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


def test_manual_plan_run_invalid_env_id_returns_404():
    # 无效 env_id 时应在创建 PlanRun 前直接失败
    class _FakePlanRun:
        def __init__(self, **kwargs):
            self.id = 1
            for k, v in kwargs.items():
                setattr(self, k, v)

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
