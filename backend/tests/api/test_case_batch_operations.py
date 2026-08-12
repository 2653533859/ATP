import asyncio
import io
import json
import sys
import types
import zipfile
from datetime import datetime, timezone
from pathlib import Path

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


async def _noop_invalidate_stats_cache():
    return None


sys.modules["app.api.v1.statistics"] = types.SimpleNamespace(invalidate_stats_cache=_noop_invalidate_stats_cache)

from app.api.v1 import cases
from app.models.bootstrap import load_all_models
from app.models.case import CaseStatus, CaseType, TestCase
from app.models.project import Module
from app.models.user import User, UserRole
from app.schemas.case import CaseBatchDeleteIn, CaseBatchMoveIn

load_all_models()


def _make_user() -> User:
    user = User(id=1, username="alice", email="alice@example.com", hashed_password="x", role=UserRole.admin)
    return user


def _make_case(case_id: int, module_id: int = 2) -> TestCase:
    case = TestCase(
        id=case_id,
        name=f"Case {case_id}",
        case_code=f"ATP-API-{case_id:04d}",
        summary="summary",
        case_type=CaseType.api,
        status=CaseStatus.active,
        priority="P2",
        case_level="regression",
        review_status="approved",
        automation_status="auto",
        tags=[],
        module_id=module_id,
        creator_id=1,
    )
    case.created_at = datetime.now(timezone.utc)
    case.updated_at = datetime.now(timezone.utc)
    return case


class _ScalarsResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeDB:
    def __init__(self, items: dict[int, object], modules: dict[int, Module] | None = None):
        self._items = items
        self._modules = dict(modules or {})
        if modules is not None or items:
            for item in items.values():
                module_id = getattr(item, "module_id", None)
                if module_id and module_id not in self._modules:
                    self._modules[module_id] = Module(
                        id=module_id,
                        name=f"module-{module_id}",
                        project_id=1,
                        parent_id=None,
                        sort_order=0,
                    )
        self.deleted: list[object] = []
        self.commits = 0

    async def execute(self, stmt):
        column = stmt.column_descriptions[0]["entity"] if stmt.column_descriptions else None
        if column is TestCase:
            requested_ids: list[int] = []
            try:
                for clause in stmt.whereclause.clauses:
                    if hasattr(clause, "right") and hasattr(clause.right, "value"):
                        value = clause.right.value
                        if isinstance(value, (list, tuple, set)):
                            requested_ids = list(value)
                            break
            except Exception:
                pass
            if not requested_ids:
                # fallback: compile params
                try:
                    params = stmt.compile().params
                    for value in params.values():
                        if isinstance(value, (list, tuple, set)):
                            requested_ids = list(value)
                            break
                except Exception:
                    requested_ids = []
            rows = [self._items[i] for i in requested_ids if i in self._items]
            return _ScalarsResult(rows)
        return _ScalarsResult([])

    async def get(self, model, pk):
        if model is Module:
            return self._modules.get(pk)
        return self._items.get(pk)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1


def test_batch_delete_returns_counts_and_skips_missing(monkeypatch):
    cases_map = {1: _make_case(1), 2: _make_case(2), 3: _make_case(3)}
    db = _FakeDB(cases_map)
    user = _make_user()

    async def fake_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(cases, "write_audit_log", fake_audit)

    body = CaseBatchDeleteIn(case_ids=[1, 2, 99])
    result = asyncio.run(cases.batch_delete_cases(body=body, db=db, current_user=user))

    assert result.requested == 3
    assert result.processed == 2
    assert result.skipped_ids == [99]
    assert {obj.id for obj in db.deleted} == {1, 2}
    assert db.commits == 1


def test_batch_delete_dedupes_ids(monkeypatch):
    cases_map = {1: _make_case(1)}
    db = _FakeDB(cases_map)
    user = _make_user()

    async def fake_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(cases, "write_audit_log", fake_audit)

    body = CaseBatchDeleteIn(case_ids=[1, 1, 1])
    result = asyncio.run(cases.batch_delete_cases(body=body, db=db, current_user=user))

    assert result.requested == 1
    assert result.processed == 1


