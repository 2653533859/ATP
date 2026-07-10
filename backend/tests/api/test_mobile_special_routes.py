"""mobile_special API 路由单元测试（Q13-02 收官切片）。

直接调用路由函数：FakeDB 承载 (模型, 主键) 对象与脚本化查询结果，
assert_project_access / Celery delay 边界按测试注入；schema 校验、
调度状态刷新、CSV/JSON 报告组装走真实现。
"""

import asyncio
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


async def _noop_async(*_a, **_kw):
    return None


# conftest 的 app.api.deps stub 缺 assert_project_access；只补缺失字段，不覆盖已有值
_deps = sys.modules.setdefault("app.api.deps", types.SimpleNamespace())
for _name, _value in (
    ("get_current_user", lambda: None),
    ("require_engineer", lambda: None),
    ("require_admin", lambda: None),
    ("assert_project_access", _noop_async),
):
    if not hasattr(_deps, _name):
        setattr(_deps, _name, _value)

from fastapi import HTTPException  # noqa: E402

from app.api.v1 import mobile_special as ms  # noqa: E402
from app.models.bootstrap import load_all_models  # noqa: E402

load_all_models()

from app.models.mobile_special import (  # noqa: E402
    DeviceScopeType,
    IncidentType,
    MetricType,
    MobileSpecialRun,
    MobileSpecialTask,
    RunStatus,
    TaskType,
    TriggerType,
)
from app.schemas.mobile_special import MobileSpecialTaskCreate, MobileSpecialTaskUpdate, RunTriggerRequest  # noqa: E402


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _Row:
    """模拟 select(Run, Task.name) 的 row：row[0] + row.task_name。"""

    def __init__(self, run, task_name):
        self._run = run
        self.task_name = task_name

    def __getitem__(self, idx):
        assert idx == 0
        return self._run


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, objects=None, execute_rows=None):
        self.objects = dict(objects or {})
        self.execute_rows = list(execute_rows or [])
        self.added = []
        self.deleted = []
        self.commits = 0
        self._next_id = 900

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        if getattr(obj, "created_at", None) is None:
            obj.created_at = _now()
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = _now()

    async def execute(self, _query):
        rows = self.execute_rows.pop(0) if self.execute_rows else []
        return _FakeResult(rows)


def _now():
    return datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc)


@pytest.fixture()
def access_recorder(monkeypatch):
    calls = []

    async def assert_access(_db, _user, project_id, role):
        calls.append((project_id, role))

    monkeypatch.setattr(ms, "assert_project_access", assert_access)
    return calls


def _user(uid=9):
    return _Obj(id=uid)


def _task(task_id=1, project_id=5, **overrides):
    values = dict(
        id=task_id,
        project_id=project_id,
        name="稳定性巡检",
        task_type=TaskType.stability,
        source_type=None,
        apk_id=None,
        app_package="com.acme.app",
        device_scope_type=None,
        device_id=77,
        config_json={"interval_seconds": 5},
        schedule_enabled=False,
        cron_expression=None,
        next_run_at=None,
    )
    values.update(overrides)
    return _Obj(**values)


def _run(run_id=10, task_id=1, status=RunStatus.pending, **overrides):
    values = dict(
        id=run_id,
        task_id=task_id,
        task_type=TaskType.stability,
        status=status,
        device_id=77,
        device_serial="emu-5554",
        apk_id=None,
        app_package="com.acme.app",
        started_at=_now(),
        finished_at=None,
        duration_ms=60_000,
        summary_json={"avg_cpu": 12.5},
        config_snapshot={"interval_seconds": 5},
        trigger_type=TriggerType.manual,
        triggered_by=9,
        created_at=_now(),
        updated_at=_now(),
    )
    values.update(overrides)
    return _Obj(**values)


# ── 调度 helper ─────────────────────────────────────────────


def test_calc_next_run_handles_empty_and_invalid_cron():
    assert ms._calc_next_run(None) is None
    assert ms._calc_next_run("not a cron") is None
    assert ms._calc_next_run("*/5 * * * *") is not None


def test_refresh_schedule_state_sets_and_clears_next_run():
    task = _task(schedule_enabled=True, cron_expression="*/10 * * * *")
    ms._refresh_schedule_state(task)
    assert task.next_run_at is not None

    task.schedule_enabled = False
    ms._refresh_schedule_state(task)
    assert task.next_run_at is None


def test_mobile_stats_cache_key_is_order_stable_and_safe(monkeypatch):
    key = ms._mobile_stats_cache_key("overview", b=2, a=1)
    assert key == "atp:mobile-stats:overview:a=1:b=2"

    builder = ms._build_mobile_stats_cache_key("trend", "project_id", "days")
    assert builder(project_id=3, days=14, noise=1) == "atp:mobile-stats:trend:days=14:project_id=3"

    async def broken(*_a, **_kw):
        raise RuntimeError("redis down")

    monkeypatch.setattr(ms, "get_json_cache", broken)
    monkeypatch.setattr(ms, "set_json_cache", broken)
    assert asyncio.run(ms._safe_get_mobile_stats_cache("k")) is None
    asyncio.run(ms._safe_set_mobile_stats_cache("k", {"v": 1}))  # 不抛异常即通过


