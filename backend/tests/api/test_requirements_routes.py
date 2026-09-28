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
from app.schemas.requirement import RequirementCaseLinkCreate, RequirementCreate, RequirementUpdate


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


def test_list_requirements_enforces_status_and_reports_link_coverage(monkeypatch):
    async def no_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(requirements, "assert_project_access", no_access)
    requirement = _requirement()
    link = RequirementCaseLink(requirement_id=41, case_id=9, criterion_ids=["AC-1"])
    db = _DB(execute_results=[_Result(count=1), _Result(scalar_rows=[requirement]), _Result(scalar_rows=[link])])

    result = asyncio.run(
        requirements.list_requirements(
            project_id=1, status_filter="draft", keyword="邮箱", page=1, page_size=10, db=db, user=_user()
        )
    )

    assert result.total == 1
    assert result.items[0].coverage_rate == 100
    assert result.items[0].linked_case_count == 1
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            requirements.list_requirements(
                project_id=1, status_filter="unknown", keyword=None, page=1, page_size=10, db=_DB(), user=_user()
            )
        )
    assert exc.value.status_code == 422


def test_requirement_update_changes_version_only_when_content_changes(monkeypatch):
    requirement = _requirement()

    async def fake_get(*_args, **_kwargs):
        return requirement

    async def no_access(*_args, **_kwargs):
        return None

    audit_actions = []

    async def record_audit(_db, **kwargs):
        audit_actions.append(kwargs["action"])

    monkeypatch.setattr(requirements, "_get_requirement", fake_get)
    monkeypatch.setattr(requirements, "assert_project_access", no_access)
    monkeypatch.setattr(requirements, "write_audit_log", record_audit)
    db = _DB(execute_results=[_Result(rows=[]), _Result(rows=[])])

    changed = asyncio.run(
        requirements.update_requirement(
            requirement_id=41,
            body=RequirementUpdate(title="新登录需求", acceptance_criteria=[]),
            db=db,
            user=_user(),
        )
    )
    unchanged = asyncio.run(
        requirements.update_requirement(
            requirement_id=41, body=RequirementUpdate(title="新登录需求"), db=db, user=_user()
        )
    )

    assert changed.title == unchanged.title == "新登录需求"
    assert changed.version == unchanged.version == 2
    assert audit_actions == ["requirement_update"]
    assert db.commits == 2


def test_requirement_detail_and_delete_keep_project_access_and_audit(monkeypatch):
    requirement = _requirement()
    seen_roles = []
    audits = []

    async def fake_get(*_args, **_kwargs):
        return requirement

    async def access(_db, _user, _project_id, role):
        seen_roles.append(role)

    async def audit(_db, **kwargs):
        audits.append(kwargs["action"])

    monkeypatch.setattr(requirements, "_get_requirement", fake_get)
    monkeypatch.setattr(requirements, "assert_project_access", access)
    monkeypatch.setattr(requirements, "write_audit_log", audit)
    db = _DB(execute_results=[_Result(rows=[])])
    db.added.append(requirement)

    detail = asyncio.run(requirements.get_requirement(requirement_id=41, db=db, user=_user()))
    removed = asyncio.run(requirements.delete_requirement(requirement_id=41, db=db, user=_user()))

    assert detail.id == 41 and detail.links == []
    assert removed == {"deleted": True, "id": 41}
    assert seen_roles == [requirements.ProjectRole.viewer, requirements.ProjectRole.editor]
    assert audits == ["requirement_delete"]
    assert requirement not in db.added


def test_requirement_case_link_create_update_and_unlink(monkeypatch):
    requirement = _requirement()
    case = _case()
    module = SimpleNamespace(id=2, project_id=1, name="登录")
    audit_actions = []

    async def fake_get(*_args, **_kwargs):
        return requirement

    async def no_access(*_args, **_kwargs):
        return None

    async def audit(_db, **kwargs):
        audit_actions.append(kwargs["action"])

    monkeypatch.setattr(requirements, "_get_requirement", fake_get)
    monkeypatch.setattr(requirements, "assert_project_access", no_access)
    monkeypatch.setattr(requirements, "write_audit_log", audit)
    db = _DB(case=case, module=module, execute_results=[_Result(one=None)])
    created = asyncio.run(
        requirements.link_requirement_case(
            requirement_id=41,
            body=RequirementCaseLinkCreate(case_id=9, criterion_ids=["AC-1", "AC-1"], note="主流程"),
            db=db,
            user=_user(),
        )
    )
    link = next(item for item in db.added if isinstance(item, RequirementCaseLink))
    db.execute_results.append(_Result(one=link))
    updated = asyncio.run(
        requirements.link_requirement_case(
            requirement_id=41,
            body=RequirementCaseLinkCreate(case_id=9, criterion_ids=["AC-1"], note="新备注"),
            db=db,
            user=_user(),
        )
    )
    removed = asyncio.run(requirements.unlink_requirement_case(requirement_id=41, link_id=51, db=db, user=_user()))

    assert created.criterion_ids == ["AC-1"]
    assert updated.note == "新备注"
    assert removed == {"deleted": True, "id": 51}
    assert audit_actions == [
        "requirement_case_link_create",
        "requirement_case_link_update",
        "requirement_case_link_delete",
    ]


def test_requirement_impact_identifies_uncovered_criteria_and_candidate_cases(monkeypatch):
    requirement = _requirement()
    case = _case()
    module = SimpleNamespace(id=2, project_id=1, name="认证")

    async def fake_get(*_args, **_kwargs):
        return requirement

    async def no_access(*_args, **_kwargs):
        return None

    async def no_links(*_args, **_kwargs):
        return []

    monkeypatch.setattr(requirements, "_get_requirement", fake_get)
    monkeypatch.setattr(requirements, "assert_project_access", no_access)
    monkeypatch.setattr(requirements, "_load_links", no_links)
    db = _DB(execute_results=[_Result(rows=[(case, module)])])

    result = asyncio.run(requirements.get_requirement_impact(requirement_id=41, db=db, user=_user()))

    assert result.impact_level == "high"
    assert result.criteria_covered == 0
    assert [item.id for item in result.uncovered_criteria] == ["AC-1"]
    assert [item.case_id for item in result.candidate_cases] == [case.id]


def test_requirement_impact_reports_low_when_all_criteria_are_linked(monkeypatch):
    requirement = _requirement()
    case = _case()
    module = SimpleNamespace(id=2, project_id=1, name="认证")
    link = RequirementCaseLink(id=51, requirement_id=41, case_id=case.id, criterion_ids=["AC-1"])

    async def fake_get(*_args, **_kwargs):
        return requirement

    async def no_access(*_args, **_kwargs):
        return None

    async def one_link(*_args, **_kwargs):
        return [(link, case, module)]

    monkeypatch.setattr(requirements, "_get_requirement", fake_get)
    monkeypatch.setattr(requirements, "assert_project_access", no_access)
    monkeypatch.setattr(requirements, "_load_links", one_link)
    db = _DB(execute_results=[_Result(rows=[(case, module)])])

    result = asyncio.run(requirements.get_requirement_impact(requirement_id=41, db=db, user=_user()))

    assert result.impact_level == "low"
    assert result.coverage_rate == 100
    assert result.candidate_cases == []
