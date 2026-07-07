"""Tests for android_perf_executor."""

import sys
import types
from pathlib import Path
from datetime import datetime

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules["app.core.minio_client"] = types.SimpleNamespace(
    download_file=lambda *args, **kwargs: None,
    upload_file=lambda *args, **kwargs: None,
    presigned_url=lambda *args, **kwargs: "http://example.com/artifact.csv",
)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(
    publish_run_event=lambda *args, **kwargs: None,
    get_json_cache=lambda *args, **kwargs: None,
    set_json_cache=lambda *args, **kwargs: None,
    delete_json_cache=lambda *args, **kwargs: None,
    delete_json_cache_pattern=lambda *args, **kwargs: None,
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
