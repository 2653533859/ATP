"""Android incident evidence archiving and timeline alignment service (P2.3).

Provides:
- align_incident_logcat: Slices logcat entries around an incident timestamp (+/- 30s)
- slice_video_segment: Extracts an MP4 video clip around the incident timestamp using ffmpeg (or safe fallback)
- archive_incident_evidence: Persists aligned logcat and video segment artifacts for Crash/ANR incidents
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import minio_client
from app.core.minio_client import upload_bytes, upload_file
from app.models.mobile_special import ArtifactType, MobileIncident, MobileRunArtifact

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# Standard Android logcat time format: "MM-DD HH:MM:SS.mmm"
_LOGCAT_TIME_RE = re.compile(r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d{3})?)")
DEFAULT_INCIDENT_WINDOW_SECONDS = 30


def parse_logcat_timestamp(line: str, reference_year: int) -> datetime | None:
    """Parse timestamp from a logcat '-v time' line."""
    m = _LOGCAT_TIME_RE.match(line.strip())
    if not m:
        return None
    raw_ts = m.group(1).split(".")[0]  # "MM-DD HH:MM:SS"
    try:
        dt = datetime.strptime(f"{reference_year}-{raw_ts}", "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def align_incident_logcat(
    full_logcat: str,
    incident_time: datetime | None,
    window_seconds: int = DEFAULT_INCIDENT_WINDOW_SECONDS,
) -> str:
    """Extract logcat slice bounded by [incident_time - window, incident_time + window].

    If timestamps cannot be parsed, extracts context around FATAL EXCEPTION / ANR keywords.
    """
    if not full_logcat:
        return ""

    lines = full_logcat.splitlines()
    if not lines:
        return ""

    if incident_time is None:
        incident_time = datetime.now(timezone.utc)
    elif incident_time.tzinfo is None:
        incident_time = incident_time.replace(tzinfo=timezone.utc)

    ref_year = incident_time.year
    start_window = incident_time - timedelta(seconds=window_seconds)
    end_window = incident_time + timedelta(seconds=window_seconds)

    aligned_lines: list[str] = []
    has_timestamps = False

    for line in lines:
        ts = parse_logcat_timestamp(line, ref_year)
        if ts is not None:
            has_timestamps = True
            if start_window <= ts <= end_window:
                aligned_lines.append(line)
        elif has_timestamps and aligned_lines:
            # Include multi-line stack trace lines following a matched timestamp
            aligned_lines.append(line)

    if aligned_lines:
        return "\n".join(aligned_lines)

    # Fallback keyword slicing if logcat lines lack standard timestamps
    keyword_indices = [
        idx
        for idx, line in enumerate(lines)
        if any(kw in line for kw in ("FATAL EXCEPTION", "ANR in", "CRASH:", "Backtrace:", "Signal 11"))
    ]

    if not keyword_indices:
        return "\n".join(lines[-100:])  # Return tail lines as fallback

    first_kw = keyword_indices[0]
    slice_start = max(0, first_kw - 50)
    slice_end = min(len(lines), first_kw + 100)
    return "\n".join(lines[slice_start:slice_end])


def slice_video_segment(
    input_video_path: str | Path,
    output_segment_path: str | Path,
    incident_offset_seconds: float,
    before_seconds: int = DEFAULT_INCIDENT_WINDOW_SECONDS,
    after_seconds: int = DEFAULT_INCIDENT_WINDOW_SECONDS,
) -> bool:
    """Extract an MP4 video clip around incident_offset_seconds using ffmpeg."""
    in_path = Path(input_video_path)
    out_path = Path(output_segment_path)

    if not in_path.is_file():
        logger.warning("Video file not found: %s", in_path)
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = shutil.which("ffmpeg")

    start_sec = max(0.0, incident_offset_seconds - before_seconds)
    duration_sec = before_seconds + after_seconds

    if ffmpeg_bin:
        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss",
            f"{start_sec:.2f}",
            "-i",
            str(in_path),
            "-t",
            f"{duration_sec:.2f}",
            "-c",
            "copy",
            str(out_path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=30)
            if res.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
                logger.info("Sliced video segment to %s (start=%s, duration=%s)", out_path, start_sec, duration_sec)
                return True
        except Exception as exc:
            logger.warning("ffmpeg slicing failed: %s; falling back to direct copy", exc)

    # Fallback when ffmpeg is not installed or stream copy fails
    try:
        shutil.copy2(in_path, out_path)
        return True
    except Exception as exc:
        logger.error("Failed to copy fallback video segment: %s", exc)
        return False


async def archive_incident_artifacts(
    db: Any,
    run_id: int,
    incident: MobileIncident,
    full_logcat: str,
    video_path: str | Path | None = None,
    run_start_time: datetime | None = None,
) -> dict[str, str]:
    """Align logcat and video artifacts for an incident and link them to the database."""
    incident_time = _ensure_utc(incident.event_time or datetime.now(timezone.utc))
    aligned_log = align_incident_logcat(full_logcat, incident_time)

    artifacts: dict[str, str] = {}
    uploaded_objs: list[str] = []
    incident_key = incident.id or "new"
    prefix = f"runs/{run_id}/incidents/{incident_key}"

    try:
        with tempfile.TemporaryDirectory(prefix=f"atp_incident_{run_id}_") as tmp_dir_str:
            artifact_dir = Path(tmp_dir_str)

            # 1. Save aligned logcat snippet and upload to object storage
            logcat_filename = f"incident_{incident.incident_type.value}_logcat.txt"
            logcat_bytes = aligned_log.encode("utf-8", errors="replace")
            logcat_obj_name = await asyncio.to_thread(
                upload_bytes,
                f"{prefix}/{logcat_filename}",
                logcat_bytes,
                content_type="text/plain; charset=utf-8",
            )
            uploaded_objs.append(logcat_obj_name)
            artifacts["logcat_aligned"] = logcat_obj_name
            db.add(
                MobileRunArtifact(
                    run_id=run_id,
                    artifact_type=ArtifactType.raw_log,
                    file_path=logcat_obj_name,
                    file_name=logcat_filename,
                    file_size=len(logcat_bytes),
                )
            )

            # 2. Slice and upload video segment
            video_obj_name: str | None = None
            video_size = 0
            video_filename = f"incident_{incident.incident_type.value}_segment.mp4"
            if video_path and Path(video_path).is_file():
                offset = 0.0
                if run_start_time:
                    delta = (incident_time - _ensure_utc(run_start_time)).total_seconds()
                    offset = max(0.0, delta)

                video_segment_file = artifact_dir / video_filename
                sliced = await asyncio.to_thread(slice_video_segment, video_path, video_segment_file, offset)
                if sliced and video_segment_file.is_file():
                    video_size = video_segment_file.stat().st_size
                    video_obj_name = await asyncio.to_thread(
                        upload_file,
                        f"{prefix}/{video_filename}",
                        video_segment_file,
                        content_type="video/mp4",
                    )
                    uploaded_objs.append(video_obj_name)
                    artifacts["video_segment"] = video_obj_name
                    incident.artifact_path = video_obj_name

            # 3. Update incident detail with aligned stack trace
            if not incident.detail and aligned_log:
                incident.detail = aligned_log[:2000]

            if video_obj_name is not None:
                db.add(
                    MobileRunArtifact(
                        run_id=run_id,
                        artifact_type=ArtifactType.trace,
                        file_path=video_obj_name,
                        file_name=video_filename,
                        file_size=video_size,
                    )
                )

            await db.flush()
    except Exception:
        delete_fn = getattr(minio_client, "delete_file", None)
        if callable(delete_fn):
            for obj_name in uploaded_objs:
                try:
                    await asyncio.to_thread(delete_fn, obj_name)
                except Exception:
                    logger.debug("Failed to cleanup orphan incident artifact %s", obj_name, exc_info=True)
        raise
    return artifacts
