"""Tests for mobile_special collectors."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.mobile_special.adb_client import (
    build_meminfo_cmd,
    build_gfxinfo_cmd,
    build_cpuinfo_cmd,
    build_batterystats_cmd,
    build_logcat_cmd,
    build_pidof_cmd,
    run_adb_shell,
)


class TestAdbClientCommands:
    def test_build_meminfo_cmd(self):
        cmd = build_meminfo_cmd("emulator-5554", "com.example.app")
        assert "dumpsys" in cmd
        assert "meminfo" in cmd
        assert "com.example.app" in cmd

    def test_build_gfxinfo_cmd(self):
        cmd = build_gfxinfo_cmd("emulator-5554", "com.example.app")
        assert "dumpsys" in cmd
        assert "gfxinfo" in cmd
        assert "framestats" in cmd
        assert "com.example.app" in cmd

    def test_build_cpuinfo_cmd(self):
        cmd = build_cpuinfo_cmd("emulator-5554", "com.example.app")
        assert "dumpsys" in cmd
        assert "cpuinfo" in cmd
        assert "com.example.app" in cmd

    def test_build_batterystats_cmd(self):
        cmd = build_batterystats_cmd("emulator-5554", "com.example.app")
        assert "dumpsys" in cmd
        assert "batterystats" in cmd

    def test_build_logcat_cmd_with_crash_filter(self):
        cmd = build_logcat_cmd("emulator-5554", filter_crash=True)
        assert "logcat" in cmd

    def test_build_logcat_cmd_with_anr_filter(self):
        cmd = build_logcat_cmd("emulator-5554", filter_anr=True)
        assert "logcat" in cmd

    def test_build_pidof_cmd(self):
        cmd = build_pidof_cmd("emulator-5554", "com.example.app")
        assert "pidof" in cmd
        assert "com.example.app" in cmd

    def test_run_adb_shell_returns_none_on_error(self, monkeypatch):
        # Mock subprocess.run to simulate ADB failure
        import subprocess

        def fake_run(*args, **kwargs):
            result = type("obj", (object,), {"returncode": 1, "stderr": "error", "stdout": ""})()
            return result

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = run_adb_shell("emulator-5554", ["shell", "echo", "test"])
        assert result is None
