"""Playback Step Video Keyframe Alignment and Incident Highlight Reporting Service (T2.3).

Provides:
1. High-precision alignment of device execution steps with MP4 screen recording timestamps.
2. Failure and self-healing keyframe detection and timeline marker compilation.
3. Interactive video chapter timeline generation (start/end seconds, seek markers, frame numbers).
4. Comprehensive playback diagnostic report generation for visual verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any
import uuid

from app.services.device_playback_driver import get_playback_session

logger = logging.getLogger(__name__)

DEFAULT_FPS = 30.0


@dataclass
class AlignedStepTimelineItem:
    step_no: int
    action: str
    params: dict[str, Any]
    status: str
    duration_ms: float
    video_start_sec: float
    video_end_sec: float
    keyframe_frame: int
    is_keyframe: bool
    highlight_type: str  # "normal" | "self_healed" | "failure"
    highlight_color: str
    error_message: str | None = None
    screenshot_url: str | None = None
    healing_details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_no": self.step_no,
            "action": self.action,
            "params": self.params,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "video_start_sec": round(self.video_start_sec, 2),
            "video_end_sec": round(self.video_end_sec, 2),
            "keyframe_frame": self.keyframe_frame,
            "is_keyframe": self.is_keyframe,
            "highlight_type": self.highlight_type,
            "highlight_color": self.highlight_color,
            "error_message": self.error_message,
            "screenshot_url": self.screenshot_url,
            "healing_details": self.healing_details,
        }


def _parse_iso_datetime(dt_str: str | None) -> datetime:
    """Parse ISO datetime string into UTC datetime object."""
    if not dt_str:
        return datetime.now(timezone.utc)
    try:
        # Replace trailing 'Z' if present
        clean_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def align_steps_to_video_timeline(
    step_records: list[dict[str, Any]],
    *,
    video_start_time: str | datetime | None = None,
    video_duration_seconds: float = 60.0,
    fps: float = DEFAULT_FPS,
) -> tuple[list[AlignedStepTimelineItem], list[dict[str, Any]]]:
    """Align individual execution step timestamps with the MP4 video recording track.

    Returns:
        (aligned_timeline_items, seek_markers)
    """
    v_start_dt = (
        _parse_iso_datetime(video_start_time)
        if isinstance(video_start_time, str)
        else (video_start_time or datetime.now(timezone.utc))
    )

    timeline_items: list[AlignedStepTimelineItem] = []
    seek_markers: list[dict[str, Any]] = []

    current_simulated_offset = 0.0

    for step in step_records:
        step_no = int(step.get("step_no", 1))
        action = str(step.get("action", "unknown"))
        params = step.get("params") or {}
        status = str(step.get("status", "passed"))
        duration_ms = float(step.get("duration_ms", 500.0))
        error_msg = step.get("error_message")
        healed = bool(step.get("healed", False))
        healing_details = step.get("healing_details")
        screenshot_url = step.get("screenshot_url")

        # Determine step start offset
        started_at_str = step.get("started_at")
        if started_at_str:
            step_start_dt = _parse_iso_datetime(started_at_str)
            offset_sec = max(0.0, (step_start_dt - v_start_dt).total_seconds())
        else:
            offset_sec = current_simulated_offset

        duration_sec = duration_ms / 1000.0
        end_sec = min(video_duration_seconds, offset_sec + duration_sec)
        keyframe_frame = int(end_sec * fps)

        # Highlight type
        if status in {"failed", "error"}:
            h_type = "failure"
            h_color = "#f5222d"
            is_keyframe = True
        elif healed:
            h_type = "self_healed"
            h_color = "#faad14"
            is_keyframe = True
        else:
            h_type = "normal"
            h_color = "#52c41a"
            is_keyframe = action in {"click", "input", "assert_text"}

        item = AlignedStepTimelineItem(
            step_no=step_no,
            action=action,
            params=params,
            status=status,
            duration_ms=duration_ms,
            video_start_sec=offset_sec,
            video_end_sec=end_sec,
            keyframe_frame=keyframe_frame,
            is_keyframe=is_keyframe,
            highlight_type=h_type,
            highlight_color=h_color,
            error_message=error_msg,
            screenshot_url=screenshot_url,
            healing_details=healing_details,
        )
        timeline_items.append(item)

        # Seek marker for video player scrubbing
        if is_keyframe or status in {"failed", "error"}:
            seek_markers.append(
                {
                    "seek_sec": round(offset_sec, 2),
                    "step_no": step_no,
                    "label": f"Step {step_no}: {action}",
                    "type": h_type,
                    "color": h_color,
                    "error_message": error_msg,
                }
            )

        current_simulated_offset = end_sec + 0.1

    return timeline_items, seek_markers


def compile_playback_timeline_report(
    session_id: str,
    platform: str,
    step_records: list[dict[str, Any]],
    *,
    video_url: str = "",
    video_start_time: str | datetime | None = None,
    video_duration_seconds: float = 60.0,
    fps: float = DEFAULT_FPS,
) -> dict[str, Any]:
    """Compile the interactive playback timeline and keyframe diagnostic report."""
    timeline_items, seek_markers = align_steps_to_video_timeline(
        step_records,
        video_start_time=video_start_time,
        video_duration_seconds=video_duration_seconds,
        fps=fps,
    )

    total = len(step_records)
    passed = sum(1 for s in step_records if s.get("status") == "passed")
    failed = sum(1 for s in step_records if s.get("status") in {"failed", "error"})
    healed = sum(1 for s in step_records if s.get("healed", False))
    success_rate = round((passed / total * 100.0), 2) if total else 100.0

    report_id = f"rpt_pb_{session_id}_{uuid.uuid4().hex[:8]}"

    return {
        "report_id": report_id,
        "session_id": session_id,
        "platform": platform,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "video_summary": {
            "video_url": video_url,
            "duration_seconds": video_duration_seconds,
            "fps": fps,
            "total_frames": int(video_duration_seconds * fps),
        },
        "execution_summary": {
            "total_steps": total,
            "passed_steps": passed,
            "failed_steps": failed,
            "healed_steps": healed,
            "success_rate": success_rate,
            "overall_status": "passed" if failed == 0 else "failed",
        },
        "timeline": [item.to_dict() for item in timeline_items],
        "seek_markers": seek_markers,
    }


def compile_report_for_active_session(
    session_id: str,
    *,
    video_url: str = "",
    video_duration_seconds: float = 60.0,
) -> dict[str, Any] | None:
    """Compile playback timeline report for an in-memory active playback session."""
    session = get_playback_session(session_id)
    if not session:
        return None

    step_dicts = [s.to_dict() for s in session.step_records]
    return compile_playback_timeline_report(
        session_id=session.session_id,
        platform=session.platform,
        step_records=step_dicts,
        video_url=video_url,
        video_start_time=session.started_at,
        video_duration_seconds=video_duration_seconds,
    )
