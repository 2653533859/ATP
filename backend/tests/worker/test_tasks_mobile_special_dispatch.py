"""tasks_mobile_special Celery 任务体单元缝测试（此前 26%）。

沿用 test_tasks_execution_chain 的约定：导入前 stub celery/redis/tracing 等基础设施，
run_async 换成真正 asyncio.run；AsyncSessionLocal 用 FakeDB 工厂替换；
executor 路由与 .delay 边界按测试注入；config 合并/设备解析/调度重排走真实现。
"""

import asyncio
import importlib
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_REAL_BOOTSTRAP = importlib.import_module("app.models.bootstrap")


class _FakeCeleryApp:
    def task(self, *args, **kwargs):
        def decorator(func):
            func.delay = lambda *a, **kw: None
            return func

        return decorator


sys.modules["app.worker.celery_app"] = types.SimpleNamespace(celery_app=_FakeCeleryApp())
sys.modules["app.models.bootstrap"] = types.SimpleNamespace(load_all_models=lambda: None)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(publish_run_event=None)
sys.modules["app.worker.async_runner"] = types.SimpleNamespace(run_async=lambda coro: asyncio.run(coro))
sys.modules.pop("app.worker.tasks_mobile_special", None)

tms = importlib.import_module("app.worker.tasks_mobile_special")

sys.modules["app.models.bootstrap"] = _REAL_BOOTSTRAP
_REAL_BOOTSTRAP.load_all_models()

from app.models.mobile_special import RunStatus, TaskType, TriggerType  # noqa: E402


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeControlClient:
    def get(self, _key):
        return None

    def delete(self, _key):
        return 1

    def close(self):
        return None


