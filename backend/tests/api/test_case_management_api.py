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
from app.models.case import CaseStatus, CaseStep, CaseType, TestCase
from app.schemas.case import TestCaseCreate, TestCaseUpdate


def _now():
    return datetime.now(timezone.utc)


def _make_case() -> TestCase:
    case = TestCase(
        id=7,
        name="Login API",
        description="legacy",
        case_code="ATP-LOGIN-API-0001",
        summary="login summary",
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
        postconditions=["session created"],
        config={"steps": [{"action": "request", "params": {"url": "/login"}}]},
    )
    case.created_at = _now()
    case.updated_at = _now()
    case.steps = [
        CaseStep(
            id=1,
            case_id=7,
            step_no=1,
            action="Open login API",
            test_data="POST /login",
            expected_result="200 OK",
            is_key_step=True,
        )
    ]
    for step in case.steps:
        step.created_at = _now()
        step.updated_at = _now()
    return case


class _CreateDB:
    def __init__(self):
        self.case = None
        self.added = []
        self.commit_calls = 0

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, TestCase):
            self.case = obj

    async def commit(self):
        self.commit_calls += 1
        if self.case and self.case.id is None:
            self.case.id = 101
            self.case.created_at = _now()
            self.case.updated_at = _now()
            for index, step in enumerate(self.case.steps, start=1):
                step.id = index
                step.case_id = self.case.id
                step.created_at = _now()
                step.updated_at = _now()

    async def refresh(self, _obj):
        return None


class _StatementDB:
    def __init__(self):
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return types.SimpleNamespace(scalars=lambda: types.SimpleNamespace(all=lambda: []))


class _DetailQueryResult:
    def __init__(self, case_obj: TestCase):
        self.case_obj = case_obj

    def scalar_one_or_none(self):
        return self.case_obj


class _DetailDB:
    def __init__(self, case_obj: TestCase | None):
        self.case_obj = case_obj

    async def execute(self, _stmt):
        return _DetailQueryResult(self.case_obj)


class _DeleteDB:
    def __init__(self, case_obj: TestCase | None):
        self.case_obj = case_obj
        self.deleted = []
        self.commit_calls = 0

    async def get(self, model, case_id):
        if model is not TestCase:
            return None
        assert case_id == 7
        return self.case_obj

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commit_calls += 1


class _UpdateDB:
    def __init__(self, case_obj: TestCase):
        self.case_obj = case_obj
        self.added = []
        self.commit_calls = 0

    def add(self, obj):
        self.added.append(obj)

    async def get(self, _model, _pk):
        return None

    async def flush(self):
        return None

    async def commit(self):
        self.commit_calls += 1
        self.case_obj.updated_at = _now()


def test_create_case_persists_standardized_fields_and_ordered_steps(monkeypatch):
    load_all_models()
    db = _CreateDB()
    current_user = types.SimpleNamespace(id=9, username="tester")
    module = types.SimpleNamespace(
        id=2,
        name="Login",
        module_code="LOGIN",
        project=types.SimpleNamespace(id=1, name="ATP", project_code="ATP"),
        project_id=1,
    )

    async def fake_module_loader(_db, module_id):
        assert module_id == 2
        return module

    async def fake_case_code(_db, _module, case_type):
        assert case_type == CaseType.api
        return "ATP-LOGIN-API-0008"

    async def fake_detail_loader(_db, case_id):
        assert case_id == 101
        return db.case

    monkeypatch.setattr(cases, "_get_module_for_case_code", fake_module_loader)
    monkeypatch.setattr(cases, "_generate_case_code", fake_case_code)
    monkeypatch.setattr(cases, "_get_case_detail_or_404", fake_detail_loader)
    monkeypatch.setattr(cases, "write_audit_log", lambda *_args, **_kwargs: asyncio.sleep(0))

    result = asyncio.run(
        cases.create_case(
            body=TestCaseCreate(
                name="Login API",
                description="Verify login",
                summary="User logs in successfully",
                case_type=CaseType.api,
                module_id=2,
                priority="P0",
                case_level="smoke",
                preconditions=["User exists"],
                postconditions=["Session issued"],
                tags=["smoke"],
                config={"steps": [{"action": "request", "params": {"url": "/login"}}]},
                steps=[
                    {"step_no": 2, "action": "Assert token", "expected_result": "token exists"},
                    {"step_no": 1, "action": "Send request", "test_data": "POST /login"},
                ],
            ),
            db=db,
            current_user=current_user,
        )
    )

    assert result.case_code == "ATP-LOGIN-API-0008"
    assert result.status == CaseStatus.draft
    assert result.review_status == "pending"
    assert result.summary == "User logs in successfully"
    assert [step.step_no for step in result.steps] == [1, 2]
    assert result.steps[0].action == "Send request"


