import sys
import types
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules["app.core.minio_client"] = types.SimpleNamespace(
    download_file=lambda *args, **kwargs: None,
    upload_file=lambda *args, **kwargs: None,
    presigned_url=lambda *args, **kwargs: "http://example.com/image.png",
)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(
    publish_run_event=lambda *args, **kwargs: None,
    get_json_cache=lambda *args, **kwargs: None,
    set_json_cache=lambda *args, **kwargs: None,
    delete_json_cache=lambda *args, **kwargs: None,
    delete_json_cache_pattern=lambda *args, **kwargs: None,
)

from app.worker.executors import android_executor


def test_check_device_reachable_reports_offline(monkeypatch):
    class _Proc:
        returncode = 0
        stdout = "offline\n"
        stderr = ""

    monkeypatch.setattr(android_executor.subprocess, "run", lambda *args, **kwargs: _Proc())
    # 关闭重连以保持旧测试语义（旧测试只 mock 一次 subprocess.run）
    from app.core.config import settings

    monkeypatch.setattr(settings, "ADB_RECONNECT_ENABLED", False)
    monkeypatch.setattr(settings, "ADB_RECONNECT_MAX_ATTEMPTS", 1)

    ok, message = android_executor._check_device_reachable("192.168.0.10:5555")

    assert ok is False
    assert "offline" in message


def test_check_device_reachable_reports_unauthorized(monkeypatch):
    class _Proc:
        returncode = 0
        stdout = "unauthorized\n"
        stderr = ""

    monkeypatch.setattr(android_executor.subprocess, "run", lambda *args, **kwargs: _Proc())

    ok, message = android_executor._check_device_reachable("ABC123")

    assert ok is False
    assert "未授权" in message


def test_install_apk_retries_via_safe_run_adb(monkeypatch):
    """APK 安装首次失败、ensure_reachable 成功后第二次成功。"""
    call_log = {"n": 0}

    def _scripted_run(cmd, *args, **kwargs):
        call_log["n"] += 1
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        # 第 1 次 install 失败
        if call_log["n"] == 1:
            return types.SimpleNamespace(returncode=1, stdout="", stderr="connection broken")
        # ensure_reachable 的 get-state
        if "get-state" in cmd_str:
            return types.SimpleNamespace(returncode=0, stdout="device", stderr="")
        # 第 2 次 install 成功
        return types.SimpleNamespace(returncode=0, stdout="Success\n", stderr="")

    monkeypatch.setattr(android_executor.subprocess, "run", _scripted_run)
    # 走 disconnect/connect 路径需要 ADB_RECONNECT_ENABLED；这里不需要重连
    from app.core.config import settings

    monkeypatch.setattr(settings, "ADB_RECONNECT_ENABLED", True)
    # 不真正 sleep
    from app.services import adb_resilience

    monkeypatch.setattr(adb_resilience.time, "sleep", lambda *_: None)

    ok, msg = android_executor._install_apk("192.168.0.10:5555", "/tmp/app.apk")

    assert ok is True
    assert "成功" in msg


def test_check_device_reachable_recovers_via_reconnect(monkeypatch):
    """offline → 自动 disconnect/connect → 第二次 device，应判定恢复。"""
    sequence = iter(
        [
            types.SimpleNamespace(returncode=0, stdout="offline", stderr=""),
            types.SimpleNamespace(returncode=0, stdout="", stderr=""),  # disconnect
            types.SimpleNamespace(returncode=0, stdout="connected to 192.168.0.10:5555", stderr=""),  # connect
            types.SimpleNamespace(returncode=0, stdout="device", stderr=""),
        ]
    )
    monkeypatch.setattr(android_executor.subprocess, "run", lambda *a, **kw: next(sequence))
    from app.services import adb_resilience

    monkeypatch.setattr(adb_resilience.time, "sleep", lambda *_: None)
    from app.core.config import settings

    monkeypatch.setattr(settings, "ADB_RECONNECT_ENABLED", True)
    monkeypatch.setattr(settings, "ADB_RECONNECT_MAX_ATTEMPTS", 3)

    ok, message = android_executor._check_device_reachable("192.168.0.10:5555")

    assert ok is True
    assert "重连后恢复" in message


