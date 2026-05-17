"""Tests for android_stability_executor."""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules["app.core.minio_client"] = types.SimpleNamespace(
    download_file=lambda *args, **kwargs: None,
    upload_file=lambda *args, **kwargs: None,
    presigned_url=lambda *args, **kwargs: "http://example.com/artifact.json",
)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(
    publish_run_event=lambda *args, **kwargs: None,
    get_json_cache=lambda *args, **kwargs: None,
    set_json_cache=lambda *args, **kwargs: None,
    delete_json_cache=lambda *args, **kwargs: None,
    delete_json_cache_pattern=lambda *args, **kwargs: None,
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
