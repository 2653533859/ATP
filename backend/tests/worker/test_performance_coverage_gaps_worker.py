"""补齐 backend/app/worker/tasks_performance.py 剩余未覆盖分支的单元测试。

针对 coverage.xml 中 hits=0 的路径：通知构建（含基线回归/节点/资源问题标记）、
分片聚合的三种短路与合并、`run_performance_test` 的五条早退（执行器未启用、
节点不匹配/不可用/不支持/容量已满）、取消、指标采样与落库、环境快照与 legacy
环境变量、数据集注入、节点约束、租约冲突、父运行聚合，`heartbeat_performance_node`
的续租失败/关闭异常/重排，以及 `check_performance_schedules` 的各类跳过分支与
环境覆盖建 run 路径。

Celery 任务函数由伪造 celery_app 重新导入后同步调用；k6 执行器、控制面客户端、
MinIO、数据库会话全部用 fake 隔离，无真实 Redis / k6 / 网络 / sleep。
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

import pytest
import redis

from app.core import config
from app.services.performance_options import ENVIRONMENT_SNAPSHOT_KEY


class _FakeCeleryApp:
    def task(self, *_args, **_kwargs):
        def decorator(func):
            return func

        return decorator


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


class _GapSession:
    """按模型类名取对象的会话：get / execute 队列 / add / commit 全部可观测。"""

    def __init__(self, objects=None, execute_queue=None):
        self.objects = objects or {}
        self.execute_queue = list(execute_queue or [])
        self.added = []
        self.commits = 0
        self.flushes = 0
        self.refreshed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return None

    async def get(self, model, pk, **_kwargs):
        bucket = self.objects.get(model.__name__)
        if isinstance(bucket, dict):
            return bucket.get(pk)
        return bucket

    async def execute(self, _statement):
        if self.execute_queue:
            return self.execute_queue.pop(0)
        return _Result()

    def add(self, item):
        if getattr(item, "id", None) is None:
            item.id = 500 + len(self.added)
        self.added.append(item)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def refresh(self, item):
        self.refreshed.append(item)


class _ControlClient:
    def __init__(self, claimed=True, close_error=None):
        self.claimed = claimed
        self.close_error = close_error
        self.closes = 0
        self.sets = []

    def set(self, key, value, **kwargs):
        self.sets.append((key, value, kwargs))
        return self.claimed

    def get(self, *_args, **_kwargs):
        return None

    def exists(self, *_args, **_kwargs):
        return 0

    def delete(self, *_args, **_kwargs):
        return 1

    def close(self):
        self.closes += 1
        if self.close_error is not None:
            raise self.close_error


@pytest.fixture
def perf_task(monkeypatch):
    monkeypatch.setitem(sys.modules, "app.worker.celery_app", types.SimpleNamespace(celery_app=_FakeCeleryApp()))
    monkeypatch.delitem(sys.modules, "app.worker.tasks_performance", raising=False)
    monkeypatch.delattr(importlib.import_module("app.worker"), "tasks_performance", raising=False)

    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ENABLED", False)
    monkeypatch.setattr(config.settings, "PERFORMANCE_METRICS_ENABLED", False)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_EGRESS_ALLOWLIST", "")

    from app.worker import tasks_performance

    monkeypatch.setattr(tasks_performance, "create_control_client", lambda: _ControlClient())
    monkeypatch.setattr(tasks_performance, "execution_run_lease", lambda *_args, **_kwargs: nullcontext())
    yield tasks_performance

    sys.modules.pop("app.worker.tasks_performance", None)


def _install_session(monkeypatch, session):
    database = importlib.import_module("app.core.database")
    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: session, raising=False)
    return session


def _run(run_id=7, **overrides):
    values = {
        "id": run_id,
        "performance_test_id": 3,
        "project_id": 2,
        "status": "pending",
        "summary": {},
        "options_snapshot": {"vus": 1},
        "raw_result_object_name": None,
        "duration_ms": None,
        "error_message": None,
        "started_at": None,
        "finished_at": None,
    }
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _test(**overrides):
    values = {
        "id": 3,
        "name": "Load test",
        "project_id": 2,
        "executor": "k6",
        "script_object_name": "scripts/load.js",
        "baseline_run_id": None,
    }
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _node(**overrides):
    values = {
        "id": 55,
        "name": "worker-a",
        "queue_name": "performance.worker-a",
        "status": "online",
        "enabled": True,
        "labels": {},
        "capabilities": {"executors": ["k6"]},
        "max_vus": 20,
        "max_concurrency": 2,
        "egress_allowlist": [],
        "last_error": "old error",
        "last_heartbeat_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    return types.SimpleNamespace(**values)


def _install_notify_recorder(monkeypatch, perf_task):
    calls = []

    async def recorder(db, run, test, metric_samples):
        calls.append((db, run, test, metric_samples))

    monkeypatch.setattr(perf_task, "_notify_performance_run", recorder)
    return calls


def _install_heartbeat(monkeypatch, perf_task, node):
    async def heartbeat(_db):
        return node

    monkeypatch.setattr(perf_task, "_heartbeat_worker_node", heartbeat)


def _install_node_checks(monkeypatch, perf_task, *, status="online", supports=True, capacity=True):
    monkeypatch.setattr(perf_task, "effective_node_status", lambda _node: status)
    monkeypatch.setattr(perf_task, "node_supports_executor", lambda _node, _executor: supports)

    async def capacity_check(*_args, **_kwargs):
        return capacity

    monkeypatch.setattr(perf_task, "node_has_capacity", capacity_check)


def _install_executor(monkeypatch, perf_task, summary=None, object_name="performance/runs/7/raw.json"):
    calls = []

    def fake_executor(**kwargs):
        calls.append(kwargs)
        return (summary if summary is not None else {"exit_code": 0}, object_name, 1234)

    monkeypatch.setattr(perf_task, "run_performance_executor", fake_executor)
    return calls


def test_notify_performance_run_returns_when_already_sent(monkeypatch, perf_task):
    sent = []

    async def fake_send(db, project_id, notification):
        sent.append(notification)

    monkeypatch.setattr(importlib.import_module("app.services.notifier"), "send_notifications", fake_send)
    run = _run(7, summary={"__performance_notification_sent": True})
    session = _GapSession()

    asyncio.run(perf_task._notify_performance_run(session, run, _test(), []))

    assert sent == []
    assert session.commits == 0


def test_notify_performance_run_flags_regression_node_and_resource_issues(monkeypatch, perf_task):
    notifier = importlib.import_module("app.services.notifier")
    report = importlib.import_module("app.services.performance_report")
    sent = []

    async def fake_send(db, project_id, notification):
        sent.append((project_id, notification))

    monkeypatch.setattr(notifier, "send_notifications", fake_send)
    monkeypatch.setattr(
        report,
        "build_baseline_comparison",
        lambda baseline_id, run_id, baseline_summary, summary: {"metrics": [{"direction": "regression"}]},
    )
    monkeypatch.setattr(report, "build_performance_gate", lambda status, summary: {"passed": False})
    captured: dict = {}

    def fake_summary(**kwargs):
        captured.update(kwargs)
        return {"summary": "fake"}

    monkeypatch.setattr(perf_task, "build_performance_notification_summary", fake_summary)

    baseline = types.SimpleNamespace(id=8, summary={"rps": 100})
    run = _run(
        7,
        status="failed",
        summary={"rps": 50},
        error_message="指定的性能压测节点当前不可用",
        duration_ms=1000,
    )
    session = _GapSession({"SimpleNamespace": {8: baseline}})

    asyncio.run(
        perf_task._notify_performance_run(
            session, run, _test(baseline_run_id=8, name="Load test"), [{"errors": {"cpu": "high"}}]
        )
    )

    assert captured["baseline_regression"] is True
    assert captured["node_issue"] is True
    assert captured["resource_issue"] is True
    assert captured["test_name"] == "Load test"
    assert captured["gate"] == {"passed": False}
    assert sent == [(2, {"summary": "fake"})]
    assert run.summary["__performance_notification_sent"] is True
    assert session.commits == 1


def test_aggregate_sharded_run_returns_without_parent(perf_task):
    session = _GapSession({"PerformanceRun": {}})

    asyncio.run(perf_task._aggregate_sharded_run(session, 42))

    assert session.commits == 0
    assert session.execute_queue == []


def test_aggregate_sharded_run_skips_unfinished_shards(perf_task):
    parent = _run(42, status="running", summary={})
    shard = _run(51, status="running", summary={})
    session = _GapSession({"PerformanceRun": {42: parent}}, [_Result([shard])])

    asyncio.run(perf_task._aggregate_sharded_run(session, 42))

    assert parent.status == "running"
    assert session.commits == 0


def test_aggregate_sharded_run_merges_terminal_shards(perf_task, monkeypatch):
    payloads = []
    monkeypatch.setattr(
        perf_task, "aggregate_performance_summaries", lambda items: payloads.append(items) or {"shards": len(items)}
    )
    parent = _run(42, status="running", summary={})
    second = _run(
        50,
        status="success",
        summary={"__shard_index": 1, "rps": 10},
        performance_node_id=17,
        started_at=datetime(2026, 5, 29, 1, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 5, 29, 1, 5, tzinfo=timezone.utc),
        duration_ms=1000,
    )
    first = _run(
        51,
        status="failed",
        summary={"__shard_index": 0, "rps": 5},
        performance_node_id=18,
        started_at=datetime(2026, 5, 29, 0, 59, tzinfo=timezone.utc),
        finished_at=datetime(2026, 5, 29, 1, 3, tzinfo=timezone.utc),
        duration_ms=500,
        error_message="boom",
    )
    session = _GapSession({"PerformanceRun": {42: parent}}, [_Result([second, first])])

    asyncio.run(perf_task._aggregate_sharded_run(session, 42))

    assert parent.status == "failed"
    assert payloads == [
        [
            {"run_id": 51, "node_id": 18, "status": "failed", "__shard_index": 0, "rps": 5},
            {"run_id": 50, "node_id": 17, "status": "success", "__shard_index": 1, "rps": 10},
        ]
    ]
    assert parent.summary == {"shards": 2}
    assert parent.started_at == first.started_at
    assert parent.finished_at == second.finished_at
    assert parent.duration_ms == 1000
    assert parent.error_message == "boom"
    assert session.commits == 1


def test_aggregate_sharded_run_marks_cancelled_when_all_shards_cancelled(perf_task, monkeypatch):
    monkeypatch.setattr(perf_task, "aggregate_performance_summaries", lambda items: {})
    parent = _run(42, status="running", summary={})
    shards = [
        _run(51, status="cancelled", summary={"__shard_index": 0}, performance_node_id=17),
        _run(52, status="cancelled", summary={}, performance_node_id=18),
    ]
    session = _GapSession({"PerformanceRun": {42: parent}}, [_Result(shards)])

    asyncio.run(perf_task._aggregate_sharded_run(session, 42))

    assert parent.status == "cancelled"
    assert session.commits == 1


def test_run_performance_test_fails_when_executor_not_enabled(perf_task, monkeypatch):
    run = _run(7)
    test = _test()
    session = _install_session(monkeypatch, _GapSession({"PerformanceRun": {7: run}, "PerformanceTest": {3: test}}))
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: [])
    notified = _install_notify_recorder(monkeypatch, perf_task)

    perf_task.run_performance_test(None, 7)

    assert run.status == "failed"
    assert run.error_message == "当前 worker 未启用 k6 性能执行器"
    assert session.commits == 1
    assert len(notified) == 1


def test_run_performance_test_fails_when_assigned_node_mismatches(perf_task, monkeypatch):
    run = _run(7, performance_node_id=99)
    test = _test()
    session = _install_session(monkeypatch, _GapSession({"PerformanceRun": {7: run}, "PerformanceTest": {3: test}}))
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: ["k6"])
    _install_heartbeat(monkeypatch, perf_task, _node(id=55))
    notified = _install_notify_recorder(monkeypatch, perf_task)

    perf_task.run_performance_test(None, 7)

    assert run.status == "failed"
    assert run.error_message == "指定的性能压测节点与当前 worker 不匹配"
    assert session.commits == 1
    assert len(notified) == 1


def test_run_performance_test_fails_when_assigned_node_unavailable(perf_task, monkeypatch):
    run = _run(7, performance_node_id=55)
    test = _test()
    session = _install_session(monkeypatch, _GapSession({"PerformanceRun": {7: run}, "PerformanceTest": {3: test}}))
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: ["k6"])
    _install_heartbeat(monkeypatch, perf_task, _node(id=55))
    _install_node_checks(monkeypatch, perf_task, status="offline")
    notified = _install_notify_recorder(monkeypatch, perf_task)

    perf_task.run_performance_test(None, 7)

    assert run.status == "failed"
    assert run.error_message == "指定的性能压测节点当前不可用"
    assert session.commits == 1
    assert len(notified) == 1


def test_run_performance_test_fails_when_assigned_node_lacks_executor(perf_task, monkeypatch):
    run = _run(7, performance_node_id=55)
    test = _test()
    session = _install_session(monkeypatch, _GapSession({"PerformanceRun": {7: run}, "PerformanceTest": {3: test}}))
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: ["k6"])
    _install_heartbeat(monkeypatch, perf_task, _node(id=55))
    _install_node_checks(monkeypatch, perf_task, supports=False)
    notified = _install_notify_recorder(monkeypatch, perf_task)

    perf_task.run_performance_test(None, 7)

    assert run.status == "failed"
    assert run.error_message == "指定的性能压测节点不支持 k6 执行器"
    assert session.commits == 1
    assert len(notified) == 1


def test_run_performance_test_fails_when_assigned_node_capacity_is_full(perf_task, monkeypatch):
    run = _run(7, performance_node_id=55)
    test = _test()
    session = _install_session(monkeypatch, _GapSession({"PerformanceRun": {7: run}, "PerformanceTest": {3: test}}))
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: ["k6"])
    _install_heartbeat(monkeypatch, perf_task, _node(id=55))
    _install_node_checks(monkeypatch, perf_task, capacity=False)
    notified = _install_notify_recorder(monkeypatch, perf_task)

    perf_task.run_performance_test(None, 7)

    assert run.status == "failed"
    assert run.error_message == "性能压测节点并发容量已满"
    assert session.commits == 1
    assert len(notified) == 1


def test_run_performance_test_marks_cancelled_when_executor_raises_cancelled(perf_task, monkeypatch):
    from app.services.performance import PerformanceRunCancelled

    run = _run(7)
    test = _test()
    session = _install_session(monkeypatch, _GapSession({"PerformanceRun": {7: run}, "PerformanceTest": {3: test}}))
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: ["k6"])

    def raising_executor(**_kwargs):
        raise PerformanceRunCancelled("cancelled by user")

    monkeypatch.setattr(perf_task, "run_performance_executor", raising_executor)
    notified = _install_notify_recorder(monkeypatch, perf_task)

    perf_task.run_performance_test(None, 7)

    assert run.status == "cancelled"
    assert run.error_message == "用户已停止压测"
    assert run.finished_at is not None
    assert session.commits == 2
    assert len(notified) == 1
    assert notified[0][3] == []


def test_run_performance_test_collects_resource_and_target_metric_samples(perf_task, monkeypatch):
    metrics_module = importlib.import_module("app.services.performance_metrics")
    target_module = importlib.import_module("app.services.performance_target_metrics")

    class _FakeResourceSampler:
        def sample(self):
            return {
                "captured_at": datetime.now(timezone.utc),
                "node_id": "worker-a",
                "source": "resource",
                "metrics": {"cpu_percent": 1.0},
                "errors": {},
            }

    def build_target_sampler(options, *, allowed_hosts=None):
        assert options["target_metrics"] == {"prometheus_url": "http://metrics.example.test/api"}
        assert allowed_hosts == []
        return lambda: {"source": "target", "metrics": {"latency_ms": 5.0}, "errors": {}}

    monkeypatch.setattr(metrics_module, "PerformanceResourceSampler", _FakeResourceSampler)
    monkeypatch.setattr(target_module, "build_target_metric_sampler", build_target_sampler)
    monkeypatch.setattr(perf_task, "build_metric_boundary", lambda options: {"source": "fake"})
    monkeypatch.setattr(config.settings, "PERFORMANCE_METRICS_ENABLED", True)

    run = _run(7, options_snapshot={"vus": 1, "target_metrics": {"prometheus_url": "http://metrics.example.test/api"}})
    test = _test()
    session = _install_session(monkeypatch, _GapSession({"PerformanceRun": {7: run}, "PerformanceTest": {3: test}}))
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: ["k6"])

    calls = []

    def fake_executor(**kwargs):
        calls.append(kwargs)
        kwargs["metric_callback"]()
        kwargs["metric_callback"]()
        return ({"exit_code": 0}, "performance/runs/7/raw.json", 1234)

    monkeypatch.setattr(perf_task, "run_performance_executor", fake_executor)
    notified = _install_notify_recorder(monkeypatch, perf_task)

    perf_task.run_performance_test(None, 7)

    assert calls[0]["metric_callback"] is not None
    assert run.status == "success"
    assert run.summary["metric_boundary"] == {"source": "fake"}
    assert run.duration_ms == 1234

    samples = [item for item in session.added if type(item).__name__ == "PerformanceMetricSample"]
    assert len(samples) == 4
    assert {sample.source for sample in samples} == {"resource", "target"}
    assert all(sample.run_id == 7 for sample in samples)
    assert notified[0][3] == [sample for sample in notified[0][3]]
    assert len(notified[0][3]) == 4
    assert session.commits == 2


def test_run_performance_test_rejects_invalid_environment_snapshot(perf_task, monkeypatch):
    run = _run(7, options_snapshot={ENVIRONMENT_SNAPSHOT_KEY: ["not", "a", "dict"]})
    test = _test()
    session = _install_session(monkeypatch, _GapSession({"PerformanceRun": {7: run}, "PerformanceTest": {3: test}}))
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: ["k6"])
    notified = _install_notify_recorder(monkeypatch, perf_task)

    perf_task.run_performance_test(None, 7)

    assert run.status == "failed"
    assert run.error_message == "压测环境快照格式无效"
    assert session.commits == 2
    assert notified[0][3] == []


def test_run_performance_test_injects_legacy_environment_variables(perf_task, monkeypatch):
    encryption = importlib.import_module("app.core.encryption")
    monkeypatch.setattr(
        encryption,
        "decrypt_env_vars",
        lambda variables: {variable.key: "plain:" + variable.value for variable in variables},
    )

    run = _run(7, environment_id=9)
    test = _test()
    session = _install_session(
        monkeypatch,
        _GapSession(
            {"PerformanceRun": {7: run}, "PerformanceTest": {3: test}},
            [_Result([types.SimpleNamespace(key="TOKEN", value="v", is_secret=False)])],
        ),
    )
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: ["k6"])
    calls = _install_executor(monkeypatch, perf_task)
    _install_notify_recorder(monkeypatch, perf_task)

    perf_task.run_performance_test(None, 7)

    assert calls[0]["options"]["env"] == {"TOKEN": "plain:v"}
    assert run.status == "success"
    assert session.commits == 2


def test_run_performance_test_injects_dataset_rows(perf_task, monkeypatch):
    loaded = []

    async def fake_load(db, dataset_id, dataset_version):
        loaded.append((dataset_id, dataset_version))
        return [{"account": "alice"}]

    monkeypatch.setattr(perf_task, "load_dataset_rows", fake_load)
    monkeypatch.setattr(perf_task, "serialize_dataset_rows", lambda rows: '{"count": 1}')

    run = _run(7, dataset_id=9, dataset_version=2)
    test = _test()
    session = _install_session(monkeypatch, _GapSession({"PerformanceRun": {7: run}, "PerformanceTest": {3: test}}))
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: ["k6"])
    calls = _install_executor(monkeypatch, perf_task)
    _install_notify_recorder(monkeypatch, perf_task)

    perf_task.run_performance_test(None, 7)

    assert loaded == [(9, 2)]
    assert calls[0]["options"]["env"]["ATP_DATASET_JSON"] == '{"count": 1}'
    assert session.commits == 2


def test_run_performance_test_fails_on_node_constraint_violation(perf_task, monkeypatch):
    from app.services.performance_node import PerformanceNodeConstraintError

    run = _run(7, performance_node_id=55)
    test = _test()
    session = _install_session(monkeypatch, _GapSession({"PerformanceRun": {7: run}, "PerformanceTest": {3: test}}))
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: ["k6"])
    _install_heartbeat(monkeypatch, perf_task, _node(id=55))
    _install_node_checks(monkeypatch, perf_task)

    def reject(*_args, **_kwargs):
        raise PerformanceNodeConstraintError("节点 egress 不允许访问该目标")

    monkeypatch.setattr(perf_task, "validate_node_options", reject)
    calls = _install_executor(monkeypatch, perf_task)
    notified = _install_notify_recorder(monkeypatch, perf_task)

    perf_task.run_performance_test(None, 7)

    assert calls == []
    assert run.status == "failed"
    assert run.error_message == "节点 egress 不允许访问该目标"
    assert session.commits == 2
    assert len(notified) == 1


def test_run_performance_test_swallows_execution_lease_conflict(perf_task, monkeypatch):
    from app.services.execution_run_leases import ExecutionLeaseConflict

    def conflicting_lease(*_args, **_kwargs):
        raise ExecutionLeaseConflict("performance run already leased")

    monkeypatch.setattr(perf_task, "execution_run_lease", conflicting_lease)

    perf_task.run_performance_test(None, 7)


def test_run_performance_test_notifies_parent_after_shard_aggregation(perf_task, monkeypatch):
    parent = _run(42, status="pending", summary={})
    run = _run(7, parent_run_id=42)
    test = _test()
    shard = _run(51, status="success", summary={"__shard_index": 0}, performance_node_id=17)
    session = _install_session(
        monkeypatch,
        _GapSession(
            {"PerformanceRun": {7: run, 42: parent}, "SimpleNamespace": {42: parent}, "PerformanceTest": {3: test}},
            [_Result([shard])],
        ),
    )
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: ["k6"])
    monkeypatch.setattr(perf_task, "aggregate_performance_summaries", lambda items: {"shards": len(items)})
    _install_executor(monkeypatch, perf_task)
    notified = _install_notify_recorder(monkeypatch, perf_task)

    perf_task.run_performance_test(None, 7)

    assert parent.status == "success"
    assert parent.summary == {"shards": 1}
    assert session.commits == 3
    assert len(notified) == 1
    assert notified[0][1] is parent
    assert notified[0][3] == []


def test_heartbeat_worker_node_refreshes_worker_managed_node(perf_task, monkeypatch):
    from app.worker import tasks_performance

    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ENABLED", True)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ID", "node-1")
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_NAME", "worker-a")
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_QUEUE", "performance.worker-a")
    monkeypatch.setattr(perf_task, "configured_performance_executors", lambda: ["k6"])

    node = _node(
        status="offline",
        labels={"managed_by": "worker_env"},
        queue_name="stale-queue",
        last_error="boom",
    )
    session = _GapSession({"PerformanceNode": {55: node}}, [_Result(scalar=node)])

    result = asyncio.run(tasks_performance._heartbeat_worker_node(session))

    assert result is node
    assert node.status == "online"
    assert node.queue_name == "performance.worker-a"
    assert node.capabilities == {"executors": ["k6"]}
    assert node.last_error is None
    assert session.flushes == 1


def test_heartbeat_worker_node_disables_stopped_node(perf_task):
    from app.worker import tasks_performance

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ENABLED", True)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ID", "node-1")
    try:
        node = _node(enabled=False, status="online", labels={})
        session = _GapSession({"PerformanceNode": {55: node}}, [_Result(scalar=node)])

        result = asyncio.run(tasks_performance._heartbeat_worker_node(session))

        assert result is node
        assert node.status == "disabled"
        assert session.flushes == 1
    finally:
        monkeypatch.undo()


def test_heartbeat_task_ignores_control_client_close_failure(perf_task, monkeypatch):
    client = _ControlClient(claimed=False, close_error=redis.RedisError("redis down"))
    monkeypatch.setattr(perf_task, "create_control_client", lambda: client)
    rescheduled = []

    perf_task.heartbeat_performance_node(types.SimpleNamespace(apply_async=lambda **kwargs: rescheduled.append(kwargs)))

    assert client.closes == 1
    assert rescheduled == []


def test_heartbeat_task_reschedules_after_run_async_failure(perf_task, monkeypatch):
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ENABLED", True)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ID", "node-1")
    client = _ControlClient(claimed=True)
    monkeypatch.setattr(perf_task, "create_control_client", lambda: client)

    def raising_run_async(coro):
        coro.close()
        raise RuntimeError("db down")

    monkeypatch.setattr(perf_task, "run_async", raising_run_async)
    rescheduled = []
    task = types.SimpleNamespace(apply_async=lambda **kwargs: rescheduled.append(kwargs))

    perf_task.heartbeat_performance_node(task)

    assert client.sets[0][2]["nx"] is True
    assert len(rescheduled) == 1
    assert rescheduled[0]["countdown"] == max(5, config.settings.PERFORMANCE_NODE_HEARTBEAT_TIMEOUT_SECONDS // 3)
    assert "queue" in rescheduled[0]


def _scheduled_test(**overrides):
    from app.models.performance import PerformanceTest

    values = {
        "id": 3,
        "project_id": 2,
        "name": "nightly",
        "executor": "k6",
        "script_object_name": "performance/scripts/nightly.js",
        "default_options": {"vus": 3},
        "schedule_enabled": True,
        "cron_expression": "* * * * *",
        "schedule_timezone": "Asia/Shanghai",
        "schedule_environment_id": None,
        "schedule_node_id": None,
        "schedule_options": {"duration": "30s"},
        "next_run_at": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    values.update(overrides)
    return PerformanceTest(**values)


def _install_schedule_dependencies(monkeypatch, perf_task, captured):
    api_module = importlib.import_module("app.api.v1.performance")

    def validate(options, executor):
        captured["validation_options"] = options
        captured["validation_executor"] = executor

    monkeypatch.setattr(api_module, "_validate_performance_options", validate)
    enqueued = []
    monkeypatch.setattr(
        perf_task,
        "enqueue_performance_run",
        lambda task_obj, run_id, queue: enqueued.append((task_obj, run_id, queue)),
    )
    captured["enqueued"] = enqueued
    return api_module


def test_schedule_task_skips_tests_without_cron(perf_task, monkeypatch):
    test = _scheduled_test(cron_expression="")
    session = _install_session(monkeypatch, _GapSession(execute_queue=[_Result([test])]))

    perf_task.check_performance_schedules()

    assert session.added == []
    assert session.commits == 0


def test_schedule_task_creates_run_with_environment_overrides(perf_task, monkeypatch):
    encryption = importlib.import_module("app.core.encryption")
    runtime_module = importlib.import_module("app.services.performance_runtime")
    monkeypatch.setattr(
        encryption,
        "decrypt_env_vars",
        lambda variables: {variable.key: "plain:" + variable.value for variable in variables},
    )
    monkeypatch.setattr(runtime_module, "encrypt", lambda value: "enc:" + value)

    test = _scheduled_test(schedule_environment_id=9)
    session = _install_session(
        monkeypatch,
        _GapSession(
            execute_queue=[
                _Result([test]),
                _Result(scalar=None),
                _Result([types.SimpleNamespace(key="TOKEN", value="v", is_secret=False)]),
            ]
        ),
    )
    captured: dict = {}
    _install_schedule_dependencies(monkeypatch, perf_task, captured)

    perf_task.check_performance_schedules()

    assert len(session.added) == 1
    run = session.added[0]
    assert run.performance_test_id == 3
    assert run.status == "pending"
    assert run.options_snapshot[ENVIRONMENT_SNAPSHOT_KEY] == {"TOKEN": "enc:plain:v"}
    assert captured["validation_options"]["env"] == {"TOKEN": "plain:v"}
    assert captured["validation_executor"] == "k6"
    assert captured["enqueued"] == [(perf_task.run_performance_test, run.id, None)]
    assert session.commits == 1
    assert test.last_scheduled_run_at is not None
    assert test.next_run_at > datetime.now(timezone.utc)


def test_schedule_task_skips_invalid_dataset_binding(perf_task, monkeypatch):
    from app.services.performance_dataset import PerformanceDatasetBindingError

    def raising_binding(*_args, **_kwargs):
        raise PerformanceDatasetBindingError("dataset version missing")

    monkeypatch.setattr(perf_task, "resolve_dataset_binding", raising_binding)
    test = _scheduled_test(dataset_id=9)
    session = _install_session(monkeypatch, _GapSession(execute_queue=[_Result([test]), _Result(scalar=None)]))
    captured: dict = {}
    _install_schedule_dependencies(monkeypatch, perf_task, captured)

    perf_task.check_performance_schedules()

    assert session.added == []
    assert session.commits == 1
    assert test.next_run_at > datetime.now(timezone.utc)


def test_schedule_task_skips_invalid_runtime_options(perf_task, monkeypatch):
    test = _scheduled_test()
    session = _install_session(monkeypatch, _GapSession(execute_queue=[_Result([test]), _Result(scalar=None)]))
    captured: dict = {}
    api_module = _install_schedule_dependencies(monkeypatch, perf_task, captured)

    def rejecting_validate(options, executor):
        raise ValueError("vus 非法")

    monkeypatch.setattr(api_module, "_validate_performance_options", rejecting_validate)

    perf_task.check_performance_schedules()

    assert session.added == []
    assert session.commits == 1
    assert test.next_run_at > datetime.now(timezone.utc)


def test_schedule_task_skips_missing_node(perf_task, monkeypatch):
    test = _scheduled_test(schedule_node_id=88)
    session = _install_session(monkeypatch, _GapSession(execute_queue=[_Result([test]), _Result(scalar=None)]))
    captured: dict = {}
    _install_schedule_dependencies(monkeypatch, perf_task, captured)

    perf_task.check_performance_schedules()

    assert session.added == []
    assert session.commits == 1


def test_schedule_task_skips_offline_node(perf_task, monkeypatch):
    test = _scheduled_test(schedule_node_id=88)
    node = _node(id=88)
    session = _install_session(
        monkeypatch,
        _GapSession({"PerformanceNode": {88: node}}, [_Result([test]), _Result(scalar=None)]),
    )
    captured: dict = {}
    _install_schedule_dependencies(monkeypatch, perf_task, captured)
    monkeypatch.setattr(perf_task, "effective_node_status", lambda _node: "offline")

    perf_task.check_performance_schedules()

    assert session.added == []
    assert session.commits == 1


def test_schedule_task_skips_node_without_executor(perf_task, monkeypatch):
    test = _scheduled_test(schedule_node_id=88)
    node = _node(id=88)
    session = _install_session(
        monkeypatch,
        _GapSession({"PerformanceNode": {88: node}}, [_Result([test]), _Result(scalar=None)]),
    )
    captured: dict = {}
    _install_schedule_dependencies(monkeypatch, perf_task, captured)
    monkeypatch.setattr(perf_task, "effective_node_status", lambda _node: "online")
    monkeypatch.setattr(perf_task, "node_supports_executor", lambda _node, _executor: False)

    perf_task.check_performance_schedules()

    assert session.added == []
    assert session.commits == 1


def test_schedule_task_skips_node_constraint_violation(perf_task, monkeypatch):
    from app.services.performance_node import PerformanceNodeConstraintError

    test = _scheduled_test(schedule_node_id=88)
    node = _node(id=88)
    session = _install_session(
        monkeypatch,
        _GapSession({"PerformanceNode": {88: node}}, [_Result([test]), _Result(scalar=None)]),
    )
    captured: dict = {}
    _install_schedule_dependencies(monkeypatch, perf_task, captured)
    monkeypatch.setattr(perf_task, "effective_node_status", lambda _node: "online")
    monkeypatch.setattr(perf_task, "node_supports_executor", lambda _node, _executor: True)

    def reject(*_args, **_kwargs):
        raise PerformanceNodeConstraintError("egress 不允许")

    monkeypatch.setattr(perf_task, "validate_node_options", reject)

    perf_task.check_performance_schedules()

    assert session.added == []
    assert session.commits == 1


def test_schedule_task_skips_full_node(perf_task, monkeypatch):
    test = _scheduled_test(schedule_node_id=88)
    node = _node(id=88)
    session = _install_session(
        monkeypatch,
        _GapSession({"PerformanceNode": {88: node}}, [_Result([test]), _Result(scalar=None)]),
    )
    captured: dict = {}
    _install_schedule_dependencies(monkeypatch, perf_task, captured)
    monkeypatch.setattr(perf_task, "effective_node_status", lambda _node: "online")
    monkeypatch.setattr(perf_task, "node_supports_executor", lambda _node, _executor: True)
    monkeypatch.setattr(perf_task, "validate_node_options", lambda *_args, **_kwargs: None)

    async def no_capacity(*_args, **_kwargs):
        return False

    monkeypatch.setattr(perf_task, "node_has_capacity", no_capacity)

    perf_task.check_performance_schedules()

    assert session.added == []
    assert session.commits == 1


def test_schedule_task_creates_run_with_dataset_binding(perf_task, monkeypatch):
    loaded = []

    async def fake_binding(db, dataset_id, project_id):
        return (11, 5)

    async def fake_load(db, dataset_id, dataset_version):
        loaded.append((dataset_id, dataset_version))
        return [{"stage": "smoke"}]

    monkeypatch.setattr(perf_task, "resolve_dataset_binding", fake_binding)
    monkeypatch.setattr(perf_task, "load_dataset_rows", fake_load)
    monkeypatch.setattr(perf_task, "serialize_dataset_rows", lambda rows: '{"count": 1}')
    test = _scheduled_test(dataset_id=9)
    session = _install_session(monkeypatch, _GapSession(execute_queue=[_Result([test]), _Result(scalar=None)]))
    captured: dict = {}
    _install_schedule_dependencies(monkeypatch, perf_task, captured)

    perf_task.check_performance_schedules()

    assert loaded == [(11, 5)]
    assert len(session.added) == 1
    run = session.added[0]
    assert run.dataset_id == 11
    assert run.dataset_version == 5
    assert captured["validation_options"]["env"]["ATP_DATASET_JSON"] == '{"count": 1}'
    assert captured["enqueued"] == [(perf_task.run_performance_test, run.id, None)]
    assert session.commits == 1
