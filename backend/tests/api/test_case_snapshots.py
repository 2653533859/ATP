import asyncio
import sys
import types
from pathlib import Path

from sqlalchemy import UniqueConstraint

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(get_current_user=lambda: None)
sys.modules["app.worker.tasks"] = types.SimpleNamespace(
    run_test_case=types.SimpleNamespace(delay=lambda *_args, **_kwargs: None)
)

from app.api.v1 import cases
from app.models.case import CaseSnapshot, TestCase
from app.schemas.case import TestCaseUpdate


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
