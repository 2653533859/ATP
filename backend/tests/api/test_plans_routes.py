"""plans API 路由单元测试（Q13 补覆盖：此前 55%）。

聚焦套件/环境校验、cron/webhook 调度处理、以及 webhook 触发的 secret 认证阶梯。
FakeDB 承载对象与脚本化查询；assert_project_access / env 解密 / Celery delay 按测试注入。
"""

import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


async def _noop_async(*_a, **_kw):
    return None


_deps = sys.modules.setdefault("app.api.deps", types.SimpleNamespace())
for _name, _value in (
    ("get_current_user", lambda: None),
    ("require_engineer", lambda: None),
    ("assert_project_access", _noop_async),
):
    if not hasattr(_deps, _name):
        setattr(_deps, _name, _value)

from fastapi import HTTPException  # noqa: E402

from app.api.v1 import plans as pl  # noqa: E402
from app.models.bootstrap import load_all_models  # noqa: E402

load_all_models()

from app.models.plan import PlanRunStatus, ScheduleType, TriggerType  # noqa: E402
from app.schemas.plan import (  # noqa: E402
    PlanRunTrigger,
    PlanSuiteItem,
    TestPlanCreate,
    TestPlanUpdate,
    WebhookTriggerRequest,
)


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, objects=None, execute_results=None):
        self.objects = dict(objects or {})
        self.execute_results = list(execute_results or [])
        self.added = []
        self.deleted = []
        self.commits = 0

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = 700
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def execute(self, _query):
        return self.execute_results.pop(0) if self.execute_results else _FakeResult()

    async def refresh(self, obj):
        if getattr(obj, "created_at", None) is None:
            obj.created_at = _now()


def _now():
    return datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setattr(pl, "assert_project_access", _noop_async)
    monkeypatch.setattr(pl, "get_trace_id", lambda: None)
    monkeypatch.setattr(pl, "decrypt_env_vars", lambda rows: {"BASE": "x"})
    # Celery run_test_plan.delay 边界
    delayed = []
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks",
        types.SimpleNamespace(run_test_plan=types.SimpleNamespace(delay=lambda *a: delayed.append(a))),
    )
    return {"delayed": delayed}


def _user(uid=9):
    return _Obj(id=uid, username="amy")


def _suite(sid, project_id=5):
    return _Obj(id=sid, project_id=project_id)


# ── 校验 helper ─────────────────────────────────────────────


def test_validate_suite_ids_rejects_duplicates():
    db = _FakeDB()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pl._validate_plan_suite_ids(db, 5, [PlanSuiteItem(suite_id=1), PlanSuiteItem(suite_id=1)]))
    assert exc.value.status_code == 400 and "重复" in exc.value.detail


def test_validate_suite_ids_rejects_missing_and_wrong_project():
    # 缺失套件
    db = _FakeDB(execute_results=[_FakeResult(rows=[])])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pl._validate_plan_suite_ids(db, 5, [PlanSuiteItem(suite_id=1)]))
    assert "不存在" in exc.value.detail

    # 套件属于别的项目
    db = _FakeDB(execute_results=[_FakeResult(rows=[_suite(1, project_id=99)])])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pl._validate_plan_suite_ids(db, 5, [PlanSuiteItem(suite_id=1)]))
    assert "不属于当前项目" in exc.value.detail


def test_validate_suite_ids_empty_is_ok():
    assert asyncio.run(pl._validate_plan_suite_ids(_FakeDB(), 5, [])) == []


def test_validate_environment_404_and_wrong_project():
    assert asyncio.run(pl._validate_plan_environment(_FakeDB(), 5, None)) is None

    with pytest.raises(HTTPException) as exc:
        asyncio.run(pl._validate_plan_environment(_FakeDB(), 5, 404))
    assert exc.value.status_code == 404

    db = _FakeDB({("Environment", 3): _Obj(id=3, project_id=99)})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pl._validate_plan_environment(db, 5, 3))
    assert "不属于当前项目" in exc.value.detail


# ── create_plan：cron / webhook 调度处理 ────────────────────


def test_create_plan_cron_computes_next_run():
    db = _FakeDB({("Project", 5): _Obj(id=5), ("TestSuite", 1): _suite(1)}, execute_results=[_FakeResult(rows=[_suite(1)])])
    body = TestPlanCreate(
        name="Nightly",
        project_id=5,
        suite_ids=[PlanSuiteItem(suite_id=1)],
        schedule_type=ScheduleType.cron,
        cron_expression="*/5 * * * *",
    )

    plan = asyncio.run(pl.create_plan(body=body, db=db, current_user=_user()))

    assert plan.next_run_at is not None
    assert plan.creator_id == 9


