"""Tests for mobile_special parsers."""
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.mobile_special.parsers import (
    parse_meminfo,
    parse_gfxinfo_framestats,
    parse_cpuinfo,
    parse_batterystats,
    parse_logcat_crash,
    parse_logcat_anr,
    parse_pid,
)


class TestParseMeminfo:
    def test_parse_meminfo_returns_memory_mb(self):
        raw = """
        Applications Memory Usage (in Kilobytes):
        Uptime: 12345678ms
        Total PSS: 256000 KB
        """
        result = parse_meminfo(raw, "com.example.app")
        assert result is not None
        assert result["metric_type"] == "mem_mb"
        assert result["metric_value"] == 250.0  # 256000 KB / 1024 = 250 MB

    def test_parse_meminfo_returns_none_for_empty_output(self):
        assert parse_meminfo("", "com.example.app") is None
        assert parse_meminfo("not relevant", "com.example.app") is None

    def test_parse_meminfo_uses_total_pss_when_available(self):
        raw = """
        Total PSS: 512000 KB
        """
        result = parse_meminfo(raw, "com.example.app")
        assert result["metric_value"] == 500.0


class TestParseGfxInfo:
    def test_parse_gfxinfo_framestats_extracts_fps_and_jank(self):
        # Simulated gfxinfo framestats output with jank frames
        raw = """Graphics info:
        Frame info frameTime histogram:
        1.5 ms: 100
        16.7 ms: 200
        50.0 ms: 15   <-- jank (>16.7ms)
        100.0 ms: 5   <-- severe jank

        Total frames: 320
        Janky frames: 20 (6.25%)
        """
        result = parse_gfxinfo_framestats(raw, "com.example.app")
        assert result is not None
        assert result["metric_type"] == "fps"
        # FPS = 1000 / avg_frame_time_ms
        assert result["metric_value"] > 0
        assert "jank_count" in result["extra"]
        assert result["extra"]["jank_count"] == 20

    def test_parse_gfxinfo_returns_none_for_invalid_input(self):
        assert parse_gfxinfo_framestats("", "com.example.app") is None
        assert parse_gfxinfo_framestats("no data here", "com.example.app") is None


class TestParseCpuinfo:
    def test_parse_cpuinfo_returns_percentage(self):
        # dumpsys cpuinfo for a process
        raw = """CPU usage from 0ms to 1000ms later:
        1000ms:
          +5.2% 1234 com.example.app: 52%user + 3%kernel / 4%iowait
        """
        result = parse_cpuinfo(raw, "com.example.app")
        assert result is not None
        assert result["metric_type"] == "cpu_pct"
        assert result["metric_value"] > 0

    def test_parse_cpuinfo_returns_none_for_no_match(self):
        assert parse_cpuinfo("", "com.example.app") is None
        assert parse_cpuinfo("no process info", "com.example.app") is None


class TestParseLogcatCrash:
    def test_parse_crash_from_fatal_log(self):
        raw = """
        --------- beginning of crash
        FATAL EXCEPTION: main
        Process: com.example.app
        java.lang.NullPointerException
            at com.example.MainActivity.onCreate(MainActivity.java:123)
        """
        incidents = parse_logcat_crash(raw)
        assert len(incidents) > 0
        assert incidents[0]["incident_type"] == "crash"
        assert "NullPointerException" in incidents[0]["title"]
        assert incidents[0]["process_name"] == "com.example.app"

    def test_parse_crash_returns_empty_for_no_crash(self):
        assert parse_logcat_crash("") == []
        assert parse_logcat_crash("normal log message") == []

    def test_parse_anr_from_logcat(self):
        raw = """
        ANR in com.example.app
        Reason: Input dispatching timed out
        Load: 8.2 / 6.1 / 5.5
        """
        incidents = parse_logcat_anr(raw)
        assert len(incidents) > 0
        assert incidents[0]["incident_type"] == "anr"
        assert incidents[0]["title"] == "ANR in com.example.app"


class TestParsePid:
    def test_parse_pid_returns_integer(self):
        raw = "12345"
        assert parse_pid(raw) == 12345

    def test_parse_pid_returns_none_for_invalid(self):
        assert parse_pid("") is None
        assert parse_pid("not a number") is None
