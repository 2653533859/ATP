"""`run_performance_test` Celery 任务的行为缝（Q15-05）。

该任务此前 0% 覆盖 —— k6 压测任务一行测试都没有。这里按仓库既有约定伪造
celery_app、AsyncSessionLocal 与 `run_k6_script`，覆盖五条状态迁移：找不到 run、
找不到 test、k6 成功、k6 非零退出、k6 抛异常。重点是 `finally` 里的
`finished_at` + `commit` 在异常路径上也必须执行，否则 run 会永远停在 running。
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import types

import pytest


class _FakeCeleryApp:
    def task(self, *_args, **_kwargs):
        def decorator(func):
            return func

        return decorator


class _FakeSession:
    """按模型类返回预置对象，并记录 commit 次数。"""

    def __init__(self, objects: dict):
        self._objects = objects
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return None

    async def get(self, model, _pk):
        return self._objects.get(model.__name__)

    async def commit(self):
        self.commits += 1


class _DatasetResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeControlClient:
    def get(self, _key):
        return None

    def delete(self, _key):
        return 1

    def close(self):
        return None


class _DatasetSession(_FakeSession):
    def __init__(self, objects, dataset_version):
        super().__init__(objects)
        self.dataset_version = dataset_version

    async def execute(self, _statement):
        return _DatasetResult(self.dataset_version)


@pytest.fixture
def perf_task(monkeypatch):
    """以伪造的 celery_app 重新导入任务模块，避免拿到别的测试留下的真 Task 对象。"""
    monkeypatch.setitem(sys.modules, "app.worker.celery_app", types.SimpleNamespace(celery_app=_FakeCeleryApp()))
    monkeypatch.delitem(sys.modules, "app.worker.tasks_performance", raising=False)

    from app.core import config

    # 本地 .env 可能启用显式压测节点，但普通任务单测使用的 fake session 不提供节点心跳查询。
    # 需要覆盖节点行为的用例会在自身测试中显式打开该开关。
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ENABLED", False)

    from app.worker import tasks_performance

    monkeypatch.setattr(tasks_performance, "create_control_client", lambda: _FakeControlClient())
    yield tasks_performance

    sys.modules.pop("app.worker.tasks_performance", None)


def _install_session(monkeypatch, objects: dict) -> _FakeSession:
    # 根 conftest 把 app.core.database 换成了 SimpleNamespace stub，此时
    # `import app.core.database as x` 会因为 app.core 不是真包而失败；
    # import_module 直接命中 sys.modules，两种情况下都拿得到。
    db_module = importlib.import_module("app.core.database")

    session = _FakeSession(objects)
    monkeypatch.setattr(db_module, "AsyncSessionLocal", lambda: session, raising=False)
    return session


def _install_k6(monkeypatch, result=None, error: Exception | None = None) -> list[dict]:
    performance_module = importlib.import_module("app.services.performance")

    calls: list[dict] = []

    def fake_run_k6_script(**kwargs):
        calls.append(kwargs)
        if error is not None:
            raise error
        return result

    monkeypatch.setattr(performance_module, "run_k6_script", fake_run_k6_script)
    return calls


def _run_and_test(status_module):
    run = types.SimpleNamespace(
        id=7,
        performance_test_id=3,
        options_snapshot={"vus": 5},
        status=status_module.pending.value,
        started_at=None,
        finished_at=None,
        summary=None,
        raw_result_object_name=None,
        duration_ms=None,
        error_message=None,
    )
    test = types.SimpleNamespace(script_object_name="scripts/load.js")
    return run, test


def test_missing_run_is_logged_and_does_not_touch_k6(perf_task, monkeypatch):
    session = _install_session(monkeypatch, {})
    calls = _install_k6(monkeypatch, result=({}, "", 0))

    perf_task.run_performance_test(None, 404)

    assert calls == [], "run 不存在时不应启动 k6"
    assert session.commits == 0


def test_missing_test_marks_the_run_failed(perf_task, monkeypatch):
    from app.models.performance import PerformanceRunStatus

    run, _test = _run_and_test(PerformanceRunStatus)
    session = _install_session(monkeypatch, {"PerformanceRun": run})
    calls = _install_k6(monkeypatch, result=({}, "", 0))

    perf_task.run_performance_test(None, 7)

    assert calls == [], "关联的压测配置缺失时不应启动 k6"
    assert run.status == PerformanceRunStatus.failed.value
    assert run.error_message == "Performance test not found"
    assert run.finished_at is not None
    assert session.commits == 1


def test_successful_k6_run_records_summary_and_success_status(perf_task, monkeypatch):
    from app.models.performance import PerformanceRunStatus

    run, test = _run_and_test(PerformanceRunStatus)
    session = _install_session(monkeypatch, {"PerformanceRun": run, "PerformanceTest": test})
    summary = {"exit_code": 0, "k6_error": None, "vus": 5}
    calls = _install_k6(monkeypatch, result=(summary, "raw/7.json", 12345))

    perf_task.run_performance_test(None, 7)

    assert calls[0]["run_id"] == 7
    assert calls[0]["script_object_name"] == "scripts/load.js"
    assert calls[0]["options"] == {"vus": 5}
    assert callable(calls[0]["cancel_check"])
    assert run.status == PerformanceRunStatus.success.value
    assert run.summary == summary
    assert run.raw_result_object_name == "raw/7.json"
    assert run.duration_ms == 12345
    assert run.error_message is None
    assert run.started_at is not None and run.finished_at is not None
    # running 一次 + 结束一次
    assert session.commits == 2


def test_environment_snapshot_is_decrypted_only_for_k6(perf_task, monkeypatch):
    from app.models.performance import PerformanceRunStatus
    from app.services.performance_options import ENVIRONMENT_SNAPSHOT_KEY

    run, test = _run_and_test(PerformanceRunStatus)
    run.options_snapshot = {
        "vus": 5,
        ENVIRONMENT_SNAPSHOT_KEY: {"API_TOKEN": "ciphertext"},
    }
    session = _install_session(monkeypatch, {"PerformanceRun": run, "PerformanceTest": test})
    monkeypatch.setattr(perf_task, "decrypt", lambda value: f"plain:{value}")
    calls = _install_k6(monkeypatch, result=({"exit_code": 0}, "", 1))

    perf_task.run_performance_test(None, 7)

    assert calls[0]["options"] == {"vus": 5, "env": {"API_TOKEN": "plain:ciphertext"}}
    assert ENVIRONMENT_SNAPSHOT_KEY not in calls[0]["options"]
    assert session.commits == 2


def test_pinned_dataset_rows_are_injected_only_into_k6_runtime_env(perf_task, monkeypatch):
    from app.models.performance import PerformanceRunStatus

    run, test = _run_and_test(PerformanceRunStatus)
    run.dataset_id = 9
    run.dataset_version = 3
    dataset_version = types.SimpleNamespace(rows=[{"account": "alice"}, {"account": "bob"}])
    database = importlib.import_module("app.core.database")
    session = _DatasetSession({"PerformanceRun": run, "PerformanceTest": test}, dataset_version)
    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: session, raising=False)
    calls = _install_k6(monkeypatch, result=({"exit_code": 0}, "raw/7.json", 1))

    perf_task.run_performance_test(None, 7)

    assert calls[0]["options"]["env"]["ATP_DATASET_JSON"] == ('[{"account":"alice"},{"account":"bob"}]')


def test_non_zero_exit_code_is_a_failed_run(perf_task, monkeypatch):
    from app.models.performance import PerformanceRunStatus

    run, test = _run_and_test(PerformanceRunStatus)
    _install_session(monkeypatch, {"PerformanceRun": run, "PerformanceTest": test})
    summary = {"exit_code": 99, "k6_error": "thresholds crossed"}
    _install_k6(monkeypatch, result=(summary, "raw/7.json", 500))

    perf_task.run_performance_test(None, 7)

    assert run.status == PerformanceRunStatus.failed.value
    assert run.error_message == "thresholds crossed"
    # 失败也要留下 summary 供排查
    assert run.summary == summary


def test_k6_exception_still_closes_the_run(perf_task, monkeypatch):
    """异常路径必须走到 finally，否则 run 永远停在 running。"""
    from app.models.performance import PerformanceRunStatus

    run, test = _run_and_test(PerformanceRunStatus)
    session = _install_session(monkeypatch, {"PerformanceRun": run, "PerformanceTest": test})
    _install_k6(monkeypatch, error=RuntimeError("x" * 1500))

    perf_task.run_performance_test(None, 7)

    assert run.status == PerformanceRunStatus.failed.value
    assert run.error_message is not None
    assert len(run.error_message) == 1000, "错误信息按 1000 字符截断，避免撑爆列"
    assert run.finished_at is not None
    assert session.commits == 2


def test_cancelled_before_worker_start_never_launches_k6(perf_task, monkeypatch):
    from app.models.performance import PerformanceRunStatus

    run, test = _run_and_test(PerformanceRunStatus)
    session = _install_session(monkeypatch, {"PerformanceRun": run, "PerformanceTest": test})
    calls = _install_k6(monkeypatch, result=({"exit_code": 0}, "raw/7.json", 1))

    class _ControlClient:
        def close(self):
            return None

    monkeypatch.setattr(perf_task, "create_control_client", lambda: _ControlClient())
    monkeypatch.setattr(perf_task, "is_cancel_requested", lambda *_a, **_kw: True)
    monkeypatch.setattr(perf_task, "clear_cancel_request", lambda *_a, **_kw: None)

    perf_task.run_performance_test(None, 7)

    assert calls == []
    assert run.status == PerformanceRunStatus.cancelled.value
    assert run.finished_at is not None
    assert session.commits == 1


class _HeartbeatResult:
    def __init__(self, node=None):
        self.node = node

    def scalar_one_or_none(self):
        return self.node


class _HeartbeatSession:
    def __init__(self, node=None):
        self.node = node
        self.added = []
        self.flushed = 0
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return None

    async def execute(self, _statement):
        return _HeartbeatResult(self.node)

    def add(self, item):
        self.added.append(item)
        self.node = item

    async def flush(self):
        self.flushed += 1

    async def commit(self):
        self.commits += 1


def test_explicit_performance_worker_registers_and_refreshes_heartbeat(perf_task, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ENABLED", True)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ID", "worker-a")
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_NAME", "Worker A")
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_QUEUE", "performance.worker-a")
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_MAX_VUS", 40)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_MAX_CONCURRENCY", 2)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_EGRESS_ALLOWLIST", "api.example.test")

    session = _HeartbeatSession()
    node = asyncio.run(perf_task._heartbeat_worker_node(session))

    assert node is session.added[0]
    assert node.node_id == "worker-a"
    assert node.name == "Worker A"
    assert node.queue_name == "performance.worker-a"
    assert node.status == "online"
    assert node.max_vus == 40
    assert node.max_concurrency == 2
    assert node.egress_allowlist == ["api.example.test"]
    assert node.last_heartbeat_at is not None
    assert session.flushed == 1


def test_ui_managed_performance_node_keeps_page_constraints_during_heartbeat(perf_task, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ENABLED", True)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ID", "worker-a")
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_QUEUE", "performance.worker-a")
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_MAX_VUS", 0)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_MAX_CONCURRENCY", 0)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_EGRESS_ALLOWLIST", "")

    node = types.SimpleNamespace(
        node_id="worker-a",
        name="Windows UI node",
        queue_name="performance.worker-a",
        status="offline",
        enabled=True,
        labels={"managed_by": "ui"},
        capabilities={"executors": ["k6", "jmeter"]},
        max_vus=100,
        max_concurrency=2,
        egress_allowlist=["api.example.test"],
        last_heartbeat_at=None,
        last_error="旧错误",
    )
    session = _HeartbeatSession(node=node)
    refreshed = asyncio.run(perf_task._heartbeat_worker_node(session))

    assert refreshed is node
    assert node.status == "online"
    assert node.name == "Windows UI node"
    assert node.max_vus == 100
    assert node.max_concurrency == 2
    assert node.egress_allowlist == ["api.example.test"]
    assert node.capabilities == {"executors": ["k6", "jmeter"]}
    assert node.last_error is None


def test_ui_managed_performance_node_reports_queue_mismatch(perf_task, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ENABLED", True)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ID", "worker-a")
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_QUEUE", "performance")
    node = types.SimpleNamespace(
        node_id="worker-a",
        name="Windows UI node",
        queue_name="performance.worker-a",
        status="online",
        enabled=True,
        labels={"managed_by": "ui"},
        capabilities={"executors": ["k6"]},
        max_vus=None,
        max_concurrency=None,
        egress_allowlist=[],
        last_heartbeat_at=None,
        last_error=None,
    )
    session = _HeartbeatSession(node=node)

    asyncio.run(perf_task._heartbeat_worker_node(session))

    assert node.status == "offline"
    assert "队列" in node.last_error


def test_performance_worker_heartbeat_refreshes_and_reschedules(perf_task, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ENABLED", True)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_ID", "worker-a")
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_HEARTBEAT_TIMEOUT_SECONDS", 90)
    monkeypatch.setattr(config.settings, "PERFORMANCE_NODE_QUEUE", "performance.worker-a")

    database = importlib.import_module("app.core.database")
    session = _HeartbeatSession()
    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: session, raising=False)

    class _Task:
        def __init__(self):
            self.calls = []

        def apply_async(self, **kwargs):
            self.calls.append(kwargs)

    task = _Task()
    perf_task.heartbeat_performance_node(task)

    assert session.commits == 1
    assert task.calls == [{"countdown": 30, "queue": "performance.worker-a"}]