class _FakeDB:
    def __init__(self, objects=None, execute_rows=None):
        self.objects = dict(objects or {})
        self.execute_rows = list(execute_rows or [])
        self.added = []
        self.executed = []
        self.commits = 0
        self._next_id = 800

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        return None

    async def execute(self, query):
        self.executed.append(query)
        rows = self.execute_rows.pop(0) if self.execute_rows else []
        return _FakeResult(rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _install_session(monkeypatch, db):
    monkeypatch.setattr(sys.modules["app.core.database"], "AsyncSessionLocal", lambda: db, raising=False)


def _events(monkeypatch):
    recorded = []

    async def publish(run_id, payload):
        recorded.append(payload)

    monkeypatch.setattr(tms, "publish_run_event", publish)
    return recorded


@pytest.fixture(autouse=True)
def _stub_device_lease(monkeypatch):
    """任务路由测试只验证执行分发，设备租约由独立服务测试覆盖。"""

    async def acquire(_db, _device_id, **_kwargs):
        return _Obj(lease_token="test-device-lease-token")

    async def release(_db, _device_id, _lease_token):
        return True

    monkeypatch.setattr(tms, "acquire_device_lease", acquire)
    monkeypatch.setattr(tms, "release_device_lease", release)


@pytest.fixture(autouse=True)
def _stub_control_client(monkeypatch):
    """任务路由测试不得连接开发机上的真实 Redis。"""

    monkeypatch.setattr(tms, "create_control_client", lambda: _FakeControlClient())


# ── 纯 helper ───────────────────────────────────────────────


def test_merge_run_config_overlays_run_over_task():
    assert tms._merge_run_config({"a": 1, "b": 2}, {"b": 9, "c": 3}) == {"a": 1, "b": 9, "c": 3}
    assert tms._merge_run_config(None, None) == {}


def test_resolve_run_device_id_precedence():
    # config.device_id (int) 优先
    assert tms._resolve_run_device_id(_Obj(config_snapshot={"device_id": 5}, device_id=7), _Obj(device_id=9)) == 5
    # 其次 run.device_id
    assert tms._resolve_run_device_id(_Obj(config_snapshot={}, device_id=7), _Obj(device_id=9)) == 7
    # 最后 task.device_id
    assert tms._resolve_run_device_id(_Obj(config_snapshot={}, device_id=None), _Obj(device_id=9)) == 9


def test_resolve_run_app_package_precedence():
    assert (
        tms._resolve_run_app_package(_Obj(config_snapshot={"app_package": "a"}, app_package="b"), _Obj(app_package="c"))
        == "a"
    )
    assert tms._resolve_run_app_package(_Obj(config_snapshot={}, app_package="b"), _Obj(app_package="c")) == "b"
    assert tms._resolve_run_app_package(_Obj(config_snapshot={}, app_package=None), _Obj(app_package="c")) == "c"


def test_get_device_serial(monkeypatch):
    from app.models.device import Device

    db = _FakeDB({("Device", 3): _Obj(id=3, serial="emu-5554")})
    assert asyncio.run(tms._get_device_serial(db, 3)) == "emu-5554"
    assert asyncio.run(tms._get_device_serial(db, None)) is None
    assert asyncio.run(tms._get_device_serial(_FakeDB(), 404)) is None
    assert Device  # 真模型可导入


def test_safe_publish_swallows_failure(monkeypatch):
    async def broken(_run_id, _payload):
        raise RuntimeError("redis down")

    monkeypatch.setattr(tms, "publish_run_event", broken)
    asyncio.run(tms._safe_publish_run_event(1, {"type": "run_status"}))


# ── run_mobile_special_task ─────────────────────────────────


def _run(run_id=10, task_id=1, **overrides):
    values = dict(
        id=run_id,
        task_id=task_id,
        status=RunStatus.pending,
        config_snapshot={},
        device_id=None,
        app_package=None,
        device_serial=None,
    )
    values.update(overrides)
    return _Obj(**values)


def _task(task_id=1, task_type=TaskType.performance, **overrides):
    values = dict(
        id=task_id, task_type=task_type, config_json={"interval_seconds": 5}, device_id=77, app_package="com.acme"
    )
    values.update(overrides)
    return _Obj(**values)


def test_run_task_returns_when_run_missing(monkeypatch):
    db = _FakeDB()
    _install_session(monkeypatch, db)

    tms.run_mobile_special_task(None, 404)

    assert db.commits == 0


def test_run_task_fails_when_task_missing(monkeypatch):
    run = _run()
    db = _FakeDB({("MobileSpecialRun", 10): run})
    _install_session(monkeypatch, db)

    tms.run_mobile_special_task(None, 10)

    assert run.status is RunStatus.failed
    assert run.summary_json["error_message"] == "Task not found"


@pytest.mark.parametrize(
    ("task_type", "executor_name"),
    [
        (TaskType.performance, "run_mobile_special_perf"),
        (TaskType.stability, "run_mobile_special_stability"),
        (TaskType.fluency, "run_mobile_special_fluency"),
    ],
)
def test_run_task_routes_to_executor_by_type(monkeypatch, task_type, executor_name):
    run = _run()
    task = _task(task_type=task_type)
    db = _FakeDB({("MobileSpecialRun", 10): run, ("MobileSpecialTask", 1): task})
    _install_session(monkeypatch, db)
    events = _events(monkeypatch)
    dispatched = []
    cancel_checks = []

    async def fake_executor(_db, run_obj, **kwargs):
        dispatched.append(run_obj.id)
        cancel_checks.append(kwargs.get("cancel_check"))

    monkeypatch.setitem(
        sys.modules,
        "app.worker.executors",
        types.SimpleNamespace(**{executor_name: fake_executor}),
    )

    tms.run_mobile_special_task(None, 10)

    assert dispatched == [10]
    assert callable(cancel_checks[0])
    # config 合并 + 设备解析落到 run 上
    assert run.config_snapshot["interval_seconds"] == 5
    assert run.device_id == 77 and run.app_package == "com.acme"
    assert events[0]["type"] == "run_status"


def test_run_task_marks_failed_on_executor_exception(monkeypatch):
    run = _run()
    db = _FakeDB({("MobileSpecialRun", 10): run, ("MobileSpecialTask", 1): _task()})
    _install_session(monkeypatch, db)
    events = _events(monkeypatch)

    async def broken(_db, _run, **_kwargs):
        raise RuntimeError("device exploded")

    monkeypatch.setitem(sys.modules, "app.worker.executors", types.SimpleNamespace(run_mobile_special_perf=broken))

    tms.run_mobile_special_task(None, 10)

    assert run.status is RunStatus.failed
    assert "device exploded" in run.summary_json["error_message"]
    assert events[-1]["type"] == "completed" and events[-1]["status"] == "failed"


def test_run_task_resolves_device_serial_from_device(monkeypatch):
    run = _run(device_id=77)
    task = _task()
    db = _FakeDB(
        {("MobileSpecialRun", 10): run, ("MobileSpecialTask", 1): task, ("Device", 77): _Obj(id=77, serial="emu-9")}
    )
    _install_session(monkeypatch, db)
    _events(monkeypatch)

    async def fake_executor(_db, _run):
        return None

    monkeypatch.setitem(
        sys.modules, "app.worker.executors", types.SimpleNamespace(run_mobile_special_perf=fake_executor)
    )

    tms.run_mobile_special_task(None, 10)

    assert run.device_serial == "emu-9"
    assert run.config_snapshot["device_serial"] == "emu-9"


# ── check_mobile_special_schedules ──────────────────────────


def test_check_schedules_triggers_due_task_and_advances(monkeypatch):
    task = _task(cron_expression="*/5 * * * *", next_run_at=None, schedule_enabled=True)
    db = _FakeDB(execute_rows=[[task]])
    _install_session(monkeypatch, db)
    delayed = []
    monkeypatch.setattr(tms.run_mobile_special_task, "delay", lambda rid: delayed.append(rid), raising=False)

    tms.check_mobile_special_schedules()

    assert len(delayed) == 1
    created = db.added[0]
    assert created.trigger_type is TriggerType.schedule
    assert task.next_run_at is not None and task.last_run_at is not None


def test_check_schedules_disables_task_on_invalid_cron(monkeypatch):
    task = _task(cron_expression="not a cron", schedule_enabled=True)
    db = _FakeDB(execute_rows=[[task]])
    _install_session(monkeypatch, db)
    monkeypatch.setattr(tms.run_mobile_special_task, "delay", lambda rid: None, raising=False)

    tms.check_mobile_special_schedules()

    assert task.schedule_enabled is False


# ── cleanup_stale_mobile_special_runs ───────────────────────


def test_cleanup_stale_runs_issues_bulk_update(monkeypatch):
    db = _FakeDB()
    _install_session(monkeypatch, db)

    tms.cleanup_stale_mobile_special_runs()

    assert len(db.executed) == 1 and db.commits == 1
