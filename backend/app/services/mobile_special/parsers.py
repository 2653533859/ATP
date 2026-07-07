"""Parsers for ADB command output.

Each parser takes raw stdout from an ADB command and returns a normalized
dictionary or list of dictionaries suitable for storing as metric samples
or incidents.
"""

import re
from datetime import datetime
from typing import Optional

from app.models.mobile_special import MetricType, IncidentType


def parse_meminfo(raw: str, package: str) -> Optional[dict]:
    """Parse `dumpsys meminfo <package>` output.

    Returns:
        Dict with keys: metric_type="mem_mb", metric_value (float, MB), extra (dict)
        Returns None if the output does not contain PSS/TOTAL info.
    """
    if not raw or not package:
        return None

    # Look for "Total PSS: <value> KB" or "TOTAL: <value> KB"
    pss_match = re.search(r"(?:Total PSS|PSS|TOTAL):\s*(\d+)\s*KB", raw, re.IGNORECASE)
    if not pss_match:
        return None

    total_kb = float(pss_match.group(1))
    total_mb = round(total_kb / 1024, 2)

    return {
        "metric_type": MetricType.mem_mb.value,
        "metric_value": total_mb,
        "source": "dumpsys meminfo",
        "extra": {
            "package": package,
            "total_kb": total_kb,
        },
    }


def parse_gfxinfo_framestats(raw: str, package: str) -> Optional[dict]:
    """Parse `dumpsys gfxinfo <package> framestats` output.

    Extracts FPS and jank (frames > 16.7ms) statistics.

    Returns:
        Dict with keys: metric_type="fps", metric_value (float, fps),
                        extra (dict with jank_count, total_frames, etc.)
        Returns None if the output is not valid framestats data.
    """
    if not raw:
        return None

    # Check if this looks like framestats output
    if "Frame" not in raw and "fps" not in raw.lower():
        return None

    # Look for janky frames count
    # Pattern: "Janky frames: 20 (6.25%)" or "Janky Rendering: 15"
    jank_match = re.search(r"Janky.*?:\s*(\d+)", raw, re.IGNORECASE)
    jank_count = int(jank_match.group(1)) if jank_match else 0

    # Total frames
    total_match = re.search(r"Total frames:\s*(\d+)", raw, re.IGNORECASE)
    total_frames = int(total_match.group(1)) if total_match else 0

    # Try to compute average FPS from frame time histogram
    # Pattern: "16.7 ms: 200" meaning 200 frames took 16.7ms each
    fps = 0.0
    frame_times: list[float] = []

    for match in re.finditer(r"(\d+\.?\d*)\s*ms:\s*(\d+)", raw):
        frame_time_ms = float(match.group(1))
        count = int(match.group(2))
        frame_times.extend([frame_time_ms] * count)

    if frame_times:
        avg_frame_time = sum(frame_times) / len(frame_times)
        if avg_frame_time > 0:
            fps = round(1000.0 / avg_frame_time, 2)

    # Fallback: estimate FPS from jank percentage if we have total frames
    if fps == 0 and total_frames > 0 and jank_count > 0:
        good_frames = total_frames - jank_count
        fps = round(good_frames / max(1, total_frames) * 60.0, 2)  # rough estimate

    if fps == 0 and total_frames == 0 and jank_count == 0:
        return None

    return {
        "metric_type": MetricType.fps.value,
        "metric_value": fps,
        "source": "dumpsys gfxinfo framestats",
        "extra": {
            "package": package,
            "jank_count": jank_count,
            "total_frames": total_frames,
        },
    }


def parse_cpuinfo(raw: str, package: str) -> Optional[dict]:
    """Parse `dumpsys cpuinfo <package>` output.

    Returns:
        Dict with keys: metric_type="cpu_pct", metric_value (float, percentage),
                        extra (dict with breakdown)
        Returns None if no CPU info for the package is found.
    """
    if not raw or not package:
        return None

    # Look for percentage: "+5.2% 1234 com.example.app: 52%user + 3%kernel"
    # or "com.example.app: 45%"
    patterns = [
        r"\+\s*(\d+\.?\d*)%\s*\d*\s*" + re.escape(package) + r".*?(\d+)%user.*?(\d+)%kernel",
        r"\+\s*(\d+\.?\d*)%\s*\d*\s*" + re.escape(package),
        re.escape(package) + r":\s*(\d+\.?\d*)%",
    ]

    cpu_pct = None
    for pattern in patterns:
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            cpu_pct = float(match.group(1) if match.lastindex == 1 else match.group(2))
            break

    if cpu_pct is None:
        # Try generic percentage pattern
        generic = re.search(r"(\d+\.?\d*)%", raw)
        if generic:
            cpu_pct = float(generic.group(1))

    if cpu_pct is None or cpu_pct == 0:
        return None

    return {
        "metric_type": MetricType.cpu_pct.value,
        "metric_value": cpu_pct,
        "source": "dumpsys cpuinfo",
        "extra": {"package": package},
    }