def test_create_plan_webhook_generates_secret():
    db = _FakeDB({("Project", 5): _Obj(id=5)}, execute_results=[_FakeResult(rows=[])])
    body = TestPlanCreate(name="Hook", project_id=5, suite_ids=[], schedule_type=ScheduleType.webhook)

    plan = asyncio.run(pl.create_plan(body=body, db=db, current_user=_user()))

    assert plan.webhook_secret  # 自动生成


def test_create_plan_404_when_project_missing():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pl.create_plan(body=TestPlanCreate(name="x", project_id=404), db=_FakeDB(), current_user=_user()))
    assert exc.value.status_code == 404


# ── update_plan ─────────────────────────────────────────────


def test_update_plan_clears_next_run_when_not_cron():
    plan = _Obj(id=1, project_id=5, schedule_type=ScheduleType.cron, cron_expression="* * * * *", next_run_at=_now())
    db = _FakeDB({("TestPlan", 1): plan})

    asyncio.run(pl.update_plan(plan_id=1, body=TestPlanUpdate(schedule_type=ScheduleType.manual), db=db, user=_user()))

    assert plan.schedule_type == ScheduleType.manual
    assert plan.next_run_at is None


def test_update_plan_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pl.update_plan(plan_id=404, body=TestPlanUpdate(name="x"), db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404


# ── manual run trigger ──────────────────────────────────────


def test_trigger_plan_run_enqueues_with_env_vars(stubs):
    plan = _Obj(id=1, project_id=5, suite_ids=[{"suite_id": 1}], env_id=3)
    db = _FakeDB(
        {("TestPlan", 1): plan, ("Environment", 3): _Obj(id=3, project_id=5)},
        execute_results=[_FakeResult(rows=[_Obj(id=1, key="k")])],
    )

    run = asyncio.run(pl.trigger_plan_run(plan_id=1, body=PlanRunTrigger(extra_vars={"X": "1"}), db=db, current_user=_user()))

    assert run.trigger_type is TriggerType.manual and run.status is PlanRunStatus.pending
    assert len(stubs["delayed"]) == 1
    # env 变量 + extra_vars 合并传入
    assert stubs["delayed"][0][1] == {"BASE": "x", "X": "1"}


def test_trigger_plan_run_rejects_empty_and_404(stubs):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pl.trigger_plan_run(plan_id=404, body=PlanRunTrigger(), db=_FakeDB(), current_user=_user()))
    assert exc.value.status_code == 404

    plan = _Obj(id=1, project_id=5, suite_ids=[])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            pl.trigger_plan_run(plan_id=1, body=PlanRunTrigger(), db=_FakeDB({("TestPlan", 1): plan}), current_user=_user())
        )
    assert exc.value.status_code == 400 and "没有测试套件" in exc.value.detail


# ── webhook trigger：secret 认证阶梯 ────────────────────────


def _hook_plan(**overrides):
    values = dict(id=1, project_id=5, schedule_type=ScheduleType.webhook, webhook_secret="s3cr3t", suite_ids=[{"suite_id": 1}], env_id=None)
    values.update(overrides)
    return _Obj(**values)


def test_webhook_trigger_success(stubs):
    db = _FakeDB({("TestPlan", 1): _hook_plan()})

    run = asyncio.run(pl.webhook_trigger(body=WebhookTriggerRequest(plan_id=1), x_webhook_secret="s3cr3t", db=db))

    assert run.trigger_type is TriggerType.webhook and run.triggered_by is None
    assert len(stubs["delayed"]) == 1


def test_webhook_trigger_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pl.webhook_trigger(body=WebhookTriggerRequest(plan_id=404), x_webhook_secret="x", db=_FakeDB()))
    assert exc.value.status_code == 404


def test_webhook_trigger_rejects_non_webhook_plan():
    plan = _hook_plan(schedule_type=ScheduleType.manual)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pl.webhook_trigger(body=WebhookTriggerRequest(plan_id=1), x_webhook_secret="s3cr3t", db=_FakeDB({("TestPlan", 1): plan})))
    assert exc.value.status_code == 400 and "不支持 Webhook" in exc.value.detail


def test_webhook_trigger_rejects_bad_secret():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pl.webhook_trigger(body=WebhookTriggerRequest(plan_id=1), x_webhook_secret="wrong", db=_FakeDB({("TestPlan", 1): _hook_plan()})))
    assert exc.value.status_code == 403 and "验证失败" in exc.value.detail


def test_webhook_trigger_rejects_empty_suites():
    plan = _hook_plan(suite_ids=[])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(pl.webhook_trigger(body=WebhookTriggerRequest(plan_id=1), x_webhook_secret="s3cr3t", db=_FakeDB({("TestPlan", 1): plan})))
    assert exc.value.status_code == 400 and "没有测试套件" in exc.value.detail