def test_install_apk_reports_timeout_via_sentinel(monkeypatch):
    """safe_run_adb 内部 TimeoutExpired 会返回带 ADB_TIMEOUT_SENTINEL 的占位 CompletedProcess；
    _install_apk 应通过 is_adb_timeout 识别并给出"安装超时"明确文案，而不是"安装失败"。
    """
    import subprocess as real_subprocess

    def _scripted_run(cmd, *args, **kwargs):
        raise real_subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 60))

    monkeypatch.setattr(android_executor.subprocess, "run", _scripted_run)
    from app.core.config import settings

    # 关闭 reconnect 以避免 ensure_reachable 在重试前再次调用
    monkeypatch.setattr(settings, "ADB_RECONNECT_ENABLED", False)
    from app.services import adb_resilience

    monkeypatch.setattr(adb_resilience.time, "sleep", lambda *_: None)

    ok, msg = android_executor._install_apk("192.168.0.10:5555", "/tmp/app.apk", timeout=15)

    assert ok is False
    assert "超时" in msg
    assert "15" in msg


# ── run_android_case 前置守卫分支 ───────────────────────────

import asyncio  # noqa: E402


class _GuardDB:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


def _events(monkeypatch):
    recorded = []

    async def publish(run_id, payload):
        recorded.append(payload)

    monkeypatch.setattr(android_executor, "_safe_publish", publish)
    return recorded


def test_run_android_case_errors_when_script_missing(monkeypatch):
    events = _events(monkeypatch)
    run = _Obj(id=1, status=None)

    asyncio.run(android_executor.run_android_case(_GuardDB(), run, _Obj(config={}), {}))

    assert run.status.value == "error"
    assert "未上传脚本" in run.error_message
    assert events[-1] == {"type": "completed", "run_id": 1, "status": "error"}


def test_run_android_case_errors_when_device_missing(monkeypatch):
    events = _events(monkeypatch)
    run = _Obj(id=2, status=None)

    asyncio.run(android_executor.run_android_case(_GuardDB(), run, _Obj(config={"script_path": "s.py"}), {}))

    assert run.status.value == "error"
    assert "未选择执行设备" in run.error_message
    assert events[-1]["status"] == "error"


def test_run_android_case_errors_when_device_unreachable(monkeypatch):
    events = _events(monkeypatch)
    monkeypatch.setattr(android_executor, "_check_device_reachable", lambda serial, timeout=10: (False, "offline"))
    run = _Obj(id=3, status=None)

    asyncio.run(
        android_executor.run_android_case(
            _GuardDB(), run, _Obj(config={"script_path": "s.py", "device_serial": "emu-5554"}), {}
        )
    )

    assert run.status.value == "error"
    assert "设备不可达" in run.error_message and "offline" in run.error_message
    assert events[-1]["status"] == "error"


# ── run_android_case 主执行链（fake create_subprocess_exec / HeartbeatMonitor / MinIO 边界）──

import json  # noqa: E402

import pytest  # noqa: E402

from app.models.bootstrap import load_all_models  # noqa: E402
from app.models.case import RunStatus  # noqa: E402

load_all_models()


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0
        self._next_id = 7000

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


class _FakeAsyncProc:
    """asyncio.subprocess.Process 替身：hang=True 时首次 communicate 挂起直到 kill。"""

    def __init__(self, returncode=0, stdout=b"", stderr=b"", hang=False):
        self._final_rc = returncode
        self.returncode = None
        self._stdout = stdout
        self._stderr = stderr
        self._hang = hang
        self.killed = False
        self.terminated = False

    async def communicate(self):
        if self._hang and not self.killed:
            await asyncio.sleep(3600)
        self.returncode = self._final_rc
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True
        self._hang = False

    def terminate(self):
        self.terminated = True


@pytest.fixture()
def chain_events(monkeypatch):
    recorded = []

    async def publish(run_id, payload):
        recorded.append(payload)

    monkeypatch.setattr(android_executor, "_safe_publish", publish)
    return recorded


@pytest.fixture()
def reachable(monkeypatch):
    monkeypatch.setattr(android_executor, "_check_device_reachable", lambda serial, timeout=10: (True, "device"))


@pytest.fixture()
def fake_minio(monkeypatch):
    uploads = []
    monkeypatch.setattr(android_executor, "download_file", lambda src, dst: Path(dst).write_text("# script"))
    monkeypatch.setattr(android_executor, "upload_file", lambda obj, path, ct=None: uploads.append(obj))
    monkeypatch.setattr(android_executor, "presigned_url", lambda obj: f"https://minio/{obj}")
    return uploads


