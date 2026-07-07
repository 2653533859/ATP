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
from app.models.bootstrap import load_all_models
from app.models.environment import Environment
from app.models.plan import TestPlan
from app.models.project import Project
from app.schemas.plan import TestPlanCreate, TestPlanUpdate
from app.models.suite import TestSuite


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _ExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _ScalarResult(self._items)


class _FakeDB:
    def __init__(self, *, project=None, plan=None, suites=None, env=None):
        self.project = project
        self.plan = plan
        self.suites = suites or []
        self.env = env
        self.added = []

    async def get(self, model, pk):
        if model is Project:
            return self.project if self.project and self.project.id == pk else None
        if model is TestPlan:
            return self.plan if self.plan and self.plan.id == pk else None
        if model is Environment:
            return self.env if self.env and self.env.id == pk else None
        return None

    async def execute(self, _stmt):
        return _ExecuteResult(self.suites)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, TestPlan):
            self.plan = obj

    async def commit(self):
        if self.plan is not None and self.plan.id is None:
            self.plan.id = 601

    async def refresh(self, _obj):
        return None


def _project(project_id: int):
    return types.SimpleNamespace(id=project_id, name=f"Project-{project_id}")


def _suite(suite_id: int, project_id: int):
    return types.SimpleNamespace(id=suite_id, project_id=project_id)


def _env(env_id: int, project_id: int):
    return types.SimpleNamespace(id=env_id, name=f"Env-{env_id}", project_id=project_id)


def test_create_plan_persists_valid_ordered_suite_ids():
    load_all_models()
    db = _FakeDB(
        project=_project(1),
        suites=[_suite(102, 1), _suite(101, 1)],
    )

    result = asyncio.run(
        plans.create_plan(
            body=TestPlanCreate(
                name="Daily Plan",
                project_id=1,
                suite_ids=[
                    {"suite_id": 102, "sort": 0},
                    {"suite_id": 101, "sort": 1},
                ],
            ),
            db=db,
            current_user=types.SimpleNamespace(id=8),
        )
    )

    assert result.suite_ids == [{"suite_id": 102, "sort": 0}, {"suite_id": 101, "sort": 1}]
    assert db.plan.suite_ids == [{"suite_id": 102, "sort": 0}, {"suite_id": 101, "sort": 1}]


def test_create_plan_rejects_missing_suite_id():
    load_all_models()
    db = _FakeDB(
        project=_project(1),
        suites=[_suite(101, 1)],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            plans.create_plan(
                body=TestPlanCreate(
                    name="Broken Plan",
                    project_id=1,
                    suite_ids=[
                        {"suite_id": 101, "sort": 0},
                        {"suite_id": 999, "sort": 1},
                    ],
                ),
                db=db,
                current_user=types.SimpleNamespace(id=8),
            )
        )

    assert exc.value.status_code == 400


def test_create_plan_rejects_duplicate_suite_ids():
    load_all_models()
    db = _FakeDB(
        project=_project(1),
        suites=[_suite(101, 1)],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            plans.create_plan(
                body=TestPlanCreate(
                    name="Duplicate Plan",
                    project_id=1,
                    suite_ids=[
                        {"suite_id": 101, "sort": 0},
                        {"suite_id": 101, "sort": 1},
                    ],
                ),
                db=db,
                current_user=types.SimpleNamespace(id=8),
            )
        )

    assert exc.value.status_code == 400


def test_update_plan_rejects_suite_from_another_project():
    load_all_models()
    db = _FakeDB(
        plan=TestPlan(id=44, name="Nightly", project_id=1, creator_id=8),
        suites=[_suite(202, 2)],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            plans.update_plan(
                plan_id=44,
                body=TestPlanUpdate(suite_ids=[{"suite_id": 202, "sort": 0}]),
                db=db,
                user=types.SimpleNamespace(id=8),
            )
        )

    assert exc.value.status_code == 400


def test_update_plan_rejects_environment_from_another_project():
    load_all_models()
    db = _FakeDB(
        plan=TestPlan(id=45, name="Nightly", project_id=1, creator_id=8),
        env=_env(9, 2),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            plans.update_plan(
                plan_id=45,
                body=TestPlanUpdate(env_id=9),
                db=db,
                user=types.SimpleNamespace(id=8),
            )
        )

    assert exc.value.status_code == 400
