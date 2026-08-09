"""Tests for android_stability_executor."""

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules.setdefault(
    "app.core.minio_client",
    types.SimpleNamespace(
        download_file=lambda *args, **kwargs: None,
        upload_file=lambda *args, **kwargs: None,
        presigned_url=lambda *args, **kwargs: "http://example.com/artifact.json",
    ),
)
sys.modules.setdefault(
    "app.core.redis_client",
    types.SimpleNamespace(
        publish_run_event=lambda *args, **kwargs: None,
        get_json_cache=lambda *args, **kwargs: None,
        set_json_cache=lambda *args, **kwargs: None,
        delete_json_cache=lambda *args, **kwargs: None,
        delete_json_cache_pattern=lambda *args, **kwargs: None,
    ),
)

from app.worker.executors import android_stability_executor


class TestMonkeyCommand:
    def test_build_monkey_command_basic(self):
        cmd = android_stability_executor._build_monkey_cmd(
            serial="emulator-5554",
            package="com.example.app",
            interval_ms=500,
            seed=12345,
        )
        assert "shell" in cmd
        assert "monkey" in cmd
        # --pct-syskeys 0 disables system keys
        assert any("--pct-syskeys" in str(a) for a in cmd)
        assert any("com.example.app" in str(a) for a in cmd)

    def test_build_monkey_command_with_count(self):
        cmd = android_stability_executor._build_monkey_cmd(
            serial="emulator-5554",
            package="com.example.app",
            interval_ms=500,
            count=10000,
        )
        # Should contain seed
        joined = " ".join(cmd)
        assert "-s" in joined

    def test_build_monkey_command_includes_throttle(self):
        cmd = android_stability_executor._build_monkey_cmd(
            serial="emulator-5554",
            package="com.example.app",
            interval_ms=500,
        )
        assert any("throttle" in str(a).lower() for a in cmd)


class TestValidateInputs:
    def test_validate_inputs_requires_package(self):
        errors = android_stability_executor._validate_inputs(
            device_serial="emulator-5554",
            app_package=None,
            config_json={},
        )
        assert any("package" in e.lower() for e in errors)

    def test_validate_inputs_accepts_valid_inputs(self):
        errors = android_stability_executor._validate_inputs(
            device_serial="emulator-5554",
            app_package="com.example.app",
            config_json={"duration_seconds": 300, "operation_interval_ms": 500},
        )
        assert errors == []


class TestParseMonkeys:
    def test_parse_logcat_crash_extracts_fatal(self):
        raw = """
        FATAL EXCEPTION: main
        Process: com.example.app
        java.lang.RuntimeException: crash here
        """
        incidents = android_stability_executor._parse_logcat_crashes(raw)
        assert len(incidents) >= 1

    def test_parse_logcat_crash_returns_empty_for_clean_log(self):
        incidents = android_stability_executor._parse_logcat_crashes("normal log message")
        assert incidents == []

    def test_build_logcat_cmd_streams_live_logs(self):
        cmd = android_stability_executor._build_logcat_cmd("emulator-5554")
        assert cmd[:3] == ["adb", "-s", "emulator-5554"]
        assert "logcat" in cmd
        assert "-d" not in cmd


# ── run_mobile_special_stability 主执行链（可控时钟 + fake monkey/logcat 边界）──

import asyncio  # noqa: E402

from app.models.bootstrap import load_all_models  # noqa: E402
from app.models.mobile_special import RunStatus  # noqa: E402

load_all_models()


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


class _FakeMonkeyProc:
    def __init__(self):
        self.returncode = None
        self.terminated = False

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    async def wait(self):
        self.returncode = 0 if self.returncode is None else self.returncode
        return self.returncode


@pytest.fixture()
def chain_events(monkeypatch):
    recorded = []

    async def publish(run_id, payload):
        recorded.append(payload)

    monkeypatch.setattr(android_stability_executor, "_safe_publish", publish)
    return recorded


