"""web_executor 单元缝测试。

传输边界（subprocess.run 跑 pytest+Playwright、MinIO 下载/上传/presign）全部 fake；
脚本缺失/超时/无测试函数/报告解析→StepResult 落库→事件推送全走真实现。
"""

import asyncio
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 其它测试可能把 app.core.minio_client 换成缺字段的 stub；导入执行器前补齐所需符号
_minio = sys.modules.setdefault("app.core.minio_client", types.SimpleNamespace())
for _name in ("download_file", "upload_file", "presigned_url"):
    if not hasattr(_minio, _name):
        setattr(_minio, _name, lambda *a, **kw: None)

from app.models.bootstrap import load_all_models  # noqa: E402
from app.models.case import RunStatus  # noqa: E402
from app.worker.executors import web_executor  # noqa: E402

load_all_models()


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0
        self._next_id = 5000

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


@pytest.fixture()
def events(monkeypatch):
    recorded = []

    async def publish(run_id, payload):
        recorded.append(payload)

    monkeypatch.setattr(web_executor, "publish_run_event", publish)
    return recorded


@pytest.fixture()
def healing(monkeypatch):
    calls = {"diagnosis": [], "run_healing": []}

    async def run_healing(_db, run):
        calls["run_healing"].append(run.id)

    monkeypatch.setattr(web_executor, "apply_healing_hook", lambda _step: False)
    monkeypatch.setattr(web_executor, "enqueue_diagnosis", lambda sid: calls["diagnosis"].append(sid))
    monkeypatch.setattr(web_executor, "maybe_enqueue_run_healing", run_healing)
    return calls


@pytest.fixture()
def fake_minio(monkeypatch):
    monkeypatch.setattr(web_executor, "download_file", lambda src, dst: Path(dst).write_text("# script"))
    monkeypatch.setattr(web_executor, "upload_file", lambda *a, **kw: None)
    monkeypatch.setattr(web_executor, "presigned_url", lambda obj: f"https://minio/{obj}")


def _run_stub():
    return _Obj(id=1, status=RunStatus.pending, result_summary=None)


def _install_subprocess(monkeypatch, *, report=None, stdout="", stderr="", timeout=False):
    """fake subprocess.run：把 report 写入 --json-report-file，返回带 stdout/stderr 的 proc。"""

    def fake_run(cmd, **kwargs):
        if timeout:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 60))
        if report is not None:
            report_path = next(a.split("=", 1)[1] for a in cmd if a.startswith("--json-report-file="))
            Path(report_path).write_text(json.dumps(report), encoding="utf-8")
        return _Obj(returncode=0, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(web_executor.subprocess, "run", fake_run)


def test_web_executor_errors_when_script_missing(events, fake_minio):
    db = _FakeDB()
    run = _run_stub()

    asyncio.run(web_executor.run_web_case(db, run, _Obj(config={}), {}))

    assert run.status is RunStatus.error
    assert "未上传脚本" in run.error_message
    assert events[-1] == {"type": "completed", "run_id": 1, "status": "error"}


def test_web_executor_marks_timeout_as_error(monkeypatch, events, fake_minio, healing):
    _install_subprocess(monkeypatch, timeout=True)
    db = _FakeDB()
    run = _run_stub()

    asyncio.run(web_executor.run_web_case(db, run, _Obj(config={"script_path": "s.py", "timeout": 5}), {}))

    assert run.status is RunStatus.error
    assert "超时" in run.error_message
    assert db.added[0].status is RunStatus.error


def test_web_executor_errors_when_no_test_functions(monkeypatch, events, fake_minio, healing):
    _install_subprocess(monkeypatch, report={"tests": []}, stderr="collected 0 items")
    db = _FakeDB()
    run = _run_stub()

    asyncio.run(web_executor.run_web_case(db, run, _Obj(config={"script_path": "s.py"}), {}))

    assert run.status is RunStatus.error
    assert "collected 0 items" in run.error_message
    assert events[-1]["status"] == "error"


def test_web_executor_maps_tests_to_steps_and_completes(monkeypatch, events, fake_minio, healing):
    report = {
        "tests": [
            {"nodeid": "test_case.py::test_login", "outcome": "passed", "duration": 1.5},
            {
                "nodeid": "test_case.py::test_checkout",
                "outcome": "failed",
                "duration": 2.0,
                "call": {"longrepr": "AssertionError: price mismatch"},
            },
            {"nodeid": "test_case.py::test_skip", "outcome": "skipped", "duration": 0.0},
        ]
    }
    _install_subprocess(monkeypatch, report=report, stdout="run output")
    db = _FakeDB()
    run = _run_stub()

    asyncio.run(
        web_executor.run_web_case(db, run, _Obj(config={"script_path": "s.py", "browser": "firefox"}), {"BASE": "x"})
    )

    # 有失败 → run 整体 failed
    assert run.status is RunStatus.failed
    statuses = [s.status for s in db.added]
    assert statuses == [RunStatus.passed, RunStatus.failed, RunStatus.skipped]
    assert db.added[1].error_message == "AssertionError: price mismatch"
    assert db.added[0].response_data["stdout"] == "run output"
    assert [e["type"] for e in events] == ["step_result", "step_result", "step_result", "completed"]
    assert healing["run_healing"] == [1]


def test_web_executor_all_passed_marks_run_passed(monkeypatch, events, fake_minio, healing):
    report = {"tests": [{"nodeid": "test_case.py::test_ok", "outcome": "passed", "duration": 0.5}]}
    _install_subprocess(monkeypatch, report=report)
    db = _FakeDB()
    run = _run_stub()

    asyncio.run(web_executor.run_web_case(db, run, _Obj(config={"script_path": "s.py"}), {}))

    assert run.status is RunStatus.passed
    assert events[-1]["status"] == "passed"


def test_web_executor_enqueues_diagnosis_when_hook_requests(monkeypatch, events, fake_minio, healing):
    monkeypatch.setattr(web_executor, "apply_healing_hook", lambda _step: True)
    report = {"tests": [{"nodeid": "test_case.py::test_x", "outcome": "failed", "duration": 1.0}]}
    _install_subprocess(monkeypatch, report=report)
    db = _FakeDB()

    asyncio.run(web_executor.run_web_case(db, _run_stub(), _Obj(config={"script_path": "s.py"}), {}))

    assert healing["diagnosis"] == [db.added[0].id]


def test_web_executor_rejects_unsupported_browser(events, fake_minio, healing):
    db = _FakeDB()
    run = _run_stub()

    asyncio.run(web_executor.run_web_case(db, run, _Obj(config={"script_path": "s.py", "browser": "safari"}), {}))

    assert run.status is RunStatus.error
    assert "不支持的浏览器" in run.error_message
    assert events[-1]["status"] == "error"


def test_web_executor_safe_publish_swallows_redis_failure(monkeypatch):
    async def broken(_run_id, _payload):
        raise RuntimeError("redis down")

    monkeypatch.setattr(web_executor, "publish_run_event", broken)
    asyncio.run(web_executor._safe_publish(1, {"type": "completed"}))
