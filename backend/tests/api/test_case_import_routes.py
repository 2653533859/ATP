import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.api.v1.cases as cases
from app.api.v1.cases import importing
from app.models.case import TestCase
from app.models.project import Module
from app.schemas.case import TestCaseCreate
from app.schemas.case_import import CaseImportRequest


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _DB:
    def __init__(self, module, existing=None, fail_commit=False):
        self.module = module
        self.existing = list(existing or [])
        self.fail_commit = fail_commit
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def get(self, model, key):
        if model is Module and key == self.module.id:
            return self.module
        return None

    async def execute(self, _query):
        return _Result(self.existing)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        if self.added and self.added[-1].id is None:
            self.added[-1].id = 101

    async def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("commit failed")

    async def rollback(self):
        self.rollbacks += 1


def _body(*, name="login", module_id=10, policy="fail"):
    return CaseImportRequest(
        cases=[
            TestCaseCreate(
                name=name,
                case_type="api",
                module_id=module_id,
                steps=[],
            )
        ],
        conflict_policy=policy,
    )


def test_preview_reports_existing_and_duplicate_names(monkeypatch):
    async def allow_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(importing, "assert_project_access", allow_access)
    module = Module(id=10, project_id=1, name="API")
    existing = TestCase(id=7, module_id=10, name="login")
    db = _DB(module, existing=[existing])
    body = CaseImportRequest(cases=[_body().cases[0], _body(name="new").cases[0], _body().cases[0]])

    result = asyncio.run(importing.preview_case_import(1, body, db, SimpleNamespace(id=8)))

    assert result.total == 3
    assert result.valid_count == 1
    assert result.invalid_count == 2
    assert {item.reason for item in result.conflicts} == {"项目中已存在同名用例", "导入内容重复"}


def test_import_rolls_back_when_commit_fails(monkeypatch):
    async def allow_access(*_args, **_kwargs):
        return None

    async def no_dataset(*_args, **_kwargs):
        return None, None

    async def fake_replace(*_args, **_kwargs):
        return None

    async def fake_invalidate(*_args, **_kwargs):
        return None

    monkeypatch.setattr(importing, "assert_project_access", allow_access)
    monkeypatch.setattr(cases, "_resolve_dataset_binding", no_dataset)

    async def fake_generate_code(*_args, **_kwargs):
        return "API-001"

    monkeypatch.setattr(cases, "_generate_case_code", fake_generate_code)
    monkeypatch.setattr(cases, "_replace_case_steps", fake_replace)
    monkeypatch.setattr(cases, "invalidate_stats_cache", fake_invalidate)
    module = Module(id=10, project_id=1, name="API")
    db = _DB(module, fail_commit=True)

    with pytest.raises(RuntimeError, match="commit failed"):
        asyncio.run(importing.import_cases(1, _body(), db, SimpleNamespace(id=8)))

    assert len(db.added) == 1
    assert db.commits == 1
    assert db.rollbacks == 1
