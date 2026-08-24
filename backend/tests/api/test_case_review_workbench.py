"""Behavioral contracts for the project-aware case review workbench."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.v1 import case_reviews
from app.models.bootstrap import load_all_models
from app.models.case import CaseStatus, CaseType, TestCase
from app.schemas.case_review import CaseReviewBatchIn
from app.services.case_review import build_review_audit_detail

load_all_models()

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, *, rows=None, one=None, scalar_rows=None):
        self.rows = rows or []
        self.one_value = one
        self.scalar_rows = scalar_rows or []

    def all(self):
        return self.rows

    def one_or_none(self):
        return self.one_value

    def scalars(self):
        return SimpleNamespace(all=lambda: self.scalar_rows)


class _DB:
    def __init__(self, results):
        self.results = results
        self.calls = 0
        self.commits = 0

    async def execute(self, _statement):
        result = self.results[self.calls]
        self.calls += 1
        return result

    async def commit(self):
        self.commits += 1


def _user():
    return SimpleNamespace(id=7, username="reviewer", role="admin")


def _case(case_id: int, status: str = "pending") -> TestCase:
    case = TestCase(
        id=case_id,
        name=f"Case {case_id}",
        description=None,
        case_code=f"ATP-API-{case_id:04d}",
        summary="review summary",
        case_type=CaseType.api,
        status=CaseStatus.draft,
        priority="P1",
        case_level="core",
        review_status=status,
        automation_status="auto",
        tags=[],
        module_id=2,
        creator_id=3,
        owner_id=3,
        preconditions=[],
        postconditions=[],
        config={},
    )
    case.created_at = NOW
    case.updated_at = NOW
    return case


def test_review_queue_returns_counts_and_context(monkeypatch):
    async def no_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(case_reviews, "assert_project_access", no_access)
    monkeypatch.setattr(case_reviews, "scope_to_visible_projects", lambda statement, *_args: statement)
    case = _case(11)
    db = _DB(
        [
            _Result(rows=[("pending", 2), ("approved", 1)]),
            _Result(rows=[(case, 4, "ATP", 2, "Auth", None, 3, 2, 2)]),
        ]
    )

    result = asyncio.run(
        case_reviews.list_case_reviews(
            project_id=4,
            module_id=None,
            review_status="pending",
            keyword=None,
            page=1,
            page_size=50,
            db=db,
            user=_user(),
        )
    )

    assert result.total == 2
    assert result.counts.all == 3
    assert result.counts.pending == 2
    assert result.items[0].module_name == "Auth"
    assert result.items[0].step_count == 3
    assert result.items[0].latest_snapshot_version == 2


def test_batch_review_only_processes_pending_cases(monkeypatch):
    async def no_access(*_args, **_kwargs):
        return None

    async def no_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(case_reviews, "assert_project_access", no_access)
    monkeypatch.setattr(case_reviews, "write_audit_log", no_audit)
    pending = _case(1)
    already_approved = _case(2, status="approved")
    db = _DB([_Result(rows=[(pending, 4), (already_approved, 4)])])

    result = asyncio.run(
        case_reviews.batch_review_cases(
            body=CaseReviewBatchIn(case_ids=[1, 1, 2, 99], action="approve", comment="looks good"),
            db=db,
            current_user=_user(),
        )
    )

    assert result.requested == 3
    assert result.processed == 1
    assert result.processed_ids == [1]
    assert result.skipped_ids == [2, 99]
    assert pending.review_status == "approved"
    assert pending.status == CaseStatus.active
    assert pending.reviewed_by == 7
    assert pending.review_comment == "looks good"
    assert db.commits == 1


def test_review_history_decodes_audit_comment(monkeypatch):
    async def no_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(case_reviews, "assert_project_access", no_access)
    log = SimpleNamespace(
        id=90,
        action="case_review_reject",
        resource_id=11,
        user_id=7,
        username="reviewer",
        detail=build_review_audit_detail(action="reject", status="rejected", comment="补充断言"),
        created_at=NOW,
    )
    db = _DB([_Result(one=(_case(11), 4)), _Result(scalar_rows=[log])])

    result = asyncio.run(case_reviews.list_case_review_history(case_id=11, db=db, user=_user()))

    assert result[0].action == "reject"
    assert result[0].status == "rejected"
    assert result[0].comment == "补充断言"
    assert result[0].reviewer_name == "reviewer"
