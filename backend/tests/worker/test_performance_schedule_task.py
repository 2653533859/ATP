from __future__ import annotations

import importlib
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest


class _FakeCeleryApp:
    def task(self, *_args, **_kwargs):
        def decorate(func):
            return func

        return decorate


class _Result:
    def __init__(self, rows=None, scalar=None):
        self.rows = rows or []
        self.scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def scalar_one_or_none(self):
        return self.scalar


class _Session:
    def __init__(self, tests, active_run_id=None):
        self.tests = tests
        self.active_run_id = active_run_id
        self.execute_count = 0
        self.added = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return None

    async def execute(self, _statement):
        self.execute_count += 1
        if self.execute_count == 1:
            return _Result(rows=self.tests)
        return _Result(scalar=self.active_run_id)

    def add(self, item):
        item.id = 55
        self.added.append(item)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _item):
        return None

    async def get(self, model, _pk):
        return None


@pytest.fixture
def perf_schedule_task(monkeypatch):
    monkeypatch.setitem(sys.modules, "app.worker.celery_app", types.SimpleNamespace(celery_app=_FakeCeleryApp()))
    monkeypatch.delitem(sys.modules, "app.worker.tasks_performance", raising=False)
    from app.worker import tasks_performance

    yield tasks_performance
    sys.modules.pop("app.worker.tasks_performance", None)


def _scheduled_test():
    from app.models.performance import PerformanceTest

    return PerformanceTest(
        id=3,
        project_id=2,
        name="nightly",
        executor="k6",
        script_object_name="performance/scripts/nightly.js",
        default_options={"vus": 3},
        schedule_enabled=True,
        cron_expression="* * * * *",
        schedule_timezone="Asia/Shanghai",
        schedule_environment_id=None,
        schedule_options={"duration": "30s"},
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )


def _install_session(monkeypatch, session):
    database = importlib.import_module("app.core.database")
    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: session, raising=False)


def test_schedule_task_creates_run_and_advances_next_time(perf_schedule_task, monkeypatch):
    session = _Session([_scheduled_test()])
    _install_session(monkeypatch, session)
    dispatched: list[int] = []
    monkeypatch.setattr(
        perf_schedule_task,
        "run_performance_test",
        types.SimpleNamespace(delay=dispatched.append),
    )

    perf_schedule_task.check_performance_schedules()

    assert len(session.added) == 1
    run = session.added[0]
    assert run.performance_test_id == 3
    assert run.options_snapshot == {"vus": 3, "duration": "30s"}
    assert run.status == "pending"
    assert dispatched == [55]
    assert session.tests[0].last_scheduled_run_at is not None
    assert session.tests[0].next_run_at > datetime.now(timezone.utc)


def test_schedule_task_skips_when_same_test_has_an_active_run(perf_schedule_task, monkeypatch):
    test = _scheduled_test()
    session = _Session([test], active_run_id=77)
    _install_session(monkeypatch, session)
    dispatched: list[int] = []
    monkeypatch.setattr(
        perf_schedule_task,
        "run_performance_test",
        types.SimpleNamespace(delay=dispatched.append),
    )

    perf_schedule_task.check_performance_schedules()

    assert session.added == []
    assert dispatched == []
    assert session.commits == 1
    assert test.next_run_at > datetime.now(timezone.utc)


def test_schedule_task_routes_to_selected_node_queue(perf_schedule_task, monkeypatch):
    test = _scheduled_test()
    test.schedule_node_id = 88
    node = types.SimpleNamespace(
        id=88,
        name="worker-a",
        queue_name="performance.worker-a",
        enabled=True,
        status="online",
        last_heartbeat_at=datetime.now(timezone.utc),
        max_concurrency=2,
        max_vus=20,
        egress_allowlist=[],
    )

    class _NodeSession(_Session):
        async def get(self, model, pk):
            if model.__name__ == "PerformanceNode" and pk == node.id:
                return node
            return None

        async def execute(self, _statement):
            self.execute_count += 1
            if self.execute_count == 1:
                return _Result(rows=self.tests)
            if self.execute_count == 2:
                return _Result(scalar=self.active_run_id)
            return _Result(rows=[])

    session = _NodeSession([test])
    _install_session(monkeypatch, session)
    dispatched: list[tuple[tuple[int], str]] = []

    class _Task:
        def apply_async(self, *, args, queue):
            dispatched.append((args, queue))

        def delay(self, _run_id):
            raise AssertionError("指定节点后必须进入节点队列")

    monkeypatch.setattr(perf_schedule_task, "run_performance_test", _Task())

    perf_schedule_task.check_performance_schedules()

    run = session.added[0]
    assert run.performance_node_id == node.id
    assert dispatched == [((55,), "performance.worker-a")]
    assert test.next_run_at > datetime.now(timezone.utc)