# ── Task CRUD ───────────────────────────────────────────────


def test_list_tasks_checks_access_only_with_project_filter(access_recorder):
    db = _FakeDB(execute_rows=[[_task()]])

    tasks = asyncio.run(ms.list_tasks(project_id=5, task_type=TaskType.stability, db=db, user=_user()))

    assert [t.id for t in tasks] == [1]
    assert access_recorder == [(5, ms.ProjectRole.viewer)]

    asyncio.run(ms.list_tasks(project_id=None, task_type=None, db=_FakeDB(execute_rows=[[]]), user=_user()))
    assert len(access_recorder) == 1  # 无 project 过滤时不做访问检查


def test_create_task_refreshes_schedule_and_stamps_creator(access_recorder):
    db = _FakeDB()
    body = MobileSpecialTaskCreate(
        project_id=5,
        name="性能采样",
        task_type=TaskType.performance,
        device_scope_type=DeviceScopeType.single_device,
        app_package="com.acme.app",
        schedule_enabled=True,
        cron_expression="*/15 * * * *",
    )

    task = asyncio.run(ms.create_task(body=body, db=db, current_user=_user(21)))

    assert access_recorder == [(5, ms.ProjectRole.editor)]
    assert task.created_by == 21
    assert task.next_run_at is not None
    assert db.commits == 1 and db.added == [task]


def test_get_update_delete_task_404():
    for call in (
        ms.get_task(404, db=_FakeDB(), user=_user()),
        ms.update_task(404, body=MobileSpecialTaskUpdate(), db=_FakeDB(), current_user=_user()),
        ms.delete_task(404, db=_FakeDB(), user=_user()),
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(call)
        assert exc.value.status_code == 404


def test_update_task_applies_non_none_fields_and_reschedules(access_recorder):
    task = _task(schedule_enabled=True, cron_expression="*/5 * * * *", next_run_at=None)
    db = _FakeDB({("MobileSpecialTask", 1): task})
    body = MobileSpecialTaskUpdate(name="改名", cron_expression="*/30 * * * *")

    updated = asyncio.run(ms.update_task(1, body=body, db=db, current_user=_user(33)))

    assert updated.name == "改名"
    assert updated.updated_by == 33
    assert updated.next_run_at is not None
    assert updated.app_package == "com.acme.app"  # None 字段不覆盖


def test_delete_task_removes_after_access_check(access_recorder):
    task = _task()
    db = _FakeDB({("MobileSpecialTask", 1): task})

    asyncio.run(ms.delete_task(1, db=db, user=_user()))

    assert db.deleted == [task] and db.commits == 1


# ── 触发与停止 ──────────────────────────────────────────────


def test_trigger_task_run_snapshots_config_and_enqueues(access_recorder, monkeypatch):
    delayed = []
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks_mobile_special",
        types.SimpleNamespace(run_mobile_special_task=types.SimpleNamespace(delay=lambda rid: delayed.append(rid))),
    )
    task = _task()
    db = _FakeDB({("MobileSpecialTask", 1): task})
    body = RunTriggerRequest(device_id=88, app_package="com.acme.beta")

    run = asyncio.run(ms.trigger_task_run(1, body=body, db=db, current_user=_user(9)))

    assert run.status is RunStatus.pending
    assert run.trigger_type is TriggerType.manual
    assert run.device_id == 88
    assert run.app_package == "com.acme.beta"
    assert run.config_snapshot["device_id"] == 88
    assert run.config_snapshot["interval_seconds"] == 5
    assert delayed == [run.id]

    with pytest.raises(HTTPException):
        asyncio.run(ms.trigger_task_run(404, body=body, db=_FakeDB(), current_user=_user()))


def test_trigger_task_run_falls_back_to_task_defaults(access_recorder, monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks_mobile_special",
        types.SimpleNamespace(run_mobile_special_task=types.SimpleNamespace(delay=lambda rid: None)),
    )
    task = _task()
    db = _FakeDB({("MobileSpecialTask", 1): task})

    run = asyncio.run(ms.trigger_task_run(1, body=RunTriggerRequest(), db=db, current_user=_user()))

    assert run.device_id == 77
    assert run.app_package == "com.acme.app"
    assert "device_id" not in run.config_snapshot


def test_stop_run_transitions_and_guards():
    run = _run(status=RunStatus.running)
    db = _FakeDB({("MobileSpecialRun", 10): run})

    stopped = asyncio.run(ms.stop_run(10, db=db))

    assert stopped.status is RunStatus.stopped
    assert stopped.finished_at is not None

    done = _run(run_id=11, status=RunStatus.completed)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ms.stop_run(11, db=_FakeDB({("MobileSpecialRun", 11): done})))
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException):
        asyncio.run(ms.stop_run(404, db=_FakeDB()))


