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

from app.api.v1 import suites
from app.models.bootstrap import load_all_models
from app.models.project import Project
from app.models.suite import TestSuite
from app.schemas.suite import TestSuiteCreate, TestSuiteUpdate


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
    def __init__(self, *, project=None, suite=None, cases=None):
        self.project = project
        self.suite = suite
        self.cases = cases or []
        self.added = []

    async def get(self, model, pk):
        if model is Project:
            return self.project if self.project and self.project.id == pk else None
        if model is TestSuite:
            return self.suite if self.suite and self.suite.id == pk else None
        return None

    async def execute(self, _stmt):
        return _ExecuteResult(self.cases)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, TestSuite):
            self.suite = obj

    async def commit(self):
        if self.suite is not None and self.suite.id is None:
            self.suite.id = 501

    async def refresh(self, _obj):
        return None


def _project(project_id: int):
    return types.SimpleNamespace(id=project_id, name=f"Project-{project_id}")


def _case(case_id: int, project_id: int):
    return types.SimpleNamespace(id=case_id, module=types.SimpleNamespace(project_id=project_id))


def test_create_suite_persists_valid_ordered_case_ids():
    load_all_models()
    db = _FakeDB(
        project=_project(1),
        cases=[_case(12, 1), _case(11, 1)],
    )

    result = asyncio.run(
        suites.create_suite(
            body=TestSuiteCreate(
                name="Smoke Suite",
                project_id=1,
                case_ids=[
                    {"case_id": 12, "sort": 0},
                    {"case_id": 11, "sort": 1},
                ],
            ),
            db=db,
            current_user=types.SimpleNamespace(id=7),
        )
    )

    assert result.case_ids == [{"case_id": 12, "sort": 0}, {"case_id": 11, "sort": 1}]
    assert db.suite.case_ids == [{"case_id": 12, "sort": 0}, {"case_id": 11, "sort": 1}]


def test_create_suite_rejects_missing_case_id():
    load_all_models()
    db = _FakeDB(
        project=_project(1),
        cases=[_case(11, 1)],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            suites.create_suite(
                body=TestSuiteCreate(
                    name="Broken Suite",
                    project_id=1,
                    case_ids=[
                        {"case_id": 11, "sort": 0},
                        {"case_id": 99, "sort": 1},
                    ],
                ),
                db=db,
                current_user=types.SimpleNamespace(id=7),
            )
        )

    assert exc.value.status_code == 400


def test_create_suite_rejects_duplicate_case_ids():
    load_all_models()
    db = _FakeDB(
        project=_project(1),
        cases=[_case(11, 1)],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            suites.create_suite(
                body=TestSuiteCreate(
                    name="Duplicate Suite",
                    project_id=1,
                    case_ids=[
                        {"case_id": 11, "sort": 0},
                        {"case_id": 11, "sort": 1},
                    ],
                ),
                db=db,
                current_user=types.SimpleNamespace(id=7),
            )
        )

    assert exc.value.status_code == 400


def test_update_suite_rejects_case_from_another_project():
    load_all_models()
    db = _FakeDB(
        suite=TestSuite(id=33, name="Smoke", project_id=1, creator_id=7),
        cases=[_case(22, 2)],
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            suites.update_suite(
                suite_id=33,
                body=TestSuiteUpdate(case_ids=[{"case_id": 22, "sort": 0}]),
                db=db,
                _=types.SimpleNamespace(id=7),
            )
        )

    assert exc.value.status_code == 400
