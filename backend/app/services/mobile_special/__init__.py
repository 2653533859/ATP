"""Mobile Special Testing Services.

This module provides ADB-based collectors, parsers, and aggregators for
Android performance, stability, and fluency testing.
"""

from app.services.mobile_special.adb_client import (
    run_adb_shell,
    build_meminfo_cmd,
    build_gfxinfo_cmd,
    build_cpuinfo_cmd,
    build_batterystats_cmd,
    build_logcat_cmd,
    build_pidof_cmd,
    build_proc_status_cmd,
)
from app.services.mobile_special.parsers import (
    parse_meminfo,
    parse_proc_status_memory,
    parse_gfxinfo_framestats,
    parse_cpuinfo,
    parse_batterystats,
    parse_logcat_crash,
    parse_logcat_anr,
    parse_pid,
)
from app.services.mobile_special.aggregator import (
    aggregate_samples,
    compute_run_summary,
)

__all__ = [
    # adb_client
    "run_adb_shell",
    "build_meminfo_cmd",
    "build_gfxinfo_cmd",
    "build_cpuinfo_cmd",
    "build_batterystats_cmd",
    "build_logcat_cmd",
    "build_pidof_cmd",
    "build_proc_status_cmd",
    # parsers
    "parse_meminfo",
    "parse_proc_status_memory",
    "parse_gfxinfo_framestats",
    "parse_cpuinfo",
    "parse_batterystats",
    "parse_logcat_crash",
    "parse_logcat_anr",
    "parse_pid",
    # aggregator
    "aggregate_samples",
    "compute_run_summary",
]