def test_create_case_invalidates_stats_cache(monkeypatch):
    load_all_models()
    db = _CreateDB()
    current_user = types.SimpleNamespace(id=9, username="tester")
    module = types.SimpleNamespace(
        id=2,
        name="Login",
        module_code="LOGIN",
        project=types.SimpleNamespace(id=1, name="ATP", project_code="ATP"),
        project_id=1,
    )
    invalidated = []

    async def fake_module_loader(_db, module_id):
        assert module_id == 2
        return module

    async def fake_case_code(_db, _module, case_type):
        assert case_type == CaseType.api
        return "ATP-LOGIN-API-0009"

    async def fake_detail_loader(_db, case_id):
        assert case_id == 101
        return db.case

    async def fake_invalidate_stats_cache():
        invalidated.append(True)

    monkeypatch.setattr(cases, "_get_module_for_case_code", fake_module_loader)
    monkeypatch.setattr(cases, "_generate_case_code", fake_case_code)
    monkeypatch.setattr(cases, "_get_case_detail_or_404", fake_detail_loader)
    monkeypatch.setattr(cases, "invalidate_stats_cache", fake_invalidate_stats_cache)
    monkeypatch.setattr(cases, "write_audit_log", lambda *_args, **_kwargs: asyncio.sleep(0))

    asyncio.run(
        cases.create_case(
            body=TestCaseCreate(
                name="Login API",
                description="Verify login",
                summary="User logs in successfully",
                case_type=CaseType.api,
                module_id=2,
                priority="P0",
                case_level="smoke",
                preconditions=["User exists"],
                postconditions=["Session issued"],
                tags=["smoke"],
                config={"steps": [{"action": "request", "params": {"url": "/login"}}]},
                steps=[{"step_no": 1, "action": "Send request", "test_data": "POST /login"}],
            ),
            db=db,
            current_user=current_user,
        )
    )

    assert invalidated == [True]
    assert db.commit_calls == 2


def test_list_cases_supports_management_filters():
    load_all_models()
    db = _StatementDB()

    result = asyncio.run(
        cases.list_cases(
            project_id=8,
            module_id=3,
            case_type="api",
            priority="P1",
            status="active",
            review_status="approved",
            owner_id=9,
            automation_status="auto",
            tag="smoke",
            keyword="login",
            db=db,
            user=None,
        )
    )

    assert result == []
    sql = str(db.statements[0])
    assert "JOIN modules" in sql
    assert "modules.project_id" in sql
    assert "test_cases.priority" in sql
    assert "test_cases.review_status" in sql
    assert "test_cases.automation_status" in sql


def test_update_case_resets_review_cycle_and_replaces_steps(monkeypatch):
    load_all_models()
    case_obj = _make_case()
    db = _UpdateDB(case_obj)

    async def fake_detail_loader(_db, case_id):
        assert case_id == 7
        return case_obj

    async def fake_next_snapshot_version(_db, case_id):
        assert case_id == 7
        return 4

    monkeypatch.setattr(cases, "_get_case_detail_or_404", fake_detail_loader)
    monkeypatch.setattr(cases, "_next_snapshot_version", fake_next_snapshot_version)

    result = asyncio.run(
        cases.update_case(
            case_id=7,
            body=TestCaseUpdate(
                summary="updated summary",
                priority="P0",
                config={"steps": [{"action": "request", "params": {"url": "/v2/login"}}]},
                steps=[{"action": "Send new request", "expected_result": "200 OK"}],
            ),
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    snapshot = db.added[0]
    assert snapshot.version == 4
    assert snapshot.snapshot_data["steps"][0]["action"] == "Open login API"
    assert result.review_status == "pending"
    assert result.status == CaseStatus.draft
    assert [step.step_no for step in result.steps] == [1]
    assert result.steps[0].action == "Send new request"


def test_delete_case_invalidates_stats_cache(monkeypatch):
    load_all_models()
    case_obj = _make_case()
    db = _DeleteDB(case_obj)
    invalidated = []
    audit_calls = []

    async def fake_invalidate_stats_cache():
        invalidated.append(True)

    async def fake_write_audit_log(*args, **kwargs):
        audit_calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(cases, "invalidate_stats_cache", fake_invalidate_stats_cache)
    monkeypatch.setattr(cases, "write_audit_log", fake_write_audit_log)

    asyncio.run(
        cases.delete_case(
            case_id=7,
            db=db,
            current_user=types.SimpleNamespace(id=9, username="tester"),
        )
    )

    assert db.deleted == [case_obj]
    assert db.commit_calls == 1
    assert len(audit_calls) == 1
    assert invalidated == [True]


def test_get_case_detail_normalizes_legacy_json_lists():
    load_all_models()
    case_obj = _make_case()
    case_obj.preconditions = {}
    case_obj.postconditions = {}
    case_obj.tags = {"legacy": True}
    db = _DetailDB(case_obj)

    result = asyncio.run(cases._get_case_detail_or_404(db, 7))

    assert result.preconditions == []
    assert result.postconditions == []
    assert result.tags == []
    payload = cases.TestCaseDetailOut.model_validate(result)
    assert payload.preconditions == []
    assert payload.postconditions == []