@pytest.fixture()
def reachable(monkeypatch):
    monkeypatch.setattr(
        android_stability_executor, "_check_device_reachable", lambda serial, timeout=10: (True, "device")
    )


@pytest.fixture()
def fast_clock(monkeypatch):
    """替换执行器模块内的 time/asyncio 绑定：sleep 直接推进假时钟，monkey 子进程为替身。"""
    state = {"now": 0.0, "procs": []}

    async def fake_sleep(secs):
        state["now"] += secs

    async def fake_exec(*cmd, **kwargs):
        proc = _FakeMonkeyProc()
        state["procs"].append((cmd, proc))
        return proc

    time_proxy = types.SimpleNamespace(monotonic=lambda: state["now"])
    asyncio_proxy = types.SimpleNamespace(
        sleep=fake_sleep,
        create_task=asyncio.create_task,
        create_subprocess_exec=fake_exec,
        wait_for=asyncio.wait_for,
        get_event_loop=asyncio.get_event_loop,
        subprocess=asyncio.subprocess,
        TimeoutError=asyncio.TimeoutError,
    )
    monkeypatch.setattr(android_stability_executor, "time", time_proxy)
    monkeypatch.setattr(android_stability_executor, "asyncio", asyncio_proxy)
    return state


@pytest.fixture()
def quiet_heartbeat(monkeypatch):
    class _HB:
        def __init__(self, serial, on_lost=None, executor_label=None):
            self.serial = serial
            self.on_lost = on_lost
            self.lost = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(android_stability_executor, "HeartbeatMonitor", _HB)
    return _HB


@pytest.fixture()
def quiet_start_app(monkeypatch):
    monkeypatch.setattr(android_stability_executor, "_start_app", lambda serial, package: True)


def _logcat_stub(monkeypatch, crashes=None, anrs=None):
    async def fake_monitor(serial, run_id, duration_seconds):
        return list(crashes or []), list(anrs or [])

    monkeypatch.setattr(android_stability_executor, "_run_logcat_monitor", fake_monitor)


def _run_stub(**config):
    return _Obj(id=31, status=RunStatus.pending, config_snapshot=config, device_serial=None, app_package=None)


def test_stability_run_fails_on_validation_error(chain_events):
    db = _FakeDB()
    run = _run_stub(device_serial="emu-5554", duration_seconds=60)  # 缺 app_package

    asyncio.run(android_stability_executor.run_mobile_special_stability(db, run))

    assert run.status is RunStatus.failed
    assert "app_package" in run.summary_json["error_message"]
    assert chain_events[-1]["status"] == "failed"


def test_stability_run_fails_when_device_unreachable(monkeypatch, chain_events):
    monkeypatch.setattr(
        android_stability_executor, "_check_device_reachable", lambda serial, timeout=10: (False, "offline")
    )
    run = _run_stub(device_serial="emu-5554", app_package="com.example.app", duration_seconds=60)

    asyncio.run(android_stability_executor.run_mobile_special_stability(_FakeDB(), run))

    assert run.status is RunStatus.failed
    assert "设备不可达" in run.summary_json["error_message"]


def test_stability_run_happy_path_collects_incidents(
    monkeypatch, chain_events, reachable, fast_clock, quiet_heartbeat, quiet_start_app
):
    _logcat_stub(
        monkeypatch,
        crashes=[{"incident_type": "crash", "title": "FATAL EXCEPTION: main", "detail": "RuntimeException"}],
        anrs=[{"incident_type": "anr", "title": "ANR in com.example.app", "detail": "Input dispatching timed out"}],
    )
    db = _FakeDB()
    run = _run_stub(
        device_serial="emu-5554", app_package="com.example.app", duration_seconds=60, operation_interval_ms=200
    )

    asyncio.run(android_stability_executor.run_mobile_special_stability(db, run))

    assert run.status is RunStatus.completed
    assert run.summary_json["crash_count"] == 1
    assert run.summary_json["anr_count"] == 1
    assert run.summary_json["operation_interval_ms"] == 200
    assert len(db.added) == 2  # 两条 MobileIncident
    types_seen = [e["type"] for e in chain_events]
    assert types_seen[0] == "started"
    assert "progress" in types_seen
    assert types_seen[-1] == "completed"
    # monkey 命令确实按配置构建并停止
    monkey_cmd, monkey_proc = fast_clock["procs"][0]
    assert "monkey" in monkey_cmd and "com.example.app" in monkey_cmd
    assert monkey_proc.terminated is True