# ── 查询与导出 ──────────────────────────────────────────────


def test_list_runs_joins_task_name():
    rows = [_Row(_run(), "稳定性巡检"), _Row(_run(run_id=12), None)]
    db = _FakeDB(execute_rows=[rows])

    items = asyncio.run(ms.list_runs(limit=50, offset=0, db=db))

    assert items[0].task_name == "稳定性巡检"
    assert items[1].task_name is None
    assert items[0].summary_json == {"avg_cpu": 12.5}


def test_get_run_and_summary():
    run = _run()
    db = _FakeDB({("MobileSpecialRun", 10): run})
    assert asyncio.run(ms.get_run(10, db=db)) is run
    assert asyncio.run(ms.get_run_summary(10, db=db)) == {"avg_cpu": 12.5}

    empty = _run(run_id=13, summary_json=None)
    assert asyncio.run(ms.get_run_summary(13, db=_FakeDB({("MobileSpecialRun", 13): empty}))) == {}

    with pytest.raises(HTTPException):
        asyncio.run(ms.get_run(404, db=_FakeDB()))


def _sample(sid=1, metric=MetricType.cpu_pct, value=12.5):
    return _Obj(
        id=sid,
        run_id=10,
        sample_time=_now(),
        metric_type=metric,
        metric_value=value,
        source="dumpsys",
        extra_json=None,
    )


def test_list_samples_incidents_artifacts_require_run():
    run = _run()
    sample = _sample()
    incident = _Obj(
        id=2,
        run_id=10,
        incident_type=IncidentType.crash,
        event_time=_now(),
        title="crash",
        detail="trace",
        process_name="main",
        thread_name="ui",
        extra_json=None,
    )
    artifact = _Obj(
        id=3,
        run_id=10,
        artifact_type=types.SimpleNamespace(value="csv"),
        file_name="m.csv",
        file_path="mobile/m.csv",
        file_size=128,
        created_at=_now(),
    )
    db = _FakeDB({("MobileSpecialRun", 10): run}, execute_rows=[[sample]])
    assert asyncio.run(ms.list_run_samples(10, limit=1000, db=db))[0] is sample

    db = _FakeDB({("MobileSpecialRun", 10): run}, execute_rows=[[incident]])
    assert asyncio.run(ms.list_run_incidents(10, db=db))[0] is incident

    db = _FakeDB({("MobileSpecialRun", 10): run}, execute_rows=[[artifact]])
    assert asyncio.run(ms.list_run_artifacts(10, db=db))[0] is artifact

    for call in (
        ms.list_run_samples(404, limit=1000, db=_FakeDB()),
        ms.list_run_incidents(404, db=_FakeDB()),
        ms.list_run_artifacts(404, db=_FakeDB()),
    ):
        with pytest.raises(HTTPException):
            asyncio.run(call)


def test_export_run_csv_formats_rows_and_404s_without_samples():
    run = _run()
    db = _FakeDB({("MobileSpecialRun", 10): run}, execute_rows=[[_sample(), _sample(sid=2, value=13.0)]])

    response = asyncio.run(ms.export_run_csv(10, db=db))

    lines = response.body.decode().splitlines()
    assert lines[0] == "id,run_id,sample_time,metric_type,metric_value,source"
    assert lines[1].startswith("1,10,2026-07-10T09:00:00+00:00,cpu_pct,12.5,dumpsys")
    assert "mobile_run_10_metrics.csv" in response.headers["Content-Disposition"]

    empty_db = _FakeDB({("MobileSpecialRun", 10): run}, execute_rows=[[]])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ms.export_run_csv(10, db=empty_db))
    assert exc.value.status_code == 404


def test_export_run_json_bundles_run_samples_incidents_artifacts():
    run = _run()
    task = _task()
    incident = _Obj(
        id=2,
        incident_type=IncidentType.anr,
        event_time=_now(),
        title="ANR",
        detail="main blocked",
        process_name="main",
        thread_name="ui",
    )
    artifact = _Obj(
        id=3,
        artifact_type=types.SimpleNamespace(value="json"),
        file_name="r.json",
        file_path="mobile/r.json",
        file_size=256,
        created_at=_now(),
    )
    db = _FakeDB(
        {("MobileSpecialRun", 10): run, ("MobileSpecialTask", 1): task},
        execute_rows=[[_sample()], [incident], [artifact]],
    )

    response = asyncio.run(ms.export_run_json(10, db=db))

    report = json.loads(response.body)
    assert report["run"]["task_name"] == "稳定性巡检"
    assert report["run"]["status"] == "pending"
    assert report["samples"][0]["metric_type"] == "cpu_pct"
    assert report["incidents"][0]["incident_type"] == "anr"
    assert report["artifacts"][0]["file_name"] == "r.json"

    with pytest.raises(HTTPException):
        asyncio.run(ms.export_run_json(404, db=_FakeDB()))