def parse_batterystats(raw: str, package: str) -> Optional[dict]:
    """Parse `dumpsys batterystats` output.

    Returns:
        Dict with keys: metric_type="battery_pct", metric_value (0-100),
                        extra (dict with details)
    """
    if not raw:
        return None

    # Look for battery level: "level: 85%" or "Charge: 85%"
    level_match = re.search(r"(?:level|charge|battery):\s*(\d+)(?:\s*%)?", raw, re.IGNORECASE)
    if not level_match:
        return None

    battery_pct = float(level_match.group(1))

    # Temperature if available: "Temperature: 32.0"
    temp_match = re.search(r"Temperature:\s*(\d+\.?\d*)", raw, re.IGNORECASE)
    temperature_c = float(temp_match.group(1)) if temp_match else None

    return {
        "metric_type": MetricType.battery_pct.value,
        "metric_value": battery_pct,
        "source": "dumpsys batterystats",
        "extra": {
            "package": package,
            "temperature_c": temperature_c,
        },
    }


def parse_logcat_crash(raw: str) -> list[dict]:
    """Parse logcat output for crash/FATAL exceptions.

    Returns:
        List of incident dicts with keys:
            incident_type="crash", title, detail, process_name, thread_name, event_time
    """
    if not raw or "FATAL" not in raw.upper() and "EXCEPTION" not in raw.upper():
        return []

    incidents = []
    # Split into individual crash blocks
    blocks = re.split(r"-+\s*(?:beginning of crash|beginning of|fatal log|motion event)", raw, flags=re.IGNORECASE)

    for block in blocks:
        if not block.strip():
            continue

        # Look for process name
        proc_match = re.search(r"Process\s*:\s*([^\s\n]+)", block, re.IGNORECASE)
        process_name = proc_match.group(1) if proc_match else None

        # Look for exception type and message
        exc_match = re.search(
            r"(?:java\.lang\.)?(\w+Exception|\w+Error)(?:\s*:?\s*(.+))?",
            block,
            re.IGNORECASE,
        )
        if not exc_match:
            continue

        exc_type = exc_match.group(1)
        exc_detail = (exc_match.group(2) or "").strip()

        # Stack trace line
        stack_match = re.search(r"at\s+([^\n]+)", block)
        stack_line = stack_match.group(1) if stack_match else None

        title = f"{exc_type}: {exc_detail[:80]}" if exc_detail else exc_type

        incidents.append(
            {
                "incident_type": IncidentType.crash.value,
                "title": title,
                "detail": stack_line or exc_detail,
                "process_name": process_name,
                "thread_name": None,
                "event_time": datetime.now(),
                "extra": {"raw_block": block[:500]},
            }
        )

    return incidents


def parse_logcat_anr(raw: str) -> list[dict]:
    """Parse logcat output for ANR events.

    Returns:
        List of incident dicts with keys:
            incident_type="anr", title, detail, process_name, event_time
    """
    if not raw or "ANR" not in raw.upper():
        return []

    incidents = []
    # Split into ANR blocks
    blocks = re.split(r"ANR\s+in\s+", raw, flags=re.IGNORECASE)

    for block in blocks:
        if not block.strip():
            continue

        # Extract package name (first word)
        pkg_match = re.search(r"([a-zA-Z0-9_.]+)", block)
        process_name = pkg_match.group(1) if pkg_match else None

        # Reason
        reason_match = re.search(r"Reason\s*:\s*([^\n]+)", block, re.IGNORECASE)
        reason = reason_match.group(1).strip() if reason_match else "Input dispatching timed out"

        title = f"ANR in {process_name}" if process_name else "ANR"

        incidents.append(
            {
                "incident_type": IncidentType.anr.value,
                "title": title,
                "detail": reason,
                "process_name": process_name,
                "thread_name": None,
                "event_time": datetime.now(),
                "extra": {"raw_block": block[:500]},
            }
        )

    return incidents


def parse_pid(raw: str) -> Optional[int]:
    """Parse `pidof <package>` output to get process PID.

    Returns:
        Integer PID or None if not found.
    """
    if not raw:
        return None

    raw = raw.strip()
    try:
        return int(raw)
    except ValueError:
        return None
