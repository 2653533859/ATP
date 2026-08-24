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


@pytest.fixture(autouse=True)
def _isolate_route_behavior_from_run_access_and_redis(monkeypatch):
    async def get_run(db, _user, run_id, _role=None):
        run = await db.get(MobileSpecialRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    monkeypatch.setattr(ms, "_get_run_with_access", get_run)
    monkeypatch.setattr(ms, "request_cancel", lambda _run_id: None)


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
    assert (
        builder(project_id=3, days=14, user=_user(uid=8), noise=1)
        == "atp:mobile-stats:trend:days=14:project_id=3:user_id=8"
    )
    assert builder(project_id=3, days=14, user=_user(uid=9)) != builder(project_id=3, days=14, user=_user(uid=8))

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


def test_create_task_copies_package_from_project_apk(access_recorder):
    db = _FakeDB({("Apk", 12): _Obj(id=12, project_id=5, package_name="com.selected.app")})
    body = MobileSpecialTaskCreate(
        project_id=5,
        name="APK 选择任务",
        task_type=TaskType.performance,
        device_scope_type=DeviceScopeType.single_device,
        apk_id=12,
    )

    task = asyncio.run(ms.create_task(body=body, db=db, current_user=_user(21)))

    assert task.apk_id == 12
    assert task.app_package == "com.selected.app"


def test_create_task_rejects_package_mismatch_with_selected_apk(access_recorder):
    db = _FakeDB({("Apk", 12): _Obj(id=12, project_id=5, package_name="com.selected.app")})
    body = MobileSpecialTaskCreate(
        project_id=5,
        name="包名不一致任务",
        task_type=TaskType.performance,
        device_scope_type=DeviceScopeType.single_device,
        apk_id=12,
        app_package="com.other.app",
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(ms.create_task(body=body, db=db, current_user=_user(21)))

    assert exc.value.status_code == 400


def test_update_task_changes_package_with_selected_apk(access_recorder):
    task = _task(apk_id=None, app_package="com.old.app")
    db = _FakeDB(
        {
            ("MobileSpecialTask", 1): task,
            ("Apk", 13): _Obj(id=13, project_id=5, package_name="com.new.app"),
        }
    )

    updated = asyncio.run(
        ms.update_task(
            1,
            body=MobileSpecialTaskUpdate(apk_id=13),
            db=db,
            current_user=_user(33),
        )
    )

    assert updated.apk_id == 13
    assert updated.app_package == "com.new.app"


def test_update_task_rejects_package_mismatch_with_bound_apk(access_recorder):
    task = _task(apk_id=13, app_package="com.bound.app")
    db = _FakeDB(
        {
            ("MobileSpecialTask", 1): task,
            ("Apk", 13): _Obj(id=13, project_id=5, package_name="com.bound.app"),
        }
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ms.update_task(
                1,
                body=MobileSpecialTaskUpdate(app_package="com.other.app"),
                db=db,
                current_user=_user(33),
            )
        )

    assert exc.value.status_code == 400


def test_create_task_rejects_apk_from_another_project(access_recorder):
    db = _FakeDB({("Apk", 14): _Obj(id=14, project_id=99, package_name="com.other.app")})
    body = MobileSpecialTaskCreate(
        project_id=5,
        name="跨项目 APK",
        task_type=TaskType.performance,
        device_scope_type=DeviceScopeType.single_device,
        apk_id=14,
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(ms.create_task(body=body, db=db, current_user=_user(21)))

    assert exc.value.status_code == 400


def test_create_task_rejects_apk_without_confirmed_package(access_recorder):
    db = _FakeDB({("Apk", 15): _Obj(id=15, project_id=5, package_name=None)})
    body = MobileSpecialTaskCreate(
        project_id=5,
        name="未识别包名 APK",
        task_type=TaskType.performance,
        device_scope_type=DeviceScopeType.single_device,
        apk_id=15,
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(ms.create_task(body=body, db=db, current_user=_user(21)))

    assert exc.value.status_code == 400
    assert "package name" in str(exc.value.detail)


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


def test_trigger_task_run_binds_selected_apk_and_package(access_recorder, monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks_mobile_special",
        types.SimpleNamespace(run_mobile_special_task=types.SimpleNamespace(delay=lambda _rid: None)),
    )
    task = _task(apk_id=11, app_package="com.task.app")
    apk = _Obj(id=12, project_id=5, package_name="com.selected.app")
    db = _FakeDB({("MobileSpecialTask", 1): task, ("Apk", 12): apk})

    run = asyncio.run(
        ms.trigger_task_run(
            1,
            body=RunTriggerRequest(apk_id=12),
            db=db,
            current_user=_user(),
        )
    )

    assert run.apk_id == 12
    assert run.app_package == "com.selected.app"
    assert run.config_snapshot["apk_id"] == 12
    assert run.config_snapshot["app_package"] == "com.selected.app"


def test_trigger_task_run_resolves_task_apk_and_rejects_package_override(access_recorder, monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks_mobile_special",
        types.SimpleNamespace(run_mobile_special_task=types.SimpleNamespace(delay=lambda _rid: None)),
    )
    task = _task(apk_id=11, app_package=None)
    apk = _Obj(id=11, project_id=5, package_name="com.task.app")
    db = _FakeDB({("MobileSpecialTask", 1): task, ("Apk", 11): apk})

    run = asyncio.run(ms.trigger_task_run(1, body=RunTriggerRequest(), db=db, current_user=_user()))

    assert run.apk_id == 11
    assert run.app_package == "com.task.app"
    assert run.config_snapshot["apk_id"] == 11
    assert run.config_snapshot["app_package"] == "com.task.app"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ms.trigger_task_run(
                1,
                body=RunTriggerRequest(app_package="com.other.app"),
                db=_FakeDB({("MobileSpecialTask", 1): task, ("Apk", 11): apk}),
                current_user=_user(),
            )
        )

    assert exc.value.status_code == 400


def test_trigger_task_run_rejects_apk_from_another_project(access_recorder, monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks_mobile_special",
        types.SimpleNamespace(run_mobile_special_task=types.SimpleNamespace(delay=lambda _rid: None)),
    )
    task = _task()
    apk = _Obj(id=13, project_id=99, package_name="com.other.app")
    db = _FakeDB({("MobileSpecialTask", 1): task, ("Apk", 13): apk})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ms.trigger_task_run(
                1,
                body=RunTriggerRequest(apk_id=13),
                db=db,
                current_user=_user(),
            )
        )

    assert exc.value.status_code == 400
    assert db.added == []


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


def test_list_run_events_returns_ordered_journal_rows():
    run = _run()
    event = _Obj(
        id=7,
        run_id=10,
        sequence=1,
        event_time=_now(),
        event_type="run_started",
        phase="device_setup",
        action="connect_device",
        level="info",
        message="started",
        parameters_json={"serial": "emu-5554"},
        result_json={"ok": True},
        duration_ms=None,
    )
    db = _FakeDB({("MobileSpecialRun", 10): run}, execute_rows=[[event]])

    result = asyncio.run(ms.list_run_events(10, limit=1000, db=db))

    assert result == [event]


def test_replay_run_preserves_monkey_seed_and_enqueues(access_recorder, monkeypatch):
    delayed = []
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks_mobile_special",
        types.SimpleNamespace(run_mobile_special_task=types.SimpleNamespace(delay=lambda rid: delayed.append(rid))),
    )
    task = _task(config_json={"duration_seconds": 30, "monkey_seed": 2468})
    source = _run(config_snapshot={"duration_seconds": 30, "monkey_seed": 2468})
    db = _FakeDB(
        {
            ("MobileSpecialRun", 10): source,
            ("MobileSpecialTask", 1): task,
        }
    )

    replay = asyncio.run(ms.replay_run(10, db=db, current_user=_user()))

    assert replay.config_snapshot["monkey_seed"] == 2468
    assert replay.config_snapshot["replay_of_run_id"] == 10
    assert replay.device_serial == source.device_serial
    assert delayed == [replay.id]


def test_get_run_artifact_url_returns_presigned_storage_url(monkeypatch):
    run = _run()
    artifact = _Obj(
        id=3,
        run_id=10,
        file_name="incident-replay.mp4",
        file_path="android-special/runs/10/incident-replay.mp4",
    )
    db = _FakeDB(
        {("MobileSpecialRun", 10): run, ("MobileRunArtifact", 3): artifact},
    )
    monkeypatch.setattr(ms, "presigned_url", lambda path: f"https://minio.test/{path}")

    result = asyncio.run(ms.get_run_artifact_url(10, 3, db=db))

    assert result == {
        "url": "https://minio.test/android-special/runs/10/incident-replay.mp4",
        "file_name": "incident-replay.mp4",
    }

    with pytest.raises(HTTPException) as exc:
        asyncio.run(ms.get_run_artifact_url(10, 404, db=db))
    assert exc.value.status_code == 404


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
        execute_rows=[[_sample()], [incident], [], [artifact]],
    )

    response = asyncio.run(ms.export_run_json(10, db=db))

    report = json.loads(response.body)
    assert report["run"]["task_name"] == "稳定性巡检"
    assert report["run"]["status"] == "pending"
    assert report["samples"][0]["metric_type"] == "cpu_pct"
    assert report["incidents"][0]["incident_type"] == "anr"
    assert report["events"] == []
    assert report["artifacts"][0]["file_name"] == "r.json"

    with pytest.raises(HTTPException):
        asyncio.run(ms.export_run_json(404, db=_FakeDB()))


def test_export_run_json_redacts_run_configuration_and_summary():
    run = _run(
        summary_json={"error": "https://example.test?token=secret", "password": "secret"},
        config_snapshot={"Authorization": "Bearer secret", "safe": "value"},
    )
    db = _FakeDB(
        {("MobileSpecialRun", 10): run, ("MobileSpecialTask", 1): _task()},
        execute_rows=[[], [], [], []],
    )

    response = asyncio.run(ms.export_run_json(10, db=db))
    report = json.loads(response.body)

    encoded = json.dumps(report, ensure_ascii=False)
    assert "secret" not in encoded
    assert report["run"]["summary"]["password"] == "[REDACTED]"
    assert report["run"]["config_snapshot"]["Authorization"] == "[REDACTED]"
    assert report["run"]["config_snapshot"]["safe"] == "value"
