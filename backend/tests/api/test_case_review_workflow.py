import asyncio
import sys
import types
from datetime import datetime, timezone
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
sys.modules["app.worker.tasks"] = types.SimpleNamespace(
    run_test_case=types.SimpleNamespace(delay=lambda *_args, **_kwargs: None)
)

from app.api.v1 import cases
from app.models.bootstrap import load_all_models
from app.models.case import CaseStatus, CaseType, TestCase
from app.schemas.case import CaseWorkflowRequest


def _case(status: CaseStatus, review_status: str) -> TestCase:
    case = TestCase(
        id=5,
        name="Workflow Case",
        description=None,
        case_code="ATP-WORKFLOW-API-0001",
        summary="workflow",
        case_type=CaseType.api,
        status=status,
        priority="P1",
        case_level="core",
        review_status=review_status,
        automation_status="auto",
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


class _WorkflowDB:
    def __init__(self, case_obj: TestCase):
        self.case_obj = case_obj

    async def get(self, model, pk):
        if getattr(model, "__name__", "") == "Module":
            return types.SimpleNamespace(id=pk, project_id=1)
        return None

    async def commit(self):
        self.case_obj.updated_at = datetime.now(timezone.utc)


def test_submit_review_marks_case_pending(monkeypatch):
    load_all_models()
    case_obj = _case(CaseStatus.draft, "rejected")
    db = _WorkflowDB(case_obj)

    monkeypatch.setattr(cases, "_get_case_detail_or_404", lambda *_args, **_kwargs: asyncio.sleep(0, result=case_obj))

    result = asyncio.run(
        cases.submit_review(
            case_id=5,
            body=CaseWorkflowRequest(comment="ready"),
            db=db,
            _current_user=types.SimpleNamespace(id=9),
        )
    )

    assert result.review_status == "pending"
    assert result.submitted_at is not None
    assert result.review_comment == "ready"


def test_approve_case_activates_pending_case(monkeypatch):
    load_all_models()
    case_obj = _case(CaseStatus.draft, "pending")
    db = _WorkflowDB(case_obj)
    monkeypatch.setattr(cases, "_get_case_detail_or_404", lambda *_args, **_kwargs: asyncio.sleep(0, result=case_obj))

    result = asyncio.run(
        cases.approve_case(
            case_id=5,
            body=CaseWorkflowRequest(comment="approved"),
            db=db,
            current_user=types.SimpleNamespace(id=7),
        )
    )

    assert result.status == CaseStatus.active
    assert result.review_status == "approved"
    assert result.reviewed_by == 7


def test_reject_case_returns_to_draft(monkeypatch):
    load_all_models()
    case_obj = _case(CaseStatus.draft, "pending")
    db = _WorkflowDB(case_obj)
    monkeypatch.setattr(cases, "_get_case_detail_or_404", lambda *_args, **_kwargs: asyncio.sleep(0, result=case_obj))

    result = asyncio.run(
        cases.reject_case(
            case_id=5,
            body=CaseWorkflowRequest(comment="missing data"),
            db=db,
            current_user=types.SimpleNamespace(id=7),
        )
    )

    assert result.status == CaseStatus.draft
    assert result.review_status == "rejected"
    assert result.review_comment == "missing data"


def test_deprecate_and_reactivate_flow(monkeypatch):
    load_all_models()
    case_obj = _case(CaseStatus.active, "approved")
    db = _WorkflowDB(case_obj)
    monkeypatch.setattr(cases, "_get_case_detail_or_404", lambda *_args, **_kwargs: asyncio.sleep(0, result=case_obj))

    deprecated = asyncio.run(
        cases.deprecate_case(
            case_id=5,
            body=CaseWorkflowRequest(comment="old path"),
            db=db,
            _current_user=types.SimpleNamespace(id=7),
        )
    )
    assert deprecated.status == CaseStatus.deprecated

    reactivated = asyncio.run(
        cases.reactivate_case(
            case_id=5,
            body=CaseWorkflowRequest(comment="restored"),
            db=db,
            _current_user=types.SimpleNamespace(id=7),
        )
    )
    assert reactivated.status == CaseStatus.active


def test_invalid_transition_raises_conflict(monkeypatch):
    load_all_models()
    case_obj = _case(CaseStatus.draft, "rejected")
    db = _WorkflowDB(case_obj)
    monkeypatch.setattr(cases, "_get_case_detail_or_404", lambda *_args, **_kwargs: asyncio.sleep(0, result=case_obj))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            cases.approve_case(
                case_id=5,
                body=CaseWorkflowRequest(comment=None),
                db=db,
                current_user=types.SimpleNamespace(id=7),
            )
        )

    assert exc_info.value.status_code == 409


def test_editing_rejected_case_cannot_silently_auto_approve(monkeypatch):
    from app.api.v1.cases import crud as cases_crud
    from app.schemas.case import TestCaseUpdate

    load_all_models()
    audit_calls = []

    async def fake_write_audit(_db, **kwargs):
        audit_calls.append(kwargs)

    async def fake_next_ver(_db, _case_id):
        return 2

    rejected = _case(CaseStatus.draft, "rejected")
    pending = _case(CaseStatus.draft, "pending")
    pending.id = 6

    class _CrudDB:
        def __init__(self, obj):
            self.obj = obj
            self.added = []

        async def get(self, model, pk):
            if getattr(model, "__name__", "") == "Module":
                return types.SimpleNamespace(id=pk, project_id=1)
            return None

        def add(self, value):
            self.added.append(value)

        async def commit(self):
            self.obj.updated_at = datetime.now(timezone.utc)

    monkeypatch.setattr(cases, "write_audit_log", fake_write_audit)
    monkeypatch.setattr(cases, "_next_snapshot_version", fake_next_ver)

    monkeypatch.setattr(cases, "_get_case_detail_or_404", lambda *_a, **_kw: asyncio.sleep(0, result=rejected))
    asyncio.run(
        cases_crud.update_case(
            case_id=5,
            body=TestCaseUpdate(description="edited after rejection", auto_approve=True),
            db=_CrudDB(rejected),
            current_user=types.SimpleNamespace(id=7, username="admin"),
        )
    )
    assert rejected.review_status == "rejected"
    assert rejected.status == CaseStatus.draft
    assert audit_calls == []

    monkeypatch.setattr(cases, "_get_case_detail_or_404", lambda *_a, **_kw: asyncio.sleep(0, result=pending))
    asyncio.run(
        cases_crud.update_case(
            case_id=6,
            body=TestCaseUpdate(description="admin direct approve", auto_approve=True),
            db=_CrudDB(pending),
            current_user=types.SimpleNamespace(id=7, username="admin"),
        )
    )
    assert pending.review_status == "approved"
    assert pending.status == CaseStatus.active
    assert len(audit_calls) == 1
    assert audit_calls[0]["action"] == "case_review_approve"
