"""Tests for android_perf_executor."""

import sys
import types
from pathlib import Path
from datetime import datetime

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules.setdefault(
    "app.core.minio_client",
    types.SimpleNamespace(
        download_file=lambda *args, **kwargs: None,
        upload_file=lambda *args, **kwargs: None,
        upload_bytes=lambda *args, **kwargs: None,
        presigned_url=lambda *args, **kwargs: "http://example.com/artifact.csv",
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

from app.worker.executors import android_perf_executor


class TestDeviceValidation:
    def test_check_device_reachable_reports_offline(self, monkeypatch):
        class _Proc:
            returncode = 0
            stdout = "offline\n"
            stderr = ""

        monkeypatch.setattr(android_perf_executor.subprocess, "run", lambda *args, **kwargs: _Proc())

        ok, message = android_perf_executor._check_device_reachable("192.168.0.10:5555")
        assert ok is False
        assert "offline" in message

    def test_check_device_reachable_reports_unauthorized(self, monkeypatch):
        class _Proc:
            returncode = 0
            stdout = "unauthorized\n"
            stderr = ""

        monkeypatch.setattr(android_perf_executor.subprocess, "run", lambda *args, **kwargs: _Proc())

        ok, message = android_perf_executor._check_device_reachable("ABC123")
        assert ok is False
        assert "未授权" in message

    def test_check_device_reachable_success(self, monkeypatch):
        class _Proc:
            returncode = 0
            stdout = "device\n"
            stderr = ""

        monkeypatch.setattr(android_perf_executor.subprocess, "run", lambda *args, **kwargs: _Proc())

        ok, message = android_perf_executor._check_device_reachable("emulator-5554")
        assert ok is True
        assert "设备在线" in message


class TestValidateInputs:
    def test_validate_inputs_rejects_missing_package(self):
        errors = android_perf_executor._validate_inputs(
            device_serial="emulator-5554",
            app_package=None,
            config_json={},
        )
        assert any("app_package" in e.lower() or "package" in e.lower() for e in errors)

    def test_validate_inputs_accepts_valid_inputs(self):
        errors = android_perf_executor._validate_inputs(
            device_serial="emulator-5554",
            app_package="com.example.app",
            config_json={"duration_seconds": 60},
        )
        assert errors == []

    def test_validate_inputs_rejects_negative_duration(self):
        errors = android_perf_executor._validate_inputs(
            device_serial="emulator-5554",
            app_package="com.example.app",
            config_json={"duration_seconds": -10},
        )
        assert any("duration" in e.lower() for e in errors)


def test_replay_window_is_bounded_to_a_rolling_segment():
    assert android_perf_executor._replay_window_seconds(30) == 30
    assert android_perf_executor._replay_window_seconds(99999) == 1800
    assert android_perf_executor._replay_window_seconds(1) == 5
    assert android_perf_executor._replay_window_seconds("invalid") == 30


class TestComputeSummary:
    def test_compute_summary_from_samples(self):
        samples = [
            {"metric_type": "cpu_pct", "metric_value": 30.0, "sample_time": datetime.now()},
            {"metric_type": "cpu_pct", "metric_value": 50.0, "sample_time": datetime.now()},
            {"metric_type": "cpu_pct", "metric_value": 70.0, "sample_time": datetime.now()},
            {"metric_type": "mem_mb", "metric_value": 200.0, "sample_time": datetime.now()},
            {"metric_type": "mem_mb", "metric_value": 300.0, "sample_time": datetime.now()},
        ]
        summary = android_perf_executor._compute_summary(samples, crash_count=0, anr_count=0)

        assert summary["avg_cpu_pct"] == 50.0
        assert summary["peak_cpu_pct"] == 70.0
        assert summary["avg_mem_mb"] == 250.0
        assert summary["peak_mem_mb"] == 300.0
        assert summary["crash_count"] == 0
        assert summary["anr_count"] == 0

    def test_compute_summary_handles_empty_samples(self):
        summary = android_perf_executor._compute_summary([], crash_count=1, anr_count=1)

        assert summary["avg_cpu_pct"] is None
        assert summary["peak_cpu_pct"] is None
        assert summary["crash_count"] == 1
        assert summary["anr_count"] == 1


def test_sample_event_metrics_is_json_safe_and_bounded():
    sample_time = datetime.now()
    samples = [
        {"metric_type": "cpu_pct", "metric_value": 42, "sample_time": sample_time},
        {"metric_type": "mem_mb", "metric_value": 128.5, "sample_time": sample_time},
        {"metric_type": "ignored", "metric_value": "not-a-number", "sample_time": sample_time},
    ]

    result = android_perf_executor._sample_event_metrics(samples)

    assert result == [
        {"metric_type": "cpu_pct", "metric_value": 42.0, "sample_time": sample_time.isoformat()},
        {"metric_type": "mem_mb", "metric_value": 128.5, "sample_time": sample_time.isoformat()},
    ]


class TestHeartbeatIntegration:
    """采样循环外包 HeartbeatMonitor —— 设备掉线时应停止循环并在 summary 中标记。"""

    def test_run_marks_device_lost_in_summary(self, monkeypatch):
        import asyncio
        from app.services import adb_resilience

        # ensure_reachable 前 1 次成功（进入循环），之后返回 offline 模拟掉线
        call_count = {"n": 0}

        def _fake_ensure(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return True, "ok"
            return False, "offline"

        monkeypatch.setattr(adb_resilience, "ensure_reachable", _fake_ensure)
        monkeypatch.setattr(android_perf_executor, "_check_device_reachable", lambda s, timeout=10: (True, "在线"))
        monkeypatch.setattr(android_perf_executor, "_start_app", lambda s, p: True)
        monkeypatch.setattr(android_perf_executor, "_sample_once", _async_return([]))

        # 缩短心跳间隔与阈值，让用例快速触发掉线
        from app.core.config import settings

        monkeypatch.setattr(settings, "ADB_HEARTBEAT_INTERVAL_SEC", 0)
        monkeypatch.setattr(settings, "ADB_HEARTBEAT_FAILURE_THRESHOLD", 1)

        run = _FakeRun(device_serial="192.168.1.10:5555", app_package="com.foo", duration_seconds=5)
        db = _FakeDB()

        asyncio.run(android_perf_executor.run_mobile_special_perf(db, run))

        # 应在掉线后提前结束（未跑满 5s）
        assert run.summary_json is not None
        assert run.summary_json.get("device_lost") is True
        assert run.summary_json.get("device_lost_at_sec") is not None


def _async_return(value):
    async def _fn(*args, **kwargs):
        return value

    return _fn


class _FakeDB:
    def add(self, obj):
        pass

    async def commit(self):
        pass


class _FakeRun:
    def __init__(self, device_serial, app_package, duration_seconds):
        self.id = 1
        self.task = None
        self.device_serial = device_serial
        self.app_package = app_package
        self.config_snapshot = {
            "device_serial": device_serial,
            "app_package": app_package,
            "duration_seconds": duration_seconds,
            "interval_seconds": 1,
            "auto_start": False,
        }
        self.started_at = None
        self.finished_at = None
        self.status = None
        self.duration_ms = None
        self.summary_json = None


# ── run_mobile_special_perf 主执行链（可控时钟 + fake 采样/上传边界）──

import asyncio  # noqa: E402

from app.models.bootstrap import load_all_models  # noqa: E402
from app.models.mobile_special import MobileRunEvent, RunStatus  # noqa: E402

load_all_models()


class _RecordingDB:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


@pytest.fixture()
def chain_events(monkeypatch):
    recorded = []

    async def publish(run_id, payload):
        recorded.append(payload)

    monkeypatch.setattr(android_perf_executor, "_safe_publish", publish)
    return recorded


@pytest.fixture()
def fast_clock(monkeypatch):
    """time/asyncio 代理：sleep 推进假时钟，避免真实等待。"""
    state = {"now": 0.0}

    async def fake_sleep(secs):
        state["now"] += secs

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    time_proxy = types.SimpleNamespace(monotonic=lambda: state["now"])
    asyncio_proxy = types.SimpleNamespace(
        sleep=fake_sleep,
        get_event_loop=asyncio.get_event_loop,
        wait_for=asyncio.wait_for,
        to_thread=fake_to_thread,
        subprocess=asyncio.subprocess,
    )
    monkeypatch.setattr(android_perf_executor, "time", time_proxy)
    monkeypatch.setattr(android_perf_executor, "asyncio", asyncio_proxy)
    return state


@pytest.fixture()
def quiet_heartbeat(monkeypatch):
    class _HB:
        def __init__(self, serial, on_lost=None, executor_label=None):
            self.on_lost = on_lost
            self.lost = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(android_perf_executor, "HeartbeatMonitor", _HB)
    return _HB


def test_perf_run_fails_on_validation_error(chain_events):
    run = _FakeRun(device_serial="emu-5554", app_package=None, duration_seconds=60)

    asyncio.run(android_perf_executor.run_mobile_special_perf(_RecordingDB(), run))

    assert run.status is RunStatus.failed
    assert "app_package" in run.summary_json["error_message"]
    assert chain_events[-1]["status"] == "failed"


def test_perf_run_fails_when_device_unreachable(monkeypatch, chain_events):
    monkeypatch.setattr(android_perf_executor, "_check_device_reachable", lambda s, timeout=10: (False, "offline"))
    run = _FakeRun(device_serial="emu-5554", app_package="com.example.app", duration_seconds=60)

    asyncio.run(android_perf_executor.run_mobile_special_perf(_RecordingDB(), run))

    assert run.status is RunStatus.failed
    assert "设备不可达" in run.summary_json["error_message"]


def test_perf_run_samples_and_uploads_csv(monkeypatch, chain_events, fast_clock, quiet_heartbeat):
    monkeypatch.setattr(android_perf_executor, "_check_device_reachable", lambda s, timeout=10: (True, "在线"))
    sample_batches = iter(
        [
            [
                {"metric_type": "cpu_pct", "metric_value": 30.0, "source": "top"},
                {"metric_type": "mem_mb", "metric_value": 200.0, "source": "meminfo"},
            ],
            [
                {"metric_type": "cpu_pct", "metric_value": 50.0, "source": "top"},
            ],
        ]
    )

    async def fake_sample_once(serial, package, **kwargs):
        return next(sample_batches, [])

    monkeypatch.setattr(android_perf_executor, "_sample_once", fake_sample_once)
    uploads = []
    monkeypatch.setattr(android_perf_executor, "upload_bytes", lambda name, content, ct: uploads.append(name))

    db = _RecordingDB()
    run = _FakeRun(device_serial="emu-5554", app_package="com.example.app", duration_seconds=2)

    asyncio.run(android_perf_executor.run_mobile_special_perf(db, run))

    assert run.status is RunStatus.completed
    assert run.summary_json["avg_cpu_pct"] == 40.0
    assert run.summary_json["peak_cpu_pct"] == 50.0
    assert run.summary_json["_sample_counts"] == {"cpu_pct": 2, "mem_mb": 1}
    # 3 条 MobileMetricSample + 1 条 CSV artifact
    domain_objects = [item for item in db.added if not isinstance(item, MobileRunEvent)]
    assert len(domain_objects) == 4
    assert uploads == ["mobile-special/runs/1/metrics.csv"]
    artifact = domain_objects[-1]
    assert artifact.file_path == "mobile-special/runs/1/metrics.csv"
    types_seen = [e["type"] for e in chain_events]
    assert types_seen[0] == "started" and types_seen[-1] == "completed"
    assert types_seen.count("sampling") == 2


def test_perf_run_reports_replay_start_failure(monkeypatch, chain_events, fast_clock, quiet_heartbeat):
    monkeypatch.setattr(android_perf_executor, "_check_device_reachable", lambda s, timeout=10: (True, "在线"))
    monkeypatch.setattr(android_perf_executor, "_start_screen_recording", lambda *_args: None)
    monkeypatch.setattr(android_perf_executor, "_collect_incidents", lambda *_args: ([], ""))

    async def fake_finish(*_args, **_kwargs):
        return None, None

    async def fake_sample_once(*_args, **_kwargs):
        return [{"metric_type": "cpu_pct", "metric_value": 10.0, "source": "top"}]

    monkeypatch.setattr(android_perf_executor, "_finish_screen_recording", fake_finish)
    monkeypatch.setattr(android_perf_executor, "_sample_once", fake_sample_once)

    run = _FakeRun(device_serial="emu-5554", app_package="com.example.app", duration_seconds=1)
    run.config_snapshot["capture_replay"] = True

    asyncio.run(android_perf_executor.run_mobile_special_perf(_RecordingDB(), run))

    assert run.status is RunStatus.completed
    assert run.summary_json["incident_replay"] == {
        "requested": True,
        "saved": False,
        "error": "设备不支持或无法启动异常回放录屏",
    }


def test_perf_run_clears_replay_start_warning_when_video_is_saved(
    monkeypatch, chain_events, fast_clock, quiet_heartbeat
):
    monkeypatch.setattr(android_perf_executor, "_check_device_reachable", lambda s, timeout=10: (True, "在线"))

    class _RecordingProcess:
        def poll(self):
            return None

    monkeypatch.setattr(android_perf_executor, "_start_screen_recording", lambda *_args: _RecordingProcess())
    monkeypatch.setattr(android_perf_executor, "_collect_incidents", lambda *_args: ([], ""))

    async def fake_finish(*_args, **_kwargs):
        return "android-special/runs/1/incident-replay.mp4", 12

    async def fake_sample_once(*_args, **_kwargs):
        return [{"metric_type": "cpu_pct", "metric_value": 10.0, "source": "top"}]

    monkeypatch.setattr(android_perf_executor, "_finish_screen_recording", fake_finish)
    monkeypatch.setattr(android_perf_executor, "_sample_once", fake_sample_once)

    run = _FakeRun(device_serial="emu-5554", app_package="com.example.app", duration_seconds=1)
    run.config_snapshot["capture_replay"] = True

    asyncio.run(android_perf_executor.run_mobile_special_perf(_RecordingDB(), run))

    assert run.summary_json["incident_replay"] == {"requested": True, "saved": True, "error": None}


def test_perf_run_honors_cancel_signal(monkeypatch, chain_events, fast_clock, quiet_heartbeat):
    monkeypatch.setattr(android_perf_executor, "_check_device_reachable", lambda s, timeout=10: (True, "在线"))
    sample_calls = []

    async def fake_sample_once(*_args):
        sample_calls.append(True)
        return []

    monkeypatch.setattr(android_perf_executor, "_sample_once", fake_sample_once)
    run = _FakeRun(device_serial="emu-5554", app_package="com.example.app", duration_seconds=60)

    asyncio.run(android_perf_executor.run_mobile_special_perf(_RecordingDB(), run, cancel_check=lambda: True))

    assert run.status is RunStatus.stopped
    assert sample_calls == []
    assert chain_events[-1]["status"] == "stopped"


def test_perf_run_swallows_csv_upload_failure(monkeypatch, chain_events, fast_clock, quiet_heartbeat):
    monkeypatch.setattr(android_perf_executor, "_check_device_reachable", lambda s, timeout=10: (True, "在线"))

    async def fake_sample_once(serial, package, **kwargs):
        return [{"metric_type": "cpu_pct", "metric_value": 10.0, "source": "top"}]

    monkeypatch.setattr(android_perf_executor, "_sample_once", fake_sample_once)

    def broken_upload(name, content, ct):
        raise RuntimeError("minio down")

    monkeypatch.setattr(android_perf_executor, "upload_bytes", broken_upload)

    db = _RecordingDB()
    run = _FakeRun(device_serial="emu-5554", app_package="com.example.app", duration_seconds=1)

    asyncio.run(android_perf_executor.run_mobile_special_perf(db, run))

    assert run.status is RunStatus.completed  # 上传失败不影响 run 完成
    # 只有 MobileMetricSample，没有 artifact 行
    assert all(type(o).__name__ != "MobileRunArtifact" for o in db.added)


def test_perf_run_fails_when_no_metrics_are_collected(monkeypatch, chain_events, fast_clock, quiet_heartbeat):
    monkeypatch.setattr(android_perf_executor, "_check_device_reachable", lambda s, timeout=10: (True, "online"))

    async def fake_sample_once(serial, package, **kwargs):
        return []

    monkeypatch.setattr(android_perf_executor, "_sample_once", fake_sample_once)
    db = _RecordingDB()
    run = _FakeRun(device_serial="emu-5554", app_package="com.example.app", duration_seconds=1)

    asyncio.run(android_perf_executor.run_mobile_special_perf(db, run))

    assert run.status is RunStatus.failed
    assert run.summary_json["error_message"] == "未采集到有效性能指标"
    assert chain_events[-1]["status"] == "failed"


def test_sample_once_routes_raw_to_parsers(monkeypatch):
    raws = {"cpu": "RAW_CPU", "mem": "RAW_MEM", "battery": None}

    monkeypatch.setattr(android_perf_executor, "build_cpuinfo_cmd", lambda s, p: "cpu")
    monkeypatch.setattr(android_perf_executor, "build_meminfo_cmd", lambda s, p: "mem")
    monkeypatch.setattr(android_perf_executor, "build_batterystats_cmd", lambda s, p: "battery")
    monkeypatch.setattr(android_perf_executor, "run_adb_shell", lambda serial, cmd, timeout=10: raws[cmd])
    monkeypatch.setattr(
        android_perf_executor, "parse_cpuinfo", lambda raw, p: {"metric_type": "cpu_pct", "metric_value": 12.0}
    )
    monkeypatch.setattr(
        android_perf_executor, "parse_meminfo", lambda raw, p: {"metric_type": "mem_mb", "metric_value": 128.0}
    )
    monkeypatch.setattr(android_perf_executor, "parse_batterystats", lambda raw, p: {"metric_type": "battery_pct"})

    samples = asyncio.run(android_perf_executor._sample_once("emu-5554", "com.example.app"))

    # battery raw 为 None → 跳过；cpu/mem 带 sample_time
    assert [s["metric_type"] for s in samples] == ["cpu_pct", "mem_mb"]
    assert all("sample_time" in s for s in samples)


def test_sample_once_keeps_zero_cpu_when_process_is_alive(monkeypatch):
    monkeypatch.setattr(android_perf_executor, "build_cpuinfo_cmd", lambda s, p: "cpu")
    monkeypatch.setattr(android_perf_executor, "build_meminfo_cmd", lambda s, p: "mem")
    monkeypatch.setattr(android_perf_executor, "build_batterystats_cmd", lambda s, p: "battery")
    monkeypatch.setattr(
        android_perf_executor, "run_adb_shell", lambda serial, cmd, timeout=10: "RAW" if cmd != "battery" else None
    )
    monkeypatch.setattr(android_perf_executor, "parse_cpuinfo", lambda raw, p: None)
    monkeypatch.setattr(android_perf_executor, "parse_meminfo", lambda raw, p: None)
    monkeypatch.setattr(android_perf_executor, "_resolve_pid", lambda serial, package: 11994)

    samples = asyncio.run(android_perf_executor._sample_once("emu-5554", "com.example.app"))

    assert samples[0]["metric_type"] == "cpu_pct"
    assert samples[0]["metric_value"] == 0.0


def test_sample_once_collects_fps_and_jank_when_enabled(monkeypatch):
    monkeypatch.setattr(android_perf_executor, "build_gfxinfo_cmd", lambda s, p: "gfx")
    monkeypatch.setattr(
        android_perf_executor, "run_adb_shell", lambda serial, cmd, timeout=15: "RAW" if cmd == "gfx" else None
    )
    monkeypatch.setattr(
        android_perf_executor,
        "parse_gfxinfo_framestats",
        lambda raw, package: {
            "metric_type": "fps",
            "metric_value": 58.0,
            "source": "gfxinfo",
            "extra": {"jank_count": 3},
        },
    )

    samples = asyncio.run(
        android_perf_executor._sample_once(
            "emu-5554",
            "com.example.app",
            collect_performance=False,
            collect_jank=True,
        )
    )

    assert [sample["metric_type"] for sample in samples] == ["fps", "jank_count"]
    assert samples[1]["metric_value"] == 3.0


def test_resolve_pid_parses_output(monkeypatch):
    monkeypatch.setattr(android_perf_executor, "build_pidof_cmd", lambda s, p: "pidof")
    monkeypatch.setattr(android_perf_executor, "run_adb_shell", lambda serial, cmd, timeout=5: "12345\n")
    monkeypatch.setattr(android_perf_executor, "parse_pid", lambda raw: 12345)

    assert android_perf_executor._resolve_pid("emu-5554", "com.example.app") == 12345

    monkeypatch.setattr(android_perf_executor, "run_adb_shell", lambda serial, cmd, timeout=5: None)
    assert android_perf_executor._resolve_pid("emu-5554", "com.example.app") is None


def test_start_app_uses_safe_run_adb(monkeypatch):
    seen = {}

    def fake_safe_run(serial, args, timeout=15, retries=1):
        seen["args"] = args
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(android_perf_executor, "safe_run_adb", fake_safe_run)
    assert android_perf_executor._start_app("emu-5554", "com.example.app") is True
    assert seen["args"][:3] == ["shell", "am", "start"]

    monkeypatch.setattr(android_perf_executor, "safe_run_adb", lambda *a, **kw: None)
    assert android_perf_executor._start_app("emu-5554", "com.example.app") is False