def test_stability_run_records_device_lost(
    monkeypatch, chain_events, reachable, fast_clock, quiet_heartbeat, quiet_start_app
):
    class _LostHB(quiet_heartbeat):
        async def __aenter__(self):
            self.lost = True
            if self.on_lost is not None:
                self.on_lost("heartbeat 3 次失败")
            return self

    monkeypatch.setattr(android_stability_executor, "HeartbeatMonitor", _LostHB)
    _logcat_stub(monkeypatch)
    run = _run_stub(device_serial="emu-5554", app_package="com.example.app", duration_seconds=60)

    asyncio.run(android_stability_executor.run_mobile_special_stability(_FakeDB(), run))

    assert run.summary_json["device_lost"] is True
    assert "device_lost_at_sec" in run.summary_json
    assert run.status is RunStatus.completed


def test_stability_run_survives_monkey_exec_failure(
    monkeypatch, chain_events, reachable, fast_clock, quiet_heartbeat, quiet_start_app
):
    async def broken_exec(*cmd, **kwargs):
        raise FileNotFoundError("adb missing")

    fast = fast_clock
    monkeypatch.setattr(android_stability_executor.asyncio, "create_subprocess_exec", broken_exec, raising=False)
    _logcat_stub(monkeypatch)
    run = _run_stub(device_serial="emu-5554", app_package="com.example.app", duration_seconds=60)

    asyncio.run(android_stability_executor.run_mobile_special_stability(_FakeDB(), run))

    assert run.status is RunStatus.completed
    assert run.summary_json["crash_count"] == 0
    assert fast["procs"] == []


def test_run_logcat_monitor_parses_crash_lines(monkeypatch):
    lines = [
        b"FATAL EXCEPTION: main\n",
        b"Process: com.example.app\n",
        b"java.lang.RuntimeException: crash here\n",
    ]

    class _Reader:
        def __init__(self, proc):
            self._proc = proc

        async def readline(self):
            if lines:
                return lines.pop(0)
            self._proc.returncode = 0
            return b""

    class _LogcatProc:
        def __init__(self):
            self.returncode = None
            self.stdout = _Reader(self)

        async def wait(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def kill(self):
            self.returncode = -9

    async def fake_exec(*cmd, **kwargs):
        assert "logcat" in cmd
        return _LogcatProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(android_stability_executor, "_clear_logcat_buffer", lambda serial: None)

    crashes, anrs = asyncio.run(android_stability_executor._run_logcat_monitor("emu-5554", 1, 30))

    assert anrs == []
    assert len(crashes) >= 1
    assert crashes[0]["incident_type"] == "crash"


def test_start_app_uses_safe_run_adb(monkeypatch):
    seen = {}

    def fake_safe_run(serial, args, timeout=15, retries=1):
        seen["args"] = args
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(android_stability_executor, "safe_run_adb", fake_safe_run)
    assert android_stability_executor._start_app("emu-5554", "com.example.app") is True
    assert seen["args"][:3] == ["shell", "am", "start"]

    monkeypatch.setattr(android_stability_executor, "safe_run_adb", lambda *a, **kw: None)
    assert android_stability_executor._start_app("emu-5554", "com.example.app") is False


def test_clear_logcat_buffer_swallows_errors(monkeypatch):
    def broken_run(*a, **kw):
        raise RuntimeError("adb gone")

    monkeypatch.setattr(android_stability_executor.subprocess, "run", broken_run)
    android_stability_executor._clear_logcat_buffer("emu-5554")  # 不应抛异常
