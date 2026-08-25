"""Tests for android_fluency_executor."""

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

from app.worker.executors import android_fluency_executor


class TestValidateInputs:
    def test_validate_inputs_requires_package(self):
        errors = android_fluency_executor._validate_inputs(
            device_serial="emulator-5554",
            app_package=None,
            config_json={},
        )
        assert any("package" in e.lower() for e in errors)

    def test_validate_inputs_accepts_valid_inputs(self):
        errors = android_fluency_executor._validate_inputs(
            device_serial="emulator-5554",
            app_package="com.example.app",
            config_json={"stages": [{"name": "launch", "action": "start_app"}]},
        )
        assert errors == []


class TestParseGfxInfo:
    def test_parse_framestats_extracts_fps(self):
        raw = """
        Applications Graphics:
        Frame info frameTime histogram:
        16.7 ms: 200
        33.4 ms: 50
        Total frames: 250
        Janky frames: 10
        """
        result = android_fluency_executor._parse_framestats(raw)
        assert result is not None
        # FPS is stored in metric_value
        assert result["metric_value"] > 0
        assert result["metric_type"] == "fps"

    def test_parse_framestats_returns_none_for_invalid(self):
        assert android_fluency_executor._parse_framestats("") is None
        assert android_fluency_executor._parse_framestats("not framestats") is None


class TestComputeSummary:
    def test_compute_summary_includes_fps_and_jank(self):
        samples = [
            {"metric_type": "fps", "metric_value": 55.0, "extra": {"jank_count": 2}},
            {"metric_type": "fps", "metric_value": 58.0, "extra": {"jank_count": 1}},
            {"metric_type": "fps", "metric_value": 52.0, "extra": {"jank_count": 3}},
        ]
        summary = android_fluency_executor._compute_summary(samples, crash_count=0, anr_count=0)

        assert summary["avg_fps"] == pytest.approx(55.0, rel=0.1)
        assert summary["total_jank_count"] == 6
        assert summary["crash_count"] == 0


# ── run_mobile_special_fluency 主执行链（fake ADB/心跳/时钟边界）──

import asyncio  # noqa: E402

from app.models.bootstrap import load_all_models  # noqa: E402
from app.models.mobile_special import MobileRunEvent, RunStatus  # noqa: E402

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


@pytest.fixture()
def chain_events(monkeypatch):
    recorded = []

    async def publish(run_id, payload):
        recorded.append(payload)

    monkeypatch.setattr(android_fluency_executor, "_safe_publish", publish)
    return recorded


@pytest.fixture()
def reachable(monkeypatch):
    monkeypatch.setattr(
        android_fluency_executor, "_check_device_reachable", lambda serial, timeout=10: (True, "device")
    )


@pytest.fixture()
def fast_sleep(monkeypatch):
    """asyncio 代理：sleep 即返；其余转发真实 asyncio。"""

    async def fake_sleep(_secs):
        return None

    proxy = types.SimpleNamespace(
        sleep=fake_sleep,
        get_event_loop=asyncio.get_event_loop,
        wait_for=asyncio.wait_for,
        subprocess=asyncio.subprocess,
    )
    monkeypatch.setattr(android_fluency_executor, "asyncio", proxy)


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

    monkeypatch.setattr(android_fluency_executor, "HeartbeatMonitor", _HB)
    return _HB


