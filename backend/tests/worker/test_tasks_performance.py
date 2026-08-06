"""`run_performance_test` Celery 任务的行为缝（Q15-05）。

该任务此前 0% 覆盖 —— k6 压测任务一行测试都没有。这里按仓库既有约定伪造
celery_app、AsyncSessionLocal 与 `run_k6_script`，覆盖五条状态迁移：找不到 run、
找不到 test、k6 成功、k6 非零退出、k6 抛异常。重点是 `finally` 里的
`finished_at` + `commit` 在异常路径上也必须执行，否则 run 会永远停在 running。
"""

from __future__ import annotations

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


@pytest.fixture
def perf_task(monkeypatch):
    """以伪造的 celery_app 重新导入任务模块，避免拿到别的测试留下的真 Task 对象。"""
    monkeypatch.setitem(sys.modules, "app.worker.celery_app", types.SimpleNamespace(celery_app=_FakeCeleryApp()))
    monkeypatch.delitem(sys.modules, "app.worker.tasks_performance", raising=False)

    from app.worker import tasks_performance

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

    assert calls == [{"run_id": 7, "script_object_name": "scripts/load.js", "options": {"vus": 5}}]
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
