"""Tests for mobile_special parsers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.mobile_special.parsers import (
    parse_batterystats,
    parse_cpuinfo,
    parse_gfxinfo_framestats,
    parse_logcat_anr,
    parse_logcat_crash,
    parse_meminfo,
    parse_proc_status_memory,
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

    def test_parse_android14_tabular_meminfo_without_kb_suffix(self):
        raw = """
                         Pss  Private  Private
                TOTAL   105485    10424     8712
                   TOTAL PSS:   105485            TOTAL RSS:   130044
        """
        result = parse_meminfo(raw, "com.example.app")
        assert result is not None
        assert result["metric_value"] == 103.01  # 105485 KB / 1024

    def test_parse_meminfo_normalizes_thousands_separator(self):
        raw = """
                         Pss  Private  Private
                TOTAL    33,398     30,000     8,712
        """
        result = parse_meminfo(raw, "com.example.app")
        assert result is not None
        assert result["metric_value"] == 32.62
        assert result["extra"]["total_kb"] == 33398.0

    def test_parse_proc_status_memory_uses_rss_fallback(self):
        raw = "Name:\tm.nebula.karing\nVmRSS:\t413860 kB\nVmHWM:\t909468 kB\n"
        result = parse_proc_status_memory(raw, "com.nebula.karing")
        assert result is not None
        assert result["metric_type"] == "mem_mb"
        assert result["metric_value"] == 404.16
        assert result["source"] == "/proc/status VmRSS"
        assert result["extra"]["fallback"] is True


class TestParseGfxInfo:
    def test_parse_gfxinfo_framestats_extracts_fps_and_jank(self):
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
        assert result["metric_value"] > 0
        assert "jank_count" in result["extra"]
        assert result["extra"]["jank_count"] == 20

    def test_parse_gfxinfo_returns_none_for_invalid_input(self):
        assert parse_gfxinfo_framestats("", "com.example.app") is None
        assert parse_gfxinfo_framestats("no data here", "com.example.app") is None

    def test_parse_android14_gfxinfo_histogram_with_equals(self):
        raw = """Applications Graphics Acceleration Info:
        Total frames rendered: 5
        Janky frames: 1 (20.00%)
        HISTOGRAM: 5ms=1 6ms=1 7ms=1 18ms=1 32ms=1
        GPU HISTOGRAM: 1ms=100 2ms=100
        """
        result = parse_gfxinfo_framestats(raw, "com.nebula.karing")
        assert result is not None
        assert result["metric_type"] == "fps"
        assert result["metric_value"] == 73.53
        assert result["extra"]["jank_count"] == 1


class TestParseCpuinfo:
    def test_parse_cpuinfo_returns_percentage(self):
        raw = """CPU usage from 0ms to 1000ms later:
        1000ms:
          +5.2% 1234 com.example.app: 52%user + 3%kernel / 4%iowait
        """
        result = parse_cpuinfo(raw, "com.example.app")
        assert result is not None
        assert result["metric_type"] == "cpu_pct"
        assert result["metric_value"] == 5.2

    def test_parse_cpuinfo_keeps_zero_percent_process_sample(self):
        raw = "  0% 11994/com.example.app: 0% user + 0% kernel"
        result = parse_cpuinfo(raw, "com.example.app")
        assert result is not None
        assert result["metric_value"] == 0.0

    def test_parse_cpuinfo_returns_none_for_no_match(self):
        assert parse_cpuinfo("", "com.example.app") is None
        assert parse_cpuinfo("no process info", "com.example.app") is None


class TestParseBattery:
    def test_parse_dumpsys_battery_output(self):
        raw = "status: 2\nlevel: 95\ntemperature: 324\n"
        result = parse_batterystats(raw, "com.example.app")
        assert result is not None
        assert result["metric_value"] == 95.0
        assert result["extra"]["temperature_c"] == 32.4

    def test_parse_battery_accepts_percent_and_celsius(self):
        raw = "Charge: 85%\nTemperature: 32.0\n"
        result = parse_batterystats(raw, "com.example.app")
        assert result is not None
        assert result["metric_value"] == 85.0
        assert result["extra"]["temperature_c"] == 32.0


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
