import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)

def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None

sys.modules["app.api.deps"] = types.SimpleNamespace(get_current_user=lambda: None, require_engineer=lambda: None,
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
from app.models.case import CaseStatus, CaseStep, CaseType, TestCase
from app.schemas.case import TestCaseUpdate


def _now():
    return datetime.now(timezone.utc)


def _make_case() -> TestCase:
    case = TestCase(
        id=9,
        name="Login Web",
        description="legacy",
        case_code="ATP-WEB-0001",
        summary="login summary",
        case_type=CaseType.web,
        status=CaseStatus.active,
        priority="P1",
        case_level="core",
        review_status="approved",
        automation_status="auto",
        tags=["smoke"],
        module_id=2,
        creator_id=1,
        owner_id=1,
        config={"steps": [{"action": "goto", "params": {"url": "https://old.example"}}]},
    )
    case.created_at = _now()
    case.updated_at = _now()
    case.steps = [
        CaseStep(
            id=1,
            case_id=9,
            step_no=1,
            action="Open old page",
            test_data='{"url":"https://old.example"}',
            expected_result="page visible",
            is_key_step=True,
        )
    ]
    for step in case.steps:
        step.created_at = _now()
        step.updated_at = _now()
    return case


class _UpdateDB:
    def __init__(self, case_obj: TestCase):
        self.case_obj = case_obj
        self.added = []
        self.persisted_step_nos = [step.step_no for step in case_obj.steps]
        self.flush_calls = 0

    def add(self, obj):
        self.added.append(obj)

    async def get(self, _model, _pk):
        return None

    async def flush(self):
        self.flush_calls += 1
        self.persisted_step_nos = []

    async def commit(self):
        duplicate_step_nos = set(self.persisted_step_nos).intersection(
            step.step_no for step in self.case_obj.steps
        )
        if duplicate_step_nos:
            raise AssertionError("Existing steps must be flushed before replacement")
        self.case_obj.updated_at = _now()


def test_update_case_flushes_old_steps_before_reinserting(monkeypatch):
    load_all_models()
    case_obj = _make_case()
    db = _UpdateDB(case_obj)

    async def fake_detail_loader(_db, case_id):
        assert case_id == 9
        return case_obj

    async def fake_next_snapshot_version(_db, case_id):
        assert case_id == 9
        return 2

    monkeypatch.setattr(cases, "_get_case_detail_or_404", fake_detail_loader)
    monkeypatch.setattr(cases, "_next_snapshot_version", fake_next_snapshot_version)

    result = asyncio.run(
        cases.update_case(
            case_id=9,
            body=TestCaseUpdate(
                config={"steps": [{"action": "goto", "params": {"url": "https://new.example"}}]},
                steps=[{"action": "Open new page", "test_data": '{"url":"https://new.example"}'}],
            ),
            db=db,
            current_user=types.SimpleNamespace(id=1),
        )
    )

    assert db.flush_calls == 1
    assert [step.step_no for step in result.steps] == [1]
    assert result.steps[0].action == "Open new page"
    assert result.review_status == "pending"
    assert result.status == CaseStatus.draft
