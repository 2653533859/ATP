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

from app.api.v1 import suites as suites_api
from app.api.v1 import plans as plans_api
from app.models.bootstrap import load_all_models
from app.models.plan import PlanStatus, ScheduleType, TestPlan
from app.models.suite import SuiteStatus, TestSuite
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole
from app.schemas.plan import PlanBatchDeleteIn, PlanBatchToggleIn
from app.schemas.suite import SuiteBatchCopyIn, SuiteBatchDeleteIn

load_all_models()


def _now():
    return datetime.now(timezone.utc)


def _make_user() -> User:
    user = User(id=1, username="op", email="op@example.com", hashed_password="x", role=UserRole.admin)
    return user


def _make_suite(suite_id: int) -> TestSuite:
    suite = TestSuite(
        id=suite_id,
        name=f"S{suite_id}",
        description="d",
        project_id=10,
        status=SuiteStatus.active,
        creator_id=1,
        case_ids=[{"case_id": 100, "sort": 0}],
        parameterization={"foo": "bar"},
        config={"execution_mode": "sequential"},
    )
    suite.created_at = _now()
    suite.updated_at = _now()
    return suite


def _make_plan(plan_id: int, *, enabled: bool = True) -> TestPlan:
    plan = TestPlan(
        id=plan_id,
        name=f"P{plan_id}",
        description="d",
        project_id=10,
        status=PlanStatus.active,
        creator_id=1,
        suite_ids=[],
        schedule_type=ScheduleType.manual,
        cron_expression=None,
        webhook_secret=None,
        is_enabled=enabled,
        auto_create_bugs=False,
        env_id=None,
    )
    plan.created_at = _now()
    plan.updated_at = _now()
    return plan


class _ScalarsResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeDB:
    def __init__(self, suites=None, plans=None):
        self.suites = suites or {}
        self.plans = plans or {}
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.commits = 0

    async def execute(self, stmt):
        target = stmt.column_descriptions[0]["entity"] if stmt.column_descriptions else None
        # 抽取 IN 子句的 ids
        ids: list[int] = []
        try:
            params = stmt.compile().params
            for value in params.values():
                if isinstance(value, (list, tuple, set)):
                    ids = list(value)
                    break
        except Exception:
            ids = []
        source = self.suites if target is TestSuite else self.plans
        rows = [source[i] for i in ids if i in source]
        return _ScalarsResult(rows)

    async def delete(self, obj):
        self.deleted.append(obj)

    def add(self, obj):
        # 模拟 id 分配
        if isinstance(obj, TestSuite):
            obj.id = 9000 + len(self.added)
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1


def test_suite_batch_delete_skips_missing(monkeypatch):
    db = _FakeDB(suites={1: _make_suite(1), 2: _make_suite(2)})
    body = SuiteBatchDeleteIn(suite_ids=[1, 2, 999])

    result = asyncio.run(suites_api.batch_delete_suites(body=body, db=db, current_user=_make_user()))

    assert result.requested == 3
    assert result.processed == 2
    assert result.skipped_ids == [999]
    assert {obj.id for obj in db.deleted} == {1, 2}


def test_suite_batch_delete_checks_project_editor_access(monkeypatch):
    calls = []

    async def record_access(_db, _user, project_id, role):
        calls.append((project_id, role))

    monkeypatch.setattr(suites_api, "assert_project_access", record_access)
    db = _FakeDB(suites={1: _make_suite(1)})

    asyncio.run(
        suites_api.batch_delete_suites(
            body=SuiteBatchDeleteIn(suite_ids=[1]),
            db=db,
            current_user=_make_user(),
        )
    )

    assert calls == [(10, ProjectRole.editor)]


def test_suite_batch_copy_creates_clones(monkeypatch):
    db = _FakeDB(suites={1: _make_suite(1)})
    user = _make_user()
    body = SuiteBatchCopyIn(suite_ids=[1, 1, 404], suffix=" copy")

    result = asyncio.run(suites_api.batch_copy_suites(body=body, db=db, current_user=user))

    assert result.requested == 2
    assert result.processed == 1
    assert result.skipped_ids == [404]
    assert len(result.created_ids) == 1
    assert db.added[0].name.endswith(" copy")
    assert db.added[0].creator_id == user.id


def test_plan_batch_delete(monkeypatch):
    db = _FakeDB(plans={1: _make_plan(1), 2: _make_plan(2)})
    body = PlanBatchDeleteIn(plan_ids=[1, 2, 3])

    result = asyncio.run(plans_api.batch_delete_plans(body=body, db=db, current_user=_make_user()))

    assert result.processed == 2
    assert result.skipped_ids == [3]
    assert {obj.id for obj in db.deleted} == {1, 2}


def test_plan_batch_toggle_only_changes_diff(monkeypatch):
    db = _FakeDB(plans={1: _make_plan(1, enabled=True), 2: _make_plan(2, enabled=False)})
    body = PlanBatchToggleIn(plan_ids=[1, 2], is_enabled=True)

    result = asyncio.run(plans_api.batch_toggle_plans(body=body, db=db, current_user=_make_user()))

    assert result.processed == 1  # 只有 plan 2 状态从 False -> True
    assert 1 in result.skipped_ids
    assert db.plans[2].is_enabled is True
