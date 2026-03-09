import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import UniqueConstraint

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(get_current_user=lambda: None)
sys.modules["app.worker.tasks"] = types.SimpleNamespace(
    run_test_case=types.SimpleNamespace(delay=lambda *_args, **_kwargs: None)
)

from app.api.v1 import cases
from app.models.bootstrap import load_all_models
from app.models.case import CaseSnapshot, TestCase
from app.schemas.case import RunTriggerRequest, TestCaseUpdate, TestRunOut


class _FakeResult:
    def __init__(self, scalar_value=None):
        self.scalar_value = scalar_value


class _FakeCase:
    def __init__(self):
        self.id = 5
        self.name = 'old'
        self.description = 'desc'
        self.tags = ['smoke']
        self.config = {'key': 'value'}


class _FakeSnapshot:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeDB:
    def __init__(self, case_obj=None, snapshot_obj=None):
        self.case_obj = case_obj
        self.snapshot_obj = snapshot_obj
        self.added = []
        self.executed = []

    async def get(self, model, _pk):
        model_name = getattr(model, '__name__', '')
        if model_name == 'TestCase':
            return self.case_obj
        if model_name in {'CaseSnapshot', '_FakeSnapshot'}:
            return self.snapshot_obj
        return None

    async def execute(self, stmt):
        self.executed.append(stmt)
        return _FakeResult()

    async def scalar(self, stmt):
        self.executed.append(stmt)
        return 4

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        return None

    async def refresh(self, _obj):
        return None


class _FakeRunQueryResult:
    def __init__(self, run_obj):
        self.run_obj = run_obj

    def scalar_one(self):
        return self.run_obj


class _TriggerRunDB(_FakeDB):
    def __init__(self, case_obj=None, env_obj=None, loaded_run=None):
        super().__init__(case_obj=case_obj)
        self.env_obj = env_obj
        self.loaded_run = loaded_run

    async def get(self, model, _pk):
        model_name = getattr(model, "__name__", "")
        if model_name == "TestCase":
            return self.case_obj
        if model_name == "Environment":
            return self.env_obj
        return None

    async def execute(self, stmt):
        self.executed.append(stmt)
        return _FakeRunQueryResult(self.loaded_run)

    async def refresh(self, obj):
        obj.id = 21
        obj.result_summary = {}
        obj.created_at = datetime.now(timezone.utc)
        obj.steps = []
        return None



def test_case_snapshot_has_unique_constraint_for_case_version():
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {'case_id', 'version'}
        for constraint in CaseSnapshot.__table__.constraints
    )



def test_next_snapshot_version_locks_case_row_before_allocating():
    db = _FakeDB()

    version = asyncio.run(cases._next_snapshot_version(db, case_id=5))

    assert version == 5
    assert db.executed[0]._for_update_arg is not None



def test_update_case_uses_reserved_snapshot_version(monkeypatch):
    case_obj = _FakeCase()
    db = _FakeDB(case_obj=case_obj)

    async def fake_next_snapshot_version(_db, case_id):
        assert case_id == 5
        return 8

    monkeypatch.setattr(cases, '_next_snapshot_version', fake_next_snapshot_version)
    monkeypatch.setattr(cases, 'CaseSnapshot', _FakeSnapshot)

    result = asyncio.run(
        cases.update_case(
            case_id=5,
            body=TestCaseUpdate(name='new-name'),
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    assert result.name == 'new-name'
    assert db.added[0].version == 8



def test_rollback_case_uses_reserved_snapshot_version(monkeypatch):
    case_obj = _FakeCase()
    snapshot_obj = types.SimpleNamespace(
        id=11,
        case_id=5,
        name='snap-name',
        description='snap-desc',
        tags=['regression'],
        config={'k': 'v'},
    )
    db = _FakeDB(case_obj=case_obj, snapshot_obj=snapshot_obj)

    async def fake_next_snapshot_version(_db, case_id):
        assert case_id == 5
        return 12

    monkeypatch.setattr(cases, '_next_snapshot_version', fake_next_snapshot_version)
    monkeypatch.setattr(cases, 'CaseSnapshot', _FakeSnapshot)

    result = asyncio.run(
        cases.rollback_case(
            case_id=5,
            snapshot_id=11,
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    assert result.name == 'snap-name'
    assert db.added[0].version == 12


def test_trigger_run_returns_serialized_schema(monkeypatch):
    load_all_models()
    case_obj = types.SimpleNamespace(id=5)
    loaded_run = types.SimpleNamespace(
        id=21,
        case_id=5,
        triggered_by=9,
        status=cases.RunStatus.pending,
        environment=None,
        duration_ms=None,
        error_message=None,
        result_summary={},
        created_at=datetime.now(timezone.utc),
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