def test_batch_move_404_when_target_module_missing(monkeypatch):
    db = _FakeDB(items={1: _make_case(1)}, modules={})
    user = _make_user()
    body = CaseBatchMoveIn(case_ids=[1], target_module_id=999)

    try:
        asyncio.run(cases.batch_move_cases(body=body, db=db, current_user=user))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("应抛 404")


def test_batch_move_skips_cases_already_in_target_module(monkeypatch):
    target = Module(id=5, name="target", module_code="MOD-005", project_id=1, parent_id=None, sort_order=0)
    cases_map = {1: _make_case(1, module_id=2), 2: _make_case(2, module_id=5)}
    db = _FakeDB(cases_map, modules={5: target})
    user = _make_user()

    async def fake_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(cases, "write_audit_log", fake_audit)

    body = CaseBatchMoveIn(case_ids=[1, 2], target_module_id=5)
    result = asyncio.run(cases.batch_move_cases(body=body, db=db, current_user=user))

    assert result.processed == 1
    assert 2 in result.skipped_ids
    assert cases_map[1].module_id == 5
    assert cases_map[2].module_id == 5
    assert db.commits == 1


def test_batch_import_zip_creates_cases(monkeypatch):
    target_module = Module(
        id=7,
        name="target",
        module_code="MOD-007",
        project_id=1,
        parent_id=None,
        sort_order=0,
    )

    class _ImportDB:
        def __init__(self):
            self.added: list[object] = []
            self.commits = 0
            self.flushes = 0
            self._seq = 1000

        async def get(self, model, pk):
            if model is Module and pk == 7:
                return target_module
            return None

        def add(self, obj):
            if isinstance(obj, cases.TestCase):
                self._seq += 1
                obj.id = self._seq
            self.added.append(obj)

        async def flush(self):
            self.flushes += 1

        async def commit(self):
            self.commits += 1

    db = _ImportDB()
    user = _make_user()

    async def fake_module_for_case_code(_db, _mid):
        return target_module

    async def fake_generate_case_code(_db, _module, _ctype):
        return "ATP-AUTO-0001"

    async def fake_invalidate():
        return None

    monkeypatch.setattr(cases, "_get_module_for_case_code", fake_module_for_case_code)
    monkeypatch.setattr(cases, "_generate_case_code", fake_generate_case_code)
    monkeypatch.setattr(cases, "invalidate_stats_cache", fake_invalidate)

    payload = json.dumps(
        [
            {
                "name": "case-a",
                "case_type": "api",
                "tags": ["smoke"],
                "config": {"url": "/x"},
                "steps": [{"action": "request /x", "step_no": 1}],
            },
            {
                "name": "",  # 触发 skip
                "case_type": "api",
            },
            {
                "name": "case-b",
                "case_type": "not_a_type",  # 触发 skip
            },
        ]
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("cases.json", payload)
    buffer.seek(0)

    class _Upload:
        async def read(self):
            return buffer.getvalue()

    result = asyncio.run(
        cases.batch_import_cases_zip(
            target_module_id=7,
            file=_Upload(),
            db=db,
            current_user=user,
        )
    )

    assert result.imported == 1
    assert result.skipped_count == 2
    assert result.target_module_id == 7
    assert len(result.created_ids) == 1
    assert len(result.errors) == 2
    assert any(isinstance(obj, cases.TestCase) for obj in db.added)


def test_batch_import_zip_rejects_bad_archive(monkeypatch):
    class _ImportDB:
        async def get(self, model, pk):
            return Module(id=pk, name="ok", module_code="MOD-001", project_id=1, parent_id=None, sort_order=0)

    class _Upload:
        async def read(self):
            return b"not a zip"

    try:
        asyncio.run(
            cases.batch_import_cases_zip(
                target_module_id=1,
                file=_Upload(),
                db=_ImportDB(),
                current_user=_make_user(),
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("应抛 400")
