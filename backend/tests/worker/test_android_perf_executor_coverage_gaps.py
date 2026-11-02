"""补齐 backend/app/worker/executors/android_perf_executor.py 剩余覆盖缺口的单元测试。

覆盖基线 term-missing 中的缺口：`_validate_inputs` 的 serial/interval 校验、
`_collect_incidents` / `_start_screen_recording` / `_remove_remote_recording` 函数体
（既有用例仅做 monkeypatch 未执行函数体）、`_finish_screen_recording` 的停录/上传/尺寸/异常/清理分支、
`_sample_once` 的 CPU 零值回退、内存 fallback 失手、电池温度与 jank 分支、
`_compute_summary` 的 jank_count 直统与无 metric_type 样本，以及
`run_mobile_special_perf` 的 launch_activity、录屏轮转、采样异常吞并、
incident 上报/落库、异常日志与回放上传及失败分支。

全部使用 fake DB / fake recorder / monkeypatch 直调，不依赖真机 ADB、PG、Redis、MinIO。
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
import types
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from app.models.bootstrap import load_all_models
from app.models.mobile_special import (
    ArtifactType,
    MobileIncident,
    MobileMetricSample,
    MobileRunArtifact,
    RunStatus,
)
from app.worker.executors import android_perf_executor

load_all_models()


class _FakeDB:
    """最小 DB 替身：只记录 add 与 commit 次数。"""

    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


class _FakeRecorder:
    """最小事件记录器替身，避免真实 MobileRunEvent 落库。"""

    def __init__(self):
        self.calls = []

    async def initialize(self):
        return None

    async def record(self, **kwargs):
        self.calls.append(kwargs)
        return None


class _RecordingProcess:
    """同步假录屏进程：可配置 terminate/wait/kill 的失败路径。"""

    def __init__(self, *, fail_terminate=False, fail_wait=False, fail_kill=False):
        self.terminated = False
        self.waited = False
        self.killed = False
        self._fail_terminate = fail_terminate
        self._fail_wait = fail_wait
        self._fail_kill = fail_kill

    def terminate(self):
        if self._fail_terminate:
            raise RuntimeError("terminate failed")
        self.terminated = True

    def wait(self, timeout=None):
        if self._fail_wait:
            raise RuntimeError("wait failed")
        self.waited = True
        return 0

    def kill(self):
        if self._fail_kill:
            raise RuntimeError("kill failed")
        self.killed = True


class _StillRecording:
    """poll() 始终返回 None 的假录屏进程（仍在录制）。"""

    def poll(self):
        return None


class _FinishedRecording:
    """poll() 立即返回 0 的假录屏进程（触发分段轮转）。"""

    def poll(self):
        return 0


class _FakeTempFile:
    """NamedTemporaryFile 替身：name 可指向一个不存在的路径。"""

    def __init__(self, name):
        self.name = name

    def close(self):
        return None


def _make_run(**config):
    config.setdefault("device_serial", "emu-5554")
    config.setdefault("app_package", "com.example.app")
    config.setdefault("duration_seconds", 1)
    config.setdefault("interval_seconds", 1)
    config.setdefault("auto_start", False)
    return types.SimpleNamespace(
        id=1,
        task=None,
        device_serial=config["device_serial"],
        app_package=config["app_package"],
        config_snapshot=dict(config),
        started_at=None,
        finished_at=None,
        status=None,
        duration_ms=None,
        summary_json=None,
    )


def _patch_adb_shell(monkeypatch, raws):
    monkeypatch.setattr(android_perf_executor, "build_cpuinfo_cmd", lambda serial, package: "cpu")
    monkeypatch.setattr(android_perf_executor, "build_meminfo_cmd", lambda serial, package: "mem")
    monkeypatch.setattr(android_perf_executor, "build_batterystats_cmd", lambda serial, package: "battery")
    monkeypatch.setattr(android_perf_executor, "build_gfxinfo_cmd", lambda serial, package: "gfx")
    monkeypatch.setattr(android_perf_executor, "build_proc_status_cmd", lambda serial, pid: "status")
    monkeypatch.setattr(android_perf_executor, "run_adb_shell", lambda serial, cmd, timeout=10: raws.get(cmd))


@pytest.fixture()
def chain_events(monkeypatch):
    """捕获 _safe_publish 事件，替代真实 Redis 发布。"""
    recorded = []

    async def publish(run_id, payload):
        recorded.append(payload)

    monkeypatch.setattr(android_perf_executor, "_safe_publish", publish)
    return recorded


@pytest.fixture()
def fast_clock(monkeypatch):
    """假时钟：sleep 只推进时间；to_thread 直接调用，避免真实等待。"""
    state = {"now": 0.0}

    async def fake_sleep(seconds):
        state["now"] += seconds

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(android_perf_executor, "time", types.SimpleNamespace(monotonic=lambda: state["now"]))
    monkeypatch.setattr(
        android_perf_executor,
        "asyncio",
        types.SimpleNamespace(
            sleep=fake_sleep,
            get_event_loop=asyncio.get_event_loop,
            wait_for=asyncio.wait_for,
            to_thread=fake_to_thread,
        ),
    )
    return state


@pytest.fixture()
def quiet_heartbeat(monkeypatch):
    """用不会触发掉线的假心跳替换 HeartbeatMonitor。"""

    class _Heartbeat:
        def __init__(self, serial, on_lost=None, executor_label=None):
            self.lost = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(android_perf_executor, "HeartbeatMonitor", _Heartbeat)
    return _Heartbeat


@pytest.fixture()
def device_online(monkeypatch):
    """设备探活恒为在线，避免真实 adb。"""
    monkeypatch.setattr(android_perf_executor, "_check_device_reachable", lambda serial, timeout=10: (True, "在线"))


# ── _validate_inputs / _safe_publish / 辅助函数 ─────────────────


def test_validate_inputs_reports_missing_serial_and_bad_interval():
    errors = android_perf_executor._validate_inputs(None, None, {"interval_seconds": 0})

    assert "未指定执行设备 serial" in errors
    assert "未指定 app_package" in errors
    assert "interval_seconds 必须大于 0: 0" in errors

    assert android_perf_executor._validate_inputs("emu-5554", "com.example.app", {"interval_seconds": -1}) == [
        "interval_seconds 必须大于 0: -1"
    ]


def test_safe_publish_swallows_publish_failure(monkeypatch):
    calls = []

    async def broken_publish(run_id, payload, run_type=None):
        calls.append((run_id, payload, run_type))
        raise RuntimeError("redis down")

    monkeypatch.setattr(android_perf_executor, "publish_run_event", broken_publish)

    asyncio.run(android_perf_executor._safe_publish(7, {"type": "log"}))

    assert calls == [(7, {"type": "log"}, "mobile")]


def test_clear_logcat_buffer_ignores_subprocess_failure(monkeypatch):
    seen = []

    def ok_run(cmd, **kwargs):
        seen.append(cmd)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(android_perf_executor, "subprocess", types.SimpleNamespace(run=ok_run))
    android_perf_executor._clear_logcat_buffer("emu-5554")

    def broken_run(cmd, **kwargs):
        seen.append(cmd)
        raise FileNotFoundError("adb not installed")

    monkeypatch.setattr(android_perf_executor, "subprocess", types.SimpleNamespace(run=broken_run))
    android_perf_executor._clear_logcat_buffer("emu-5554")

    assert seen == [["adb", "-s", "emu-5554", "logcat", "-c"]] * 2


def test_collect_incidents_handles_empty_and_parsed_logcat(monkeypatch):
    monkeypatch.setattr(android_perf_executor, "run_adb_shell", lambda serial, cmd, timeout=30: None)
    assert android_perf_executor._collect_incidents("emu-5554") == ([], "")

    monkeypatch.setattr(android_perf_executor, "run_adb_shell", lambda serial, cmd, timeout=30: "LOGCAT-RAW")
    monkeypatch.setattr(android_perf_executor, "parse_logcat_crash", lambda raw: [{"incident_type": "crash"}])
    monkeypatch.setattr(android_perf_executor, "parse_logcat_anr", lambda raw: [{"incident_type": "anr"}])

    incidents, raw = android_perf_executor._collect_incidents("emu-5554")

    assert incidents == [{"incident_type": "crash"}, {"incident_type": "anr"}]
    assert raw == "LOGCAT-RAW"


def test_start_screen_recording_clamps_time_limit(monkeypatch):
    commands = []

    def fake_popen(cmd, stdout=None, stderr=None):
        commands.append(cmd)
        return types.SimpleNamespace(pid=1)

    monkeypatch.setattr(
        android_perf_executor,
        "subprocess",
        types.SimpleNamespace(Popen=fake_popen, DEVNULL=subprocess.DEVNULL, PIPE=subprocess.PIPE),
    )

    process = android_perf_executor._start_screen_recording("emu-5554", "/sdcard/seg.mp4", 99999)
    assert process is not None
    assert commands[-1][3:6] == ["shell", "screenrecord", "--time-limit"]
    assert commands[-1][6] == "1800"  # 上限钳制到 1800 秒

    android_perf_executor._start_screen_recording("emu-5554", "/sdcard/seg.mp4", 0)
    assert commands[-1][6] == "1"  # 下限钳制到 1 秒


def test_start_screen_recording_returns_none_when_popen_fails(monkeypatch):
    def broken_popen(cmd, stdout=None, stderr=None):
        raise OSError("adb missing")

    monkeypatch.setattr(
        android_perf_executor,
        "subprocess",
        types.SimpleNamespace(Popen=broken_popen, DEVNULL=subprocess.DEVNULL, PIPE=subprocess.PIPE),
    )

    assert android_perf_executor._start_screen_recording("emu-5554", "/sdcard/seg.mp4", 30) is None


def test_remove_remote_recording_swallows_errors(monkeypatch):
    calls = []

    def ok_run(cmd, timeout=None):
        calls.append(cmd)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(android_perf_executor, "subprocess", types.SimpleNamespace(run=ok_run))
    asyncio.run(android_perf_executor._remove_remote_recording("emu-5554", "/sdcard/seg.mp4"))
    assert calls == [["adb", "-s", "emu-5554", "shell", "rm", "/sdcard/seg.mp4"]]

    def broken_run(cmd, timeout=None):
        raise OSError("adb missing")

    monkeypatch.setattr(android_perf_executor, "subprocess", types.SimpleNamespace(run=broken_run))
    asyncio.run(android_perf_executor._remove_remote_recording("emu-5554", "/sdcard/seg.mp4"))


# ── _finish_screen_recording ─────────────────────────────────────


def test_finish_screen_recording_discards_segments_without_save(monkeypatch):
    removed = []

    async def fake_remove(serial, path):
        removed.append(path)

    monkeypatch.setattr(android_perf_executor, "_remove_remote_recording", fake_remove)

    process = _RecordingProcess()
    result = asyncio.run(
        android_perf_executor._finish_screen_recording(
            "emu-5554",
            process,
            "/sdcard/cur.mp4",
            9,
            save=False,
            cleanup_paths=["/sdcard/prev.mp4", "/sdcard/cur.mp4"],
        )
    )

    assert result == (None, None)
    assert process.terminated is True
    assert process.waited is True
    assert removed == ["/sdcard/prev.mp4", "/sdcard/cur.mp4"]  # 去重后 cur 只清理一次


def test_finish_screen_recording_kills_process_after_failed_wait(monkeypatch):
    async def fake_remove(serial, path):
        return None

    monkeypatch.setattr(android_perf_executor, "_remove_remote_recording", fake_remove)

    waited_but_killed = _RecordingProcess(fail_wait=True)
    assert asyncio.run(
        android_perf_executor._finish_screen_recording("emu-5554", waited_but_killed, "/sdcard/a.mp4", 1, save=False)
    ) == (None, None)
    assert waited_but_killed.killed is True

    terminated_failed = _RecordingProcess(fail_terminate=True)
    assert asyncio.run(
        android_perf_executor._finish_screen_recording("emu-5554", terminated_failed, "/sdcard/a.mp4", 1, save=False)
    ) == (None, None)
    assert terminated_failed.killed is True

    both_failed = _RecordingProcess(fail_wait=True, fail_kill=True)
    assert asyncio.run(
        android_perf_executor._finish_screen_recording("emu-5554", both_failed, "/sdcard/a.mp4", 1, save=False)
    ) == (None, None)
    assert both_failed.killed is False


def test_finish_screen_recording_uploads_saved_replay(monkeypatch):
    removed = []
    uploaded = []
    local_paths = []

    async def fake_remove(serial, path):
        removed.append(path)

    monkeypatch.setattr(android_perf_executor, "_remove_remote_recording", fake_remove)

    def fake_pull(cmd, capture_output=None, text=None, timeout=None):
        Path(cmd[-1]).write_bytes(b"video-bytes")
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(android_perf_executor, "subprocess", types.SimpleNamespace(run=fake_pull))

    def fake_upload(object_name, local_path, content_type=None):
        uploaded.append((object_name, content_type))
        local_paths.append(local_path)

    monkeypatch.setattr(android_perf_executor, "upload_file", fake_upload)

    result = asyncio.run(
        android_perf_executor._finish_screen_recording(
            "emu-5554",
            _RecordingProcess(),
            "/sdcard/cur.mp4",
            42,
            save=True,
            cleanup_paths=["/sdcard/prev.mp4", "/sdcard/cur.mp4"],
        )
    )

    assert result == ("android-special/runs/42/incident-replay.mp4", len(b"video-bytes"))
    assert uploaded == [("android-special/runs/42/incident-replay.mp4", "video/mp4")]
    assert removed == ["/sdcard/prev.mp4", "/sdcard/cur.mp4"]
    assert local_paths and not local_paths[0].exists()  # finally 已删除本地临时文件


def test_finish_screen_recording_returns_none_when_pull_fails(monkeypatch):
    async def fake_remove(serial, path):
        return None

    monkeypatch.setattr(android_perf_executor, "_remove_remote_recording", fake_remove)
    monkeypatch.setattr(
        android_perf_executor,
        "subprocess",
        types.SimpleNamespace(run=lambda *args, **kwargs: types.SimpleNamespace(returncode=1)),
    )

    assert asyncio.run(
        android_perf_executor._finish_screen_recording("emu-5554", None, "/sdcard/a.mp4", 1, save=True)
    ) == (None, None)


def test_finish_screen_recording_returns_none_when_replay_is_missing(monkeypatch):
    removed = []
    missing = Path(tempfile.gettempdir()) / f"atp-missing-replay-{uuid.uuid4().hex}.mp4"

    async def fake_remove(serial, path):
        removed.append(path)

    monkeypatch.setattr(android_perf_executor, "_remove_remote_recording", fake_remove)
    monkeypatch.setattr(
        android_perf_executor,
        "tempfile",
        types.SimpleNamespace(NamedTemporaryFile=lambda **kwargs: _FakeTempFile(str(missing))),
    )
    monkeypatch.setattr(
        android_perf_executor,
        "subprocess",
        types.SimpleNamespace(run=lambda *args, **kwargs: types.SimpleNamespace(returncode=0)),
    )

    assert asyncio.run(
        android_perf_executor._finish_screen_recording("emu-5554", None, "/sdcard/a.mp4", 1, save=True)
    ) == (None, None)
    assert removed == ["/sdcard/a.mp4"]  # 拉取落空时远端片段仍被清理


def test_finish_screen_recording_returns_none_for_empty_replay(monkeypatch):
    removed = []

    async def fake_remove(serial, path):
        removed.append(path)

    monkeypatch.setattr(android_perf_executor, "_remove_remote_recording", fake_remove)
    # adb pull 返回成功但不落盘：真实 NamedTemporaryFile 保持 0 字节
    monkeypatch.setattr(
        android_perf_executor,
        "subprocess",
        types.SimpleNamespace(run=lambda *args, **kwargs: types.SimpleNamespace(returncode=0)),
    )

    assert asyncio.run(
        android_perf_executor._finish_screen_recording("emu-5554", None, "/sdcard/a.mp4", 1, save=True)
    ) == (None, None)
    assert removed == ["/sdcard/a.mp4"]


def test_finish_screen_recording_swallows_pull_exception(monkeypatch):
    removed = []

    async def fake_remove(serial, path):
        removed.append(path)

    monkeypatch.setattr(android_perf_executor, "_remove_remote_recording", fake_remove)

    def broken_pull(cmd, **kwargs):
        raise OSError("adb crashed")

    monkeypatch.setattr(android_perf_executor, "subprocess", types.SimpleNamespace(run=broken_pull))

    assert asyncio.run(
        android_perf_executor._finish_screen_recording(
            "emu-5554", None, "/sdcard/cur.mp4", 3, save=True, cleanup_paths=["/sdcard/prev.mp4"]
        )
    ) == (None, None)
    assert removed == ["/sdcard/prev.mp4", "/sdcard/cur.mp4"]


def test_finish_screen_recording_swallows_upload_failure(monkeypatch):
    removed = []

    async def fake_remove(serial, path):
        removed.append(path)

    monkeypatch.setattr(android_perf_executor, "_remove_remote_recording", fake_remove)

    def fake_pull(cmd, capture_output=None, text=None, timeout=None):
        Path(cmd[-1]).write_bytes(b"video-bytes")
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(android_perf_executor, "subprocess", types.SimpleNamespace(run=fake_pull))

    def broken_upload(object_name, local_path, content_type=None):
        raise RuntimeError("minio down")

    monkeypatch.setattr(android_perf_executor, "upload_file", broken_upload)

    assert asyncio.run(
        android_perf_executor._finish_screen_recording("emu-5554", None, "/sdcard/a.mp4", 4, save=True)
    ) == (None, None)
    assert removed == ["/sdcard/a.mp4"]


def test_finish_screen_recording_ignores_local_cleanup_failure(monkeypatch):
    removed = []
    written = []

    async def fake_remove(serial, path):
        removed.append(path)

    monkeypatch.setattr(android_perf_executor, "_remove_remote_recording", fake_remove)

    def fake_pull(cmd, **kwargs):
        written.append(Path(cmd[-1]))
        Path(cmd[-1]).write_bytes(b"x")
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(android_perf_executor, "subprocess", types.SimpleNamespace(run=fake_pull))
    monkeypatch.setattr(android_perf_executor, "upload_file", lambda *args, **kwargs: None)

    class _LockedPath:
        """卸载本地临时文件时抛 OSError，模拟文件被占用。"""

        def __init__(self, raw):
            self._path = Path(raw)

        def __str__(self):
            return str(self._path)

        def __fspath__(self):
            return str(self._path)

        def exists(self):
            return self._path.exists()

        def stat(self):
            return self._path.stat()

        def unlink(self, missing_ok=False):
            raise OSError("locked by recording bridge")

    monkeypatch.setattr(android_perf_executor, "Path", _LockedPath)

    result = asyncio.run(
        android_perf_executor._finish_screen_recording("emu-5554", None, "/sdcard/a.mp4", 5, save=True)
    )

    assert result == ("android-special/runs/5/incident-replay.mp4", 1)
    assert removed == ["/sdcard/a.mp4"]
    written[0].unlink(missing_ok=True)  # 测试收尾：删掉被"占用"的临时文件


# ── _sample_once / _compute_summary 剩余分支 ─────────────────────


def test_sample_once_skips_metrics_when_pid_disappears(monkeypatch):
    _patch_adb_shell(monkeypatch, {"cpu": "CPU-RAW"})
    monkeypatch.setattr(android_perf_executor, "parse_cpuinfo", lambda raw, package: None)
    monkeypatch.setattr(android_perf_executor, "parse_meminfo", lambda raw, package: None)
    monkeypatch.setattr(android_perf_executor, "_resolve_pid", lambda serial, package: None)

    assert asyncio.run(android_perf_executor._sample_once("emu-5554", "com.example.app")) == []


def test_sample_once_collects_battery_and_temperature(monkeypatch):
    _patch_adb_shell(monkeypatch, {"battery": "BATT-RAW"})
    monkeypatch.setattr(android_perf_executor, "parse_meminfo", lambda raw, package: None)
    monkeypatch.setattr(android_perf_executor, "_resolve_pid", lambda serial, package: None)
    battery_results = iter(
        [
            {
                "metric_type": "battery_pct",
                "metric_value": 88.0,
                "source": "batterystats",
                "extra": {"temperature_c": 36.5},
            },
            {"metric_type": "battery_pct", "metric_value": 87.0, "source": "batterystats", "extra": {}},
            None,
        ]
    )
    monkeypatch.setattr(android_perf_executor, "parse_batterystats", lambda raw, package: next(battery_results))

    first = asyncio.run(android_perf_executor._sample_once("emu-5554", "com.example.app"))
    assert [sample["metric_type"] for sample in first] == ["battery_pct", "temperature_c"]
    assert first[1]["metric_value"] == 36.5
    assert first[1]["extra"] == {"package": "com.example.app"}

    second = asyncio.run(android_perf_executor._sample_once("emu-5554", "com.example.app"))
    assert [sample["metric_type"] for sample in second] == ["battery_pct"]

    third = asyncio.run(android_perf_executor._sample_once("emu-5554", "com.example.app"))
    assert third == []


def test_sample_once_jank_paths(monkeypatch):
    _patch_adb_shell(monkeypatch, {})
    parse_results = iter(
        [
            None,
            {"metric_type": "fps", "metric_value": 58.0, "source": "gfxinfo", "extra": {"jank_count": "n/a"}},
            {"metric_type": "fps", "metric_value": 59.0, "source": "gfxinfo", "extra": {"jank_count": 4}},
        ]
    )
    monkeypatch.setattr(android_perf_executor, "parse_gfxinfo_framestats", lambda raw, package: next(parse_results))

    empty = asyncio.run(
        android_perf_executor._sample_once("emu-5554", "pkg", collect_performance=False, collect_jank=True)
    )
    assert empty == []  # gfxinfo 无输出

    monkeypatch.setattr(android_perf_executor, "run_adb_shell", lambda serial, cmd, timeout=15: "GFX-RAW")
    unparsed = asyncio.run(
        android_perf_executor._sample_once("emu-5554", "pkg", collect_performance=False, collect_jank=True)
    )
    assert unparsed == []  # 解析失败

    no_jank = asyncio.run(
        android_perf_executor._sample_once("emu-5554", "pkg", collect_performance=False, collect_jank=True)
    )
    assert [sample["metric_type"] for sample in no_jank] == ["fps"]  # jank_count 非数值

    with_jank = asyncio.run(
        android_perf_executor._sample_once("emu-5554", "pkg", collect_performance=False, collect_jank=True)
    )
    assert [sample["metric_type"] for sample in with_jank] == ["fps", "jank_count"]
    assert with_jank[1]["metric_value"] == 4.0


def test_compute_summary_counts_jank_and_skips_typeless():
    samples = [
        {"metric_value": 10.0},  # 无 metric_type → 跳过
        {"metric_type": "jank_count", "metric_value": 2.0},
        {"metric_type": "jank_count", "metric_value": 3.0},
    ]

    summary = android_perf_executor._compute_summary(samples, crash_count=0, anr_count=0)

    assert summary["total_jank_count"] == 5
    assert summary["_sample_counts"] == {"jank_count": 2}


# ── run_mobile_special_perf 主链路剩余分支 ───────────────────────


def test_perf_run_launches_explicit_activity(monkeypatch, chain_events, fast_clock, quiet_heartbeat, device_online):
    launched = []

    def fake_start(serial, package, activity=None):
        launched.append((serial, package, activity))
        return True

    monkeypatch.setattr(android_perf_executor, "_start_app", fake_start)

    async def fake_sample_once(serial, package, **kwargs):
        return [{"metric_type": "cpu_pct", "metric_value": 17.0, "source": "top"}]

    monkeypatch.setattr(android_perf_executor, "_sample_once", fake_sample_once)

    run = _make_run(auto_start=True, launch_activity=" .MainActivity ", duration_seconds=1)

    asyncio.run(android_perf_executor.run_mobile_special_perf(_FakeDB(), run, recorder=_FakeRecorder()))

    assert launched == [("emu-5554", "com.example.app", ".MainActivity")]
    assert run.status is RunStatus.completed
    assert run.summary_json["avg_cpu_pct"] == 17.0


def test_perf_run_rotates_replay_segments(monkeypatch, chain_events, fast_clock, quiet_heartbeat, device_online):
    recordings = iter([_FinishedRecording(), _FinishedRecording(), None])
    monkeypatch.setattr(
        android_perf_executor, "_start_screen_recording", lambda serial, path, seconds: next(recordings)
    )
    monkeypatch.setattr(android_perf_executor, "_clear_logcat_buffer", lambda serial: None)
    monkeypatch.setattr(android_perf_executor, "_collect_incidents", lambda serial: ([], ""))
    removed = []

    async def fake_remove(serial, path):
        removed.append(path)

    monkeypatch.setattr(android_perf_executor, "_remove_remote_recording", fake_remove)
    finished = []

    async def fake_finish(serial, process, remote_path, run_id, *, save, cleanup_paths=None):
        finished.append((process, remote_path, save, list(cleanup_paths or [])))
        return None, None

    monkeypatch.setattr(android_perf_executor, "_finish_screen_recording", fake_finish)

    async def fake_sample_once(serial, package, **kwargs):
        return [{"metric_type": "cpu_pct", "metric_value": 5.0, "source": "top"}]

    monkeypatch.setattr(android_perf_executor, "_sample_once", fake_sample_once)

    run = _make_run(capture_replay=True, duration_seconds=3)
    recorder = _FakeRecorder()

    asyncio.run(android_perf_executor.run_mobile_special_perf(_FakeDB(), run, recorder=recorder))

    rotations = [call for call in recorder.calls if call.get("action") == "rotate_screen_recording"]
    assert [call["parameters"]["segment"] for call in rotations] == [1, 2]
    assert removed == ["/sdcard/atp_mobile_run_1_0.mp4"]  # 只保留上一段 + 当前段
    assert finished == [
        (
            None,
            "/sdcard/atp_mobile_run_1_2.mp4",
            False,
            ["/sdcard/atp_mobile_run_1_1.mp4", "/sdcard/atp_mobile_run_1_2.mp4"],
        )
    ]
    assert run.summary_json["incident_replay"] == {
        "requested": True,
        "saved": False,
        "error": "设备不支持或无法启动异常回放录屏",
    }


def test_perf_run_survives_sampling_exception(monkeypatch, chain_events, fast_clock, quiet_heartbeat, device_online):
    async def broken_sample_once(serial, package, **kwargs):
        raise RuntimeError("adb bridge crashed")

    monkeypatch.setattr(android_perf_executor, "_sample_once", broken_sample_once)

    run = _make_run(duration_seconds=1)

    asyncio.run(android_perf_executor.run_mobile_special_perf(_FakeDB(), run, recorder=_FakeRecorder()))

    assert run.status is RunStatus.failed
    assert run.summary_json["error_message"] == "未采集到有效性能指标"
    assert chain_events[-1]["status"] == "failed"


def test_perf_run_records_incidents_and_uploads_artifacts(
    monkeypatch, chain_events, fast_clock, quiet_heartbeat, device_online
):
    incidents = [
        {
            "incident_type": "crash",
            "title": "崩溃: NullPointer",
            "detail": "d" * 600,
            "process_name": "com.example.app",
        },
        {"incident_type": "anr", "title": None, "detail": None},
    ]
    monkeypatch.setattr(android_perf_executor, "_clear_logcat_buffer", lambda serial: None)
    monkeypatch.setattr(android_perf_executor, "_collect_incidents", lambda serial: (incidents, "LOGCAT-RAW" * 10))
    monkeypatch.setattr(
        android_perf_executor, "_start_screen_recording", lambda serial, path, seconds: _StillRecording()
    )
    saves = []

    async def fake_finish(serial, process, remote_path, run_id, *, save, cleanup_paths=None):
        saves.append(save)
        return f"android-special/runs/{run_id}/incident-replay.mp4", 2048

    monkeypatch.setattr(android_perf_executor, "_finish_screen_recording", fake_finish)

    async def fake_sample_once(serial, package, **kwargs):
        return [{"metric_type": "cpu_pct", "metric_value": 21.0, "source": "top", "sample_time": datetime.now()}]

    monkeypatch.setattr(android_perf_executor, "_sample_once", fake_sample_once)
    uploads = []
    monkeypatch.setattr(
        android_perf_executor,
        "upload_bytes",
        lambda name, content, content_type: uploads.append((name, content_type)),
    )

    db = _FakeDB()
    run = _make_run(collect_incidents=True, capture_replay=True, duration_seconds=1)
    recorder = _FakeRecorder()

    asyncio.run(android_perf_executor.run_mobile_special_perf(db, run, recorder=recorder))

    assert run.status is RunStatus.completed
    assert saves == [True]
    assert run.summary_json["crash_count"] == 1
    assert run.summary_json["anr_count"] == 1
    assert run.summary_json["incident_replay"] == {"requested": True, "saved": True, "error": None}
    assert [name for name, _ in uploads] == [
        "mobile-special/runs/1/metrics.csv",
        "android-special/runs/1/incident.log",
    ]

    incident_payloads = [event for event in chain_events if event.get("type") == "incident"]
    assert [event["incident_type"] for event in incident_payloads] == ["crash", "anr"]
    assert incident_payloads[0]["detail"] == "d" * 500
    assert incident_payloads[1]["title"] == "检测到移动端异常"

    incident_records = [call for call in recorder.calls if call.get("event_type") == "incident"]
    assert len(incident_records) == 2

    artifact_types = [obj.artifact_type for obj in db.added if isinstance(obj, MobileRunArtifact)]
    assert artifact_types == [ArtifactType.csv, ArtifactType.raw_log, ArtifactType.replay]

    incident_rows = [obj for obj in db.added if isinstance(obj, MobileIncident)]
    assert [row.incident_type for row in incident_rows] == ["crash", "anr"]
    assert {row.artifact_path for row in incident_rows} == {"android-special/runs/1/incident-replay.mp4"}

    assert len([obj for obj in db.added if isinstance(obj, MobileMetricSample)]) == 1


def test_perf_run_reports_missing_replay_when_incidents_found(
    monkeypatch, chain_events, fast_clock, quiet_heartbeat, device_online
):
    monkeypatch.setattr(android_perf_executor, "_clear_logcat_buffer", lambda serial: None)
    monkeypatch.setattr(
        android_perf_executor, "_collect_incidents", lambda serial: ([{"incident_type": "crash"}], "LOGCAT-RAW")
    )
    monkeypatch.setattr(
        android_perf_executor, "_start_screen_recording", lambda serial, path, seconds: _StillRecording()
    )
    saves = []

    async def fake_finish(serial, process, remote_path, run_id, *, save, cleanup_paths=None):
        saves.append(save)
        return None, None

    monkeypatch.setattr(android_perf_executor, "_finish_screen_recording", fake_finish)

    async def fake_sample_once(serial, package, **kwargs):
        return []

    monkeypatch.setattr(android_perf_executor, "_sample_once", fake_sample_once)
    monkeypatch.setattr(android_perf_executor, "upload_bytes", lambda *args, **kwargs: None)

    run = _make_run(collect_incidents=True, capture_replay=True, duration_seconds=1)

    asyncio.run(android_perf_executor.run_mobile_special_perf(_FakeDB(), run, recorder=_FakeRecorder()))

    assert saves == [True]
    assert run.status is RunStatus.completed  # 有异常事件时不因无样本判失败
    assert run.summary_json["incident_replay"] == {
        "requested": True,
        "saved": False,
        "error": "检测到异常，但未生成可上传的回放视频",
    }


def test_perf_run_swallows_incident_log_upload_failure(
    monkeypatch, chain_events, fast_clock, quiet_heartbeat, device_online
):
    monkeypatch.setattr(android_perf_executor, "_clear_logcat_buffer", lambda serial: None)
    monkeypatch.setattr(
        android_perf_executor, "_collect_incidents", lambda serial: ([{"incident_type": "crash"}], "LOGCAT-RAW")
    )

    async def fake_sample_once(serial, package, **kwargs):
        return [{"metric_type": "cpu_pct", "metric_value": 1.0, "source": "top"}]

    monkeypatch.setattr(android_perf_executor, "_sample_once", fake_sample_once)
    uploaded = []

    def broken_log_upload(name, content, content_type):
        if content_type.startswith("text/plain"):
            raise RuntimeError("minio down")
        uploaded.append(name)

    monkeypatch.setattr(android_perf_executor, "upload_bytes", broken_log_upload)

    db = _FakeDB()
    run = _make_run(collect_incidents=True, duration_seconds=1)

    asyncio.run(android_perf_executor.run_mobile_special_perf(db, run, recorder=_FakeRecorder()))

    assert run.status is RunStatus.completed
    assert uploaded == ["mobile-special/runs/1/metrics.csv"]
    artifact_types = [obj.artifact_type for obj in db.added if isinstance(obj, MobileRunArtifact)]
    assert artifact_types == [ArtifactType.csv]
    assert chain_events[-1]["status"] == "completed"