@pytest.fixture()
def healing(monkeypatch):
    calls = {"diagnosis": [], "run_healing": []}

    async def run_healing(_db, run):
        calls["run_healing"].append(run.id)

    monkeypatch.setattr(android_executor, "apply_healing_hook", lambda _step: False)
    monkeypatch.setattr(android_executor, "enqueue_diagnosis", lambda sid: calls["diagnosis"].append(sid))
    monkeypatch.setattr(android_executor, "maybe_enqueue_run_healing", run_healing)
    return calls


@pytest.fixture()
def quiet_heartbeat(monkeypatch):
    class _HB:
        instances = []

        def __init__(self, serial, on_lost=None, executor_label=None):
            self.serial = serial
            self.on_lost = on_lost
            _HB.instances.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    _HB.instances = []
    monkeypatch.setattr(android_executor, "HeartbeatMonitor", _HB)
    return _HB


def _install_exec(
    monkeypatch, *, report=None, returncode=0, stdout=b"", stderr=b"", screenshots=None, hang=False, raise_exc=None
):
    """fake asyncio.create_subprocess_exec：写 --json-report-file 与截图文件后返回替身进程。"""
    procs = []

    async def fake_exec(*cmd, **kwargs):
        if raise_exc is not None:
            raise raise_exc
        tmpdir = Path(kwargs["cwd"])
        if report is not None:
            report_path = next(a.split("=", 1)[1] for a in cmd if str(a).startswith("--json-report-file="))
            Path(report_path).write_text(json.dumps(report), encoding="utf-8")
        for rel in screenshots or []:
            target = tmpdir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"\x89PNG")
        proc = _FakeAsyncProc(returncode=returncode, stdout=stdout, stderr=stderr, hang=hang)
        procs.append(proc)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    return procs


def _case_stub(**extra):
    return _Obj(config={"script_path": "scripts/case.py", "device_serial": "emu-5554", **extra})


def _run(db, run, case, extra_vars=None):
    asyncio.run(android_executor.run_android_case(db, run, case, extra_vars or {}))


def test_android_chain_maps_tests_to_steps(monkeypatch, chain_events, reachable, fake_minio, healing, quiet_heartbeat):
    report = {
        "tests": [
            {"nodeid": "case.py::test_login", "outcome": "passed", "duration": 1.2},
            {
                "nodeid": "case.py::test_cart",
                "outcome": "failed",
                "duration": 0.4,
                "call": {"longrepr": "AssertionError: cart empty"},
            },
            {"nodeid": "case.py::test_later", "outcome": "skipped", "duration": 0.0},
        ]
    }
    _install_exec(monkeypatch, report=report, stdout=b"pytest output")
    db = _FakeDB()
    run = _Obj(id=11, status=RunStatus.pending)

    _run(db, run, _case_stub(), {"BASE_URL": "http://x"})

    assert run.status is RunStatus.failed
    assert [s.status for s in db.added] == [RunStatus.passed, RunStatus.failed, RunStatus.skipped]
    assert db.added[1].error_message == "AssertionError: cart empty"
    assert db.added[0].response_data["stdout"] == "pytest output"
    assert [e["type"] for e in chain_events] == ["step_result", "step_result", "step_result", "completed"]
    assert healing["run_healing"] == [11]


def test_android_chain_all_passed_marks_run_passed(
    monkeypatch, chain_events, reachable, fake_minio, healing, quiet_heartbeat
):
    report = {"tests": [{"nodeid": "case.py::test_ok", "outcome": "passed", "duration": 0.3}]}
    _install_exec(monkeypatch, report=report)
    run = _Obj(id=12, status=RunStatus.pending)

    _run(_FakeDB(), run, _case_stub())

    assert run.status is RunStatus.passed
    assert chain_events[-1]["status"] == "passed"


def test_android_chain_timeout_kills_and_errors(
    monkeypatch, chain_events, reachable, fake_minio, healing, quiet_heartbeat
):
    procs = _install_exec(monkeypatch, report=None, hang=True)
    db = _FakeDB()
    run = _Obj(id=13, status=RunStatus.pending)

    _run(db, run, _case_stub(timeout=1))

    assert run.status is RunStatus.error
    assert "超时" in run.error_message and "1" in run.error_message
    assert procs[0].killed is True
    assert db.added[0].status is RunStatus.error
    assert chain_events[-1]["status"] == "error"


def test_android_chain_subprocess_start_failure(
    monkeypatch, chain_events, reachable, fake_minio, healing, quiet_heartbeat
):
    _install_exec(monkeypatch, raise_exc=FileNotFoundError("python missing"))
    db = _FakeDB()
    run = _Obj(id=14, status=RunStatus.pending)

    _run(db, run, _case_stub())

    assert run.status is RunStatus.error
    assert "pytest 子进程启动失败" in run.error_message
    assert db.added[0].status is RunStatus.error


