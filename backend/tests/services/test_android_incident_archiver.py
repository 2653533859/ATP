"""Unit tests for P2.3 Android Video Segment Recording and Logcat Incident Alignment.

Tests:
1. parse_logcat_timestamp parsing standard Android logcat timestamps
2. align_incident_logcat slicing within +/- 30s window
3. align_incident_logcat keyword-based fallback slicing
4. slice_video_segment extracting segment using ffmpeg or direct fallback
5. archive_incident_artifacts updating MobileIncident and creating MobileRunArtifacts
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from app.models.bootstrap import load_all_models
from app.models.mobile_special import ArtifactType, IncidentType, MobileIncident, MobileRunArtifact
from app.services.android_incident_archiver import (
    align_incident_logcat,
    archive_incident_artifacts,
    parse_logcat_timestamp,
    slice_video_segment,
)

load_all_models()


class _FakeDB:
    def __init__(self):
        self.added = []
        self.flushed = 0

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushed += 1


def test_parse_logcat_timestamp():
    line = "10-15 19:20:25.123 1000 1000 E AndroidRuntime: FATAL EXCEPTION"
    dt = parse_logcat_timestamp(line, reference_year=2026)
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 10
    assert dt.day == 15
    assert dt.hour == 19
    assert dt.minute == 20
    assert dt.second == 25

    # Non-timestamped line returns None
    assert parse_logcat_timestamp("--------- beginning of main", 2026) is None


def test_align_incident_logcat_window():
    logcat_content = (
        "10-15 19:19:00.000 D Test: early log\n"
        "10-15 19:20:00.000 I App: normal operation\n"
        "10-15 19:20:20.000 W System: warning signal\n"
        "10-15 19:20:25.000 E AndroidRuntime: FATAL EXCEPTION: main\n"
        "    java.lang.NullPointerException: test crash\n"
        "    at com.example.MainActivity.onCreate(MainActivity.java:42)\n"
        "10-15 19:20:45.000 I ActivityManager: Process died\n"
        "10-15 19:22:00.000 D Test: late log\n"
    )

    incident_time = datetime(2026, 10, 15, 19, 20, 25, tzinfo=timezone.utc)
    aligned = align_incident_logcat(logcat_content, incident_time, window_seconds=30)

    # Within [19:19:55, 19:20:55]
    assert "FATAL EXCEPTION: main" in aligned
    assert "java.lang.NullPointerException" in aligned
    assert "Process died" in aligned
    assert "normal operation" in aligned
    # Out of window lines must be excluded
    assert "early log" not in aligned
    assert "late log" not in aligned


def test_align_incident_logcat_keyword_fallback():
    raw_lines = [
        "Generic log line 1",
        "Generic log line 2",
        "FATAL EXCEPTION: Crash happened here",
        "    at com.example.Crash.run(Crash.java:10)",
        "Generic log line 3",
    ]
    raw_text = "\n".join(raw_lines)
    aligned = align_incident_logcat(raw_text, incident_time=None)

    assert "FATAL EXCEPTION: Crash happened here" in aligned
    assert "Crash.java:10" in aligned


def test_slice_video_segment(tmp_path: Path):
    dummy_video = tmp_path / "full_recording.mp4"
    dummy_video.write_bytes(b"dummy-mp4-video-stream-content")

    out_segment = tmp_path / "incident_segment.mp4"
    ok = slice_video_segment(
        dummy_video, out_segment, incident_offset_seconds=45.0, before_seconds=30, after_seconds=30
    )

    assert ok is True
    assert out_segment.is_file()
    assert out_segment.stat().st_size > 0


def test_archive_incident_artifacts(tmp_path: Path):
    db = _FakeDB()
    dummy_video = tmp_path / "recording.mp4"
    dummy_video.write_bytes(b"sample-video-bytes")

    incident = MobileIncident(
        id=77,
        run_id=12,
        incident_type=IncidentType.crash,
        event_time=datetime(2026, 10, 15, 19, 20, 25, tzinfo=timezone.utc),
        title="NullPointerException in MainActivity",
        detail=None,
    )

    logcat_sample = "10-15 19:20:25.000 E AndroidRuntime: FATAL EXCEPTION: main\nCrash stack..."
    start_time = datetime(2026, 10, 15, 19, 20, 0, tzinfo=timezone.utc)

    artifacts = asyncio.run(
        archive_incident_artifacts(
            db,
            run_id=12,
            incident=incident,
            full_logcat=logcat_sample,
            video_path=dummy_video,
            run_start_time=start_time,
        )
    )

    assert "logcat_aligned" in artifacts
    assert "video_segment" in artifacts
    assert incident.artifact_path is not None
    assert "FATAL EXCEPTION" in (incident.detail or "")

    # Check MobileRunArtifacts added
    artifact_types = [a.artifact_type for a in db.added if isinstance(a, MobileRunArtifact)]
    assert ArtifactType.raw_log in artifact_types
    assert ArtifactType.trace in artifact_types
    assert db.flushed >= 1