@pytest.fixture()
def quiet_adb(monkeypatch):
    """屏蔽 app 启动 / gfxinfo reset 的真实 subprocess 调用，并记录 swipe/tap。"""
    actions = []
    monkeypatch.setattr(
        android_fluency_executor.subprocess,
        "run",
        lambda cmd, **kw: types.SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(android_fluency_executor, "_reset_gfxinfo", lambda serial, package: None)

    async def swipe(serial, x1, y1, x2, y2, duration_ms=300):
        actions.append(("swipe", x1, y1, x2, y2))
        return True

    async def tap(serial, x, y):
        actions.append(("tap", x, y))
        return True

    monkeypatch.setattr(android_fluency_executor, "_perform_swipe", swipe)
    monkeypatch.setattr(android_fluency_executor, "_perform_tap", tap)
    return actions


def _gfx_stub(monkeypatch, raws):
    """按 stage 顺序返回 gfxinfo 原始输出（None 表示无输出）。"""
    queue = list(raws)
    monkeypatch.setattr(
        android_fluency_executor, "run_adb_shell", lambda serial, cmd, timeout=10: queue.pop(0) if queue else None
    )


_GFX_RAW = """
Applications Graphics:
Frame info frameTime histogram:
16.7 ms: 200
33.4 ms: 50
Total frames: 250
Janky frames: 10
"""


def _run_stub(**config):
    return _Obj(id=41, status=RunStatus.pending, config_snapshot=config, device_serial=None, app_package=None)


def test_fluency_run_fails_on_missing_stages(chain_events):
    run = _run_stub(device_serial="emu-5554", app_package="com.example.app")  # 无 stages

    asyncio.run(android_fluency_executor.run_mobile_special_fluency(_FakeDB(), run))

    assert run.status is RunStatus.failed
    assert "stage" in run.summary_json["error_message"]
    assert chain_events[-1]["status"] == "failed"


def test_fluency_run_fails_when_device_unreachable(monkeypatch, chain_events):
    monkeypatch.setattr(
        android_fluency_executor, "_check_device_reachable", lambda serial, timeout=10: (False, "offline")
    )
    run = _run_stub(device_serial="emu-5554", app_package="com.example.app", stages=[{"name": "s1"}])

    asyncio.run(android_fluency_executor.run_mobile_special_fluency(_FakeDB(), run))

    assert run.status is RunStatus.failed
    assert "设备不可达" in run.summary_json["error_message"]


def test_fluency_run_fails_when_app_start_fails(
    monkeypatch, chain_events, reachable, fast_sleep, quiet_heartbeat, quiet_adb
):
    monkeypatch.setattr(
        android_fluency_executor,
        "launch_android_app",
        lambda *args: (_ for _ in ()).throw(android_fluency_executor.AndroidPreflightError("activity missing")),
    )
    run = _run_stub(device_serial="emu-5554", app_package="com.example.app", stages=[{"name": "s1"}])

    asyncio.run(android_fluency_executor.run_mobile_special_fluency(_FakeDB(), run))

    assert run.status is RunStatus.failed
    assert run.summary_json["error_message"] == "应用启动失败: activity missing"
    assert quiet_adb == []
    assert chain_events[-1]["status"] == "failed"


def test_fluency_run_samples_each_stage(monkeypatch, chain_events, reachable, fast_sleep, quiet_heartbeat, quiet_adb):
    _gfx_stub(monkeypatch, [_GFX_RAW, _GFX_RAW])
    db = _FakeDB()
    run = _run_stub(
        device_serial="emu-5554",
        app_package="com.example.app",
        stages=[
            {"name": "scroll_home", "action": "swipe", "coords": {"x1": 500, "y1": 900, "x2": 500, "y2": 300}},
            {"name": "open_detail", "action": "tap", "coords": {"x": 320, "y": 640}},
        ],
    )

    asyncio.run(android_fluency_executor.run_mobile_special_fluency(db, run))

    assert run.status is RunStatus.completed
    assert quiet_adb == [("swipe", 500, 900, 500, 300), ("tap", 320, 640)]
    domain_objects = [item for item in db.added if not isinstance(item, MobileRunEvent)]
    assert len(domain_objects) == 2
    assert run.summary_json["avg_fps"] is not None
    assert run.summary_json["_fps_sample_count"] == 2
    types_seen = [e["type"] for e in chain_events]
    assert types_seen[0] == "started"
    assert types_seen.count("stage_start") == 2 and types_seen.count("stage_end") == 2
    assert types_seen[-1] == "completed"


def test_fluency_run_skips_duplicate_start_after_preflight(
    monkeypatch, chain_events, reachable, fast_sleep, quiet_heartbeat, quiet_adb
):
    _gfx_stub(monkeypatch, [_GFX_RAW])
    launch_calls = []
    monkeypatch.setattr(
        android_fluency_executor,
        "launch_android_app",
        lambda *args: launch_calls.append(args),
    )
    db = _FakeDB()
    run = _run_stub(
        device_serial="emu-5554",
        app_package="com.example.app",
        auto_start=False,
        stages=[{"name": "home", "action": "swipe"}],
    )

    asyncio.run(android_fluency_executor.run_mobile_special_fluency(db, run))

    assert run.status is RunStatus.completed
    assert launch_calls == []
    app_events = [event for event in db.added if isinstance(event, MobileRunEvent) and event.action == "start_app"]
    assert app_events and app_events[0].result_json["skipped"] is True


def test_fluency_run_skips_empty_gfx_output(
    monkeypatch, chain_events, reachable, fast_sleep, quiet_heartbeat, quiet_adb
):
    _gfx_stub(monkeypatch, [None])
    db = _FakeDB()
    run = _run_stub(device_serial="emu-5554", app_package="com.example.app", stages=[{"name": "s1", "action": "swipe"}])

    asyncio.run(android_fluency_executor.run_mobile_special_fluency(db, run))

    assert run.status is RunStatus.completed
    assert not [item for item in db.added if not isinstance(item, MobileRunEvent)]
    assert run.summary_json["avg_fps"] is None
    assert run.summary_json["_fps_sample_count"] == 0


def test_fluency_run_stops_stages_after_device_lost(
    monkeypatch, chain_events, reachable, fast_sleep, quiet_heartbeat, quiet_adb
):
    class _LostHB(quiet_heartbeat):
        async def __aenter__(self):
            self.lost = True
            if self.on_lost is not None:
                self.on_lost("heartbeat 3 次失败")
            return self

    monkeypatch.setattr(android_fluency_executor, "HeartbeatMonitor", _LostHB)
    _gfx_stub(monkeypatch, [_GFX_RAW])
    run = _run_stub(device_serial="emu-5554", app_package="com.example.app", stages=[{"name": "s1"}, {"name": "s2"}])

    asyncio.run(android_fluency_executor.run_mobile_special_fluency(_FakeDB(), run))

    assert run.status is RunStatus.completed
    assert run.summary_json["device_lost"] is True
    assert quiet_adb == []  # 掉线后一个 stage 都不执行
    types_seen = [e["type"] for e in chain_events]
    assert "stage_start" not in types_seen


def test_fluency_run_survives_stage_exception(
    monkeypatch, chain_events, reachable, fast_sleep, quiet_heartbeat, quiet_adb
):
    async def broken_swipe(*a, **kw):
        raise RuntimeError("input service died")

    monkeypatch.setattr(android_fluency_executor, "_perform_swipe", broken_swipe)
    _gfx_stub(monkeypatch, [])
    run = _run_stub(device_serial="emu-5554", app_package="com.example.app", stages=[{"name": "s1", "action": "swipe"}])

    asyncio.run(android_fluency_executor.run_mobile_special_fluency(_FakeDB(), run))

    assert run.status is RunStatus.failed
    assert run.summary_json["error_message"] == "流畅度执行失败: input service died"
    assert run.summary_json["_fps_sample_count"] == 0
    assert chain_events[-1]["status"] == "failed"


def test_perform_swipe_and_tap_run_adb_input(monkeypatch):
    seen = []

    def fake_run(cmd, **kw):
        seen.append(cmd)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(android_fluency_executor.subprocess, "run", fake_run)

    assert asyncio.run(android_fluency_executor._perform_swipe("emu-5554", 1, 2, 3, 4)) is True
    assert asyncio.run(android_fluency_executor._perform_tap("emu-5554", 5, 6)) is True
    assert seen[0][:5] == ["adb", "-s", "emu-5554", "shell", "input"] and "swipe" in seen[0]
    assert "tap" in seen[1]

    def broken_run(cmd, **kw):
        raise RuntimeError("adb gone")

    monkeypatch.setattr(android_fluency_executor.subprocess, "run", broken_run)
    assert asyncio.run(android_fluency_executor._perform_swipe("emu-5554", 1, 2, 3, 4)) is False
    assert asyncio.run(android_fluency_executor._perform_tap("emu-5554", 5, 6)) is False


def test_reset_gfxinfo_swallows_errors(monkeypatch):
    def broken_run(cmd, **kw):
        raise RuntimeError("adb gone")

    monkeypatch.setattr(android_fluency_executor.subprocess, "run", broken_run)
    android_fluency_executor._reset_gfxinfo("emu-5554", "com.example.app")  # 不应抛异常