def test_android_chain_no_tests_reports_stderr(
    monkeypatch, chain_events, reachable, fake_minio, healing, quiet_heartbeat
):
    _install_exec(monkeypatch, report={"tests": []}, stderr=b"collected 0 items")
    run = _Obj(id=15, status=RunStatus.pending)

    _run(_FakeDB(), run, _case_stub())

    assert run.status is RunStatus.error
    assert "collected 0 items" in run.error_message


def test_android_chain_device_lost_mid_run(monkeypatch, chain_events, reachable, fake_minio, healing, quiet_heartbeat):
    class _LostHB(quiet_heartbeat):
        async def __aenter__(self):
            if self.on_lost is not None:
                self.on_lost("heartbeat 连续 3 次失败")
            return self

    monkeypatch.setattr(android_executor, "HeartbeatMonitor", _LostHB)
    report = {"tests": [{"nodeid": "case.py::test_ok", "outcome": "passed", "duration": 0.3}]}
    _install_exec(monkeypatch, report=report)
    db = _FakeDB()
    run = _Obj(id=16, status=RunStatus.pending)

    _run(db, run, _case_stub())

    assert run.status is RunStatus.error
    assert "失联" in run.error_message
    assert db.added[0].status is RunStatus.error


def test_android_chain_apk_install_failure_stops_run(
    monkeypatch, chain_events, reachable, fake_minio, healing, quiet_heartbeat
):
    monkeypatch.setattr(
        android_executor, "_install_apk", lambda serial, path, timeout=120: (False, "connection broken")
    )
    run = _Obj(id=17, status=RunStatus.pending)

    _run(_GuardDB(), run, _case_stub(apk_object_name="apks/app.apk"))

    assert run.status is RunStatus.error
    assert "APK 安装失败" in run.error_message and "connection broken" in run.error_message
    assert chain_events[-1]["status"] == "error"


def test_android_chain_apk_install_success_continues(
    monkeypatch, chain_events, reachable, fake_minio, healing, quiet_heartbeat
):
    installs = []
    monkeypatch.setattr(
        android_executor,
        "_install_apk",
        lambda serial, path, timeout=120: installs.append((serial, path)) or (True, "ok"),
    )
    report = {"tests": [{"nodeid": "case.py::test_ok", "outcome": "passed", "duration": 0.3}]}
    _install_exec(monkeypatch, report=report)
    run = _Obj(id=18, status=RunStatus.pending)

    _run(_FakeDB(), run, _case_stub(apk_object_name="apks/app.apk"))

    assert run.status is RunStatus.passed
    assert installs and installs[0][0] == "emu-5554" and installs[0][1].endswith("app.apk")


def test_android_chain_uploads_screenshot_for_matching_test(
    monkeypatch, chain_events, reachable, fake_minio, healing, quiet_heartbeat
):
    report = {"tests": [{"nodeid": "case.py::test_shot", "outcome": "failed", "duration": 0.2}]}
    _install_exec(monkeypatch, report=report, screenshots=["screenshots/after_test_shot_1.png"])
    db = _FakeDB()
    run = _Obj(id=19, status=RunStatus.pending)

    _run(db, run, _case_stub())

    assert fake_minio == ["screenshots/runs/19/step_0.png"]
    assert db.added[0].screenshot_url == "https://minio/screenshots/runs/19/step_0.png"


def test_android_chain_enqueues_diagnosis_when_hook_requests(
    monkeypatch, chain_events, reachable, fake_minio, healing, quiet_heartbeat
):
    monkeypatch.setattr(android_executor, "apply_healing_hook", lambda _step: True)
    report = {"tests": [{"nodeid": "case.py::test_x", "outcome": "failed", "duration": 0.1}]}
    _install_exec(monkeypatch, report=report)
    db = _FakeDB()

    _run(db, _Obj(id=20, status=RunStatus.pending), _case_stub())

    assert healing["diagnosis"] == [db.added[0].id]


def test_android_chain_generic_exception_marks_run_failed(
    monkeypatch, chain_events, reachable, healing, quiet_heartbeat
):
    def broken_download(src, dst):
        raise RuntimeError("minio down")

    monkeypatch.setattr(android_executor, "download_file", broken_download)
    run = _Obj(id=21, status=RunStatus.pending)

    _run(_FakeDB(), run, _case_stub())

    assert run.status is RunStatus.failed
    assert "minio down" in run.error_message
    assert chain_events[-1]["status"] == "failed"
