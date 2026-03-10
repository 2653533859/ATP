import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(get_current_user=lambda: None)
sys.modules["app.worker.tasks"] = types.SimpleNamespace(
    run_test_case=types.SimpleNamespace(delay=lambda *_args, **_kwargs: None)
)

from app.api.v1 import cases
from app.models.bootstrap import load_all_models
from app.models.case import CaseStatus, CaseStep, CaseType, RunStatus, TestCase
from app.schemas.case import RunTriggerRequest, TestCaseUpdate, TestRunOut


def _now():
    return datetime.now(timezone.utc)


def _case() -> TestCase:
    case = TestCase(
        id=5,
        name="old",
        description="desc",
        case_code="ATP-LOGIN-API-0001",
        summary="legacy summary",
        case_type=CaseType.api,
        status=CaseStatus.active,
        priority="P1",
        case_level="core",
        review_status="approved",
        automation_status="auto",
        tags=["smoke"],
        module_id=2,
        creator_id=9,
        owner_id=9,
        preconditions=["service up"],
        postconditions=["token saved"],
        config={"steps": [{"action": "request", "params": {"url": "/login"}}]},
    )
    case.created_at = _now()
    case.updated_at = _now()
    case.steps = [
        CaseStep(
            id=1,
            case_id=5,
            step_no=1,
            action="Send request",
            test_data="POST /login",
            expected_result="200 OK",
            is_key_step=True,
        )
    ]
    for step in case.steps:
        step.created_at = _now()
        step.updated_at = _now()
    return case


class _FakeSnapshot:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _SnapshotDB:
    def __init__(self, case_obj=None, snapshot_obj=None):
        self.case_obj = case_obj
        self.snapshot_obj = snapshot_obj
        self.added = []

    async def get(self, model, _pk):
        model_name = getattr(model, "__name__", "")
        if model_name == "CaseSnapshot":
            return self.snapshot_obj
        if model_name == "TestCase":
            return self.case_obj
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.case_obj.updated_at = _now()


class _RunQueryResult:
    def __init__(self, run_obj):
        self.run_obj = run_obj

    def scalar_one(self):
        return self.run_obj


class _TriggerRunDB(_SnapshotDB):
    def __init__(self, case_obj=None, loaded_run=None):
        super().__init__(case_obj=case_obj)
        self.loaded_run = loaded_run

    async def execute(self, _stmt):
        return _RunQueryResult(self.loaded_run)

    async def refresh(self, _obj):
        return None

    async def commit(self):
        if self.added:
            self.added[0].id = 21


def test_update_case_snapshot_contains_standardized_payload(monkeypatch):
    load_all_models()
    case_obj = _case()
    db = _SnapshotDB(case_obj=case_obj)

    async def fake_detail_loader(_db, case_id):
        assert case_id == 5
        return case_obj

    async def fake_next_snapshot_version(_db, case_id):
        assert case_id == 5
        return 8

    monkeypatch.setattr(cases, "_get_case_detail_or_404", fake_detail_loader)
    monkeypatch.setattr(cases, "_next_snapshot_version", fake_next_snapshot_version)

    result = asyncio.run(
        cases.update_case(
            case_id=5,
            body=TestCaseUpdate(name="new-name"),
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    assert result.name == "new-name"
    assert db.added[0].version == 8
    assert db.added[0].snapshot_data["summary"] == "legacy summary"
    assert db.added[0].snapshot_data["steps"][0]["action"] == "Send request"


def test_rollback_case_restores_standardized_fields_and_steps(monkeypatch):
    case_obj = _case()
    snapshot_obj = types.SimpleNamespace(
        id=11,
        case_id=5,
        name="snap-name",
        description="snap-desc",
        tags=["regression"],
        config={"steps": [{"action": "request", "params": {"url": "/v2/login"}}]},
        snapshot_data={
            "name": "snap-name",
            "description": "snap-desc",
            "summary": "snap summary",
            "case_type": "api",
            "status": "active",
            "priority": "P0",
            "case_level": "smoke",
            "review_status": "approved",
            "automation_status": "auto",
            "owner_id": 9,
            "preconditions": ["seeded user"],
            "postconditions": ["token refreshed"],
            "tags": ["regression"],
            "config": {"steps": [{"action": "request", "params": {"url": "/v2/login"}}]},
            "steps": [
                {
                    "step_no": 1,
                    "action": "Request v2 login",
                    "test_data": "POST /v2/login",
                    "expected_result": "200 OK",
                    "is_key_step": True,
                    "remarks": None,
                }
            ],
        },
    )
    db = _SnapshotDB(case_obj=case_obj, snapshot_obj=snapshot_obj)

    async def fake_detail_loader(_db, case_id):
        assert case_id == 5
        return case_obj

    async def fake_next_snapshot_version(_db, case_id):
        assert case_id == 5
        return 12

    monkeypatch.setattr(cases, "_get_case_detail_or_404", fake_detail_loader)
    monkeypatch.setattr(cases, "_next_snapshot_version", fake_next_snapshot_version)
    result = asyncio.run(
        cases.rollback_case(
            case_id=5,
            snapshot_id=11,
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    assert result.name == "snap-name"
    assert result.summary == "snap summary"
    assert result.priority == "P0"
    assert result.preconditions == ["seeded user"]
    assert result.steps[0].action == "Request v2 login"
    assert db.added[0].version == 12


def test_trigger_run_returns_serialized_schema(monkeypatch):
    load_all_models()
    case_obj = _case()
    loaded_run = types.SimpleNamespace(
        id=21,
        case_id=5,
        triggered_by=9,
        status=RunStatus.pending,
        environment=None,
        duration_ms=None,
        error_message=None,
        result_summary={},
        created_at=_now(),
        steps=[],
    )
    db = _TriggerRunDB(case_obj=case_obj, loaded_run=loaded_run)
    delayed = {}

    monkeypatch.setattr(
        cases,
        "run_test_case",
        types.SimpleNamespace(delay=lambda run_id, extra_vars: delayed.update(run_id=run_id, extra_vars=extra_vars)),
    )

    result = asyncio.run(
        cases.trigger_run(
            case_id=5,
            body=RunTriggerRequest(extra_vars={"base_url": "http://backend:8000"}),
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    assert isinstance(result, TestRunOut)
    assert result.id == 21
    assert result.steps == []
    assert delayed == {"run_id": 21, "extra_vars": {"base_url": "http://backend:8000"}}
