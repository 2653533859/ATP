"""Behavioral contracts for requirement parsing and case traceability."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import requirements
from app.models.bootstrap import load_all_models
from app.models.case import CaseStatus, CaseType, TestCase
from app.models.project import Module, Project
from app.models.requirement import RequirementCaseLink, TestRequirement
from app.schemas.requirement import RequirementCaseLinkCreate, RequirementCreate


load_all_models()
NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, *, rows=None, scalar_rows=None, one=None, count=None):
        self.rows = rows or []
        self.scalar_rows = scalar_rows or []
        self.one = one
        self.count = count

    def all(self):
        return self.rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self.scalar_rows)

    def scalar_one(self):
        return self.count if self.count is not None else self.one

    def scalar_one_or_none(self):
        return self.one


class _DB:
    def __init__(self, *, project=None, case=None, module=None, execute_results=None):
        self.project = project or SimpleNamespace(id=1)
        self.case = case
        self.module = module
        self.execute_results = list(execute_results or [])
        self.added = []
        self.commits = 0
        self.refreshes = 0

    async def get(self, model, entity_id):
        name = getattr(model, "__name__", "")
        if name == "Project":
            return self.project if entity_id == self.project.id else None
        if name == "TestCase":
            return self.case if self.case and entity_id == self.case.id else None
        if name == "Module":
            return self.module if self.module and entity_id == self.module.id else None
        return next((item for item in self.added if isinstance(item, model) and item.id == entity_id), None)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if isinstance(value, TestRequirement) and value.id is None:
                value.id = 41
            if isinstance(value, RequirementCaseLink) and value.id is None:
                value.id = 51

    async def execute(self, _statement):
        if not self.execute_results:
            raise AssertionError("unexpected database query in test")
        return self.execute_results.pop(0)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _value):
        self.refreshes += 1

    async def delete(self, value):
        self.added.remove(value)


def _user():
    return SimpleNamespace(id=7, username="engineer", role="engineer")


def _requirement(*, criteria=None, requirement_id=41):
    item = TestRequirement(
        id=requirement_id,
        project_id=1,
        requirement_code="REQ-001-00041",
        title="邮箱登录",
        description="用户通过邮箱登录系统",
        status="draft",
        priority="P1",
        acceptance_criteria=criteria
        or [{"id": "AC-1", "text": "登录成功进入首页", "priority": "P2", "status": "draft"}],
        source="manual",
        version=1,
        creator_id=7,
    )
    item.created_at = NOW
    item.updated_at = NOW
    return item


def _case(case_id=9):
    item = TestCase(
        id=case_id,
        name="邮箱登录主流程",
        description=None,
        case_code="ATP-API-0009",
        summary="验证邮箱登录",
        case_type=CaseType.api,
        status=CaseStatus.draft,
        priority="P1",
        case_level="core",
        review_status="pending",
        automation_status="auto",
        tags=["登录"],
        module_id=2,
        creator_id=7,
        preconditions=[],
        postconditions=[],
        config={},
    )
    item.created_at = NOW
    item.updated_at = NOW
    return item


def test_parse_requirement_text_creates_editable_criteria_and_terms():
    result = requirements._parse_requirement_text(
        "用户登录\n用户可以使用邮箱登录系统\n- 登录成功后进入首页\n- 密码错误时提示错误"
    )

    assert result.title == "用户登录"
    assert [item.id for item in result.acceptance_criteria] == ["AC-1", "AC-2"]
    assert result.acceptance_criteria[0].text == "登录成功后进入首页"
    assert any("登录" in term for term in result.keywords)
    assert result.warnings


def test_create_requirement_assigns_project_scoped_code_and_audits(monkeypatch):
    async def no_access(*_args, **_kwargs):
        return None

    async def no_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(requirements, "assert_project_access", no_access)
    monkeypatch.setattr(requirements, "write_audit_log", no_audit)
    db = _DB()

    result = asyncio.run(
        requirements.create_requirement(
            body=RequirementCreate(project_id=1, title="  登录  ", acceptance_criteria=[]),
            db=db,
            user=_user(),
        )
    )

    assert result.requirement_code == "REQ-001-00041"
    assert result.title == "登录"
    assert db.commits == 1
    assert db.refreshes == 1
    assert len(db.added) == 1


def test_link_requirement_rejects_case_from_another_project(monkeypatch):
    async def no_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(requirements, "assert_project_access", no_access)

    async def fake_get_requirement(*_args, **_kwargs):
        return _requirement()

    monkeypatch.setattr(requirements, "_get_requirement", fake_get_requirement)
    db = _DB(case=_case(), module=SimpleNamespace(id=2, project_id=2, name="其他项目"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            requirements.link_requirement_case(
                requirement_id=41,
                body=RequirementCaseLinkCreate(case_id=9, criterion_ids=["AC-1"]),
                db=db,
                user=_user(),
            )
        )

    assert exc.value.status_code == 400
    assert "不属于当前需求项目" in str(exc.value.detail)


def test_link_requirement_rejects_unknown_acceptance_criterion(monkeypatch):
    async def no_access(*_args, **_kwargs):
        return None

    async def fake_get_requirement(*_args, **_kwargs):
        return _requirement()

    monkeypatch.setattr(requirements, "assert_project_access", no_access)
    monkeypatch.setattr(requirements, "_get_requirement", fake_get_requirement)
    db = _DB(case=_case(), module=SimpleNamespace(id=2, project_id=1, name="登录"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            requirements.link_requirement_case(
                requirement_id=41,
                body=RequirementCaseLinkCreate(case_id=9, criterion_ids=["AC-404"]),
                db=db,
                user=_user(),
            )
        )

    assert exc.value.status_code == 400
    assert "AC-404" in str(exc.value.detail)


def test_coverage_only_counts_criteria_declared_on_the_requirement():
    requirement = _requirement(
        criteria=[
            {"id": "AC-1", "text": "成功", "priority": "P2", "status": "draft"},
            {"id": "AC-2", "text": "失败提示", "priority": "P2", "status": "draft"},
        ]
    )
    links = [
        RequirementCaseLink(criterion_ids=["AC-1", "AC-404"]),
        RequirementCaseLink(criterion_ids=["AC-2", "AC-1"]),
    ]

    assert requirements._covered_criterion_ids(requirement, links) == {"AC-1", "AC-2"}
