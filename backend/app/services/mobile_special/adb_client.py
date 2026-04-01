"""ADB command wrappers for mobile special testing.

Provides building blocks for:
  - Sampling: dumpsys meminfo, cpuinfo, gfxinfo, batterystats
  - Process: pidof to get app PID
  - Logs: logcat for crash and ANR detection
"""
import logging
import subprocess
from typing import Sequence

logger = logging.getLogger(__name__)


def run_adb_shell(
    serial: str,
    args: Sequence[str],
    timeout: int = 30,
) -> str | None:
    """Execute an ADB shell command on the specified device.

    Args:
        serial: Device serial number (e.g. "emulator-5554")
        args: Command arguments after "adb -s <serial> shell"
        timeout: Command timeout in seconds

    Returns:
        stdout text on success, None on failure
    """
    cmd = ["adb", "-s", serial, "shell", *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            logger.warning(
                "ADB command failed (%s): %s",
                proc.returncode,
                (proc.stderr or "").strip(),
            )
            return None
        return proc.stdout.strip()
    except FileNotFoundError:
        logger.warning("adb not found, is ADB installed?")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("ADB command timed out: %s", " ".join(cmd))
        return None
    except Exception as e:
        logger.error("ADB command error: %s", e)
        return None


# ---- Command builders ----

def build_meminfo_cmd(serial: str, package: str) -> list[str]:
    """Build command to get memory info for a package."""
    return ["dumpsys", "meminfo", package]


def build_gfxinfo_cmd(serial: str, package: str) -> list[str]:
    """Build command to get graphics info (FPS/jank) for a package."""
    return ["dumpsys", "gfxinfo", package, "framestats"]


def build_cpuinfo_cmd(serial: str, package: str) -> list[str]:
    """Build command to get CPU usage for a package."""
    return ["dumpsys", "cpuinfo", package]


def build_batterystats_cmd(serial: str, package: str) -> list[str]:
    """Build command to get battery stats reset and collect."""
    return ["dumpsys", "batterystats", "--reset"]


def build_logcat_cmd(
    serial: str,
    filter_crash: bool = False,
    filter_anr: bool = False,
    buffer: str = "main",
) -> list[str]:
    """Build logcat command with crash or ANR filter.

    Args:
        serial: Device serial
        filter_crash: Show only FATAL logs
        filter_anr: Show only ANR logs
        buffer: Log buffer (main, system, crash)
    """
    cmd = ["logcat", "-d", "-b", buffer]
    if filter_crash:
        cmd.extend(["--pid", str(0)])  # Will be set dynamically
        cmd.extend(["-s", "FATAL"])  # Only FATAL level
    elif filter_anr:
        cmd.extend(["-s", "ANR"])
    return cmd


def build_pidof_cmd(serial: str, package: str) -> list[str]:
    """Build command to get PID of a package."""
    return ["pidof", package]


def build_package_info_cmd(serial: str, package: str, activity: str) -> list[str]:
    """Build command to get package activity info."""
    return ["dumpsys", "package", package, "|", "grep", activity]


def build_top_cmd(serial: str, package: str, lines: int = 10) -> list[str]:
    """Build command to get top CPU consumers for a package."""
    return ["top", "-n", str(lines), "-b", "-p", package]


def is_device_online(serial: str) -> bool:
    """Check if a device is online and responsive."""
    output = run_adb_shell(serial, ["echo", "ok"], timeout=5)
    return output == "ok"
