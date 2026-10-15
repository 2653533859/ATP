"""Unit tests for T2.3 Playback Step Video Keyframe Alignment and Incident Highlight Reporting.

Tests:
1. align_steps_to_video_timeline calculates relative video offsets and frame numbers
2. align_steps_to_video_timeline generates failure and self-healing keyframe highlight markers
3. compile_playback_timeline_report aggregates execution KPIs and chapters
4. compile_report_for_active_session bridges active DevicePlaybackSession into a structured report
"""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from app.models.bootstrap import load_all_models
from app.services.device_playback_driver import (
    AndroidPlaybackAdapter,
    initialize_playback_session,
)
from app.services.playback_timeline_reporter import (
    _parse_iso_datetime,
    align_steps_to_video_timeline,
    compile_playback_timeline_report,
    compile_report_for_active_session,
)

load_all_models()


def test_parse_iso_datetime():
    dt1 = _parse_iso_datetime("2026-10-16T12:00:00Z")
    assert dt1.year == 2026
    assert dt1.month == 10
    assert dt1.day == 16

    dt2 = _parse_iso_datetime(None)
    assert dt2 is not None


def test_align_steps_to_video_timeline():
    # 3 steps:
    # Step 1: click (normal, passed) 500ms
    # Step 2: input (self_healed, passed) 800ms
    # Step 3: assert_text (failure, failed) 1200ms
    step_records = [
        {
            "step_no": 1,
            "action": "click(btnLogin)",
            "params": {"text": "登录"},
            "status": "passed",
            "duration_ms": 500.0,
            "healed": False,
        },
        {
            "step_no": 2,
            "action": "input(txtUser)",
            "params": {"text": "admin"},
            "status": "passed",
            "duration_ms": 800.0,
            "healed": True,
            "healing_details": "无障碍树模糊评分自愈",
        },
        {
            "step_no": 3,
            "action": "assert_text(welcome)",
            "params": {"expected_text": "欢迎回来"},
            "status": "failed",
            "duration_ms": 1200.0,
            "error_message": "未在页面找到期望文本",
            "healed": False,
        },
    ]

    items, markers = align_steps_to_video_timeline(
        step_records,
        video_start_time="2026-10-16T12:00:00Z",
        video_duration_seconds=60.0,
        fps=30.0,
    )

    assert len(items) == 3
    # Step 1: normal passed
    assert items[0].status == "passed"
    assert items[0].highlight_type == "normal"
    assert items[0].highlight_color == "#52c41a"
    assert items[0].video_start_sec == 0.0
    assert items[0].video_end_sec == 0.5
    assert items[0].keyframe_frame == int(0.5 * 30.0)

    # Step 2: self_healed
    assert items[1].status == "passed"
    assert items[1].highlight_type == "self_healed"
    assert items[1].highlight_color == "#faad14"
    assert "模糊评分自愈" in str(items[1].healing_details)

    # Step 3: failure
    assert items[2].status == "failed"
    assert items[2].highlight_type == "failure"
    assert items[2].highlight_color == "#f5222d"
    assert items[2].is_keyframe is True
    assert "未在页面找到期望文本" in str(items[2].error_message)

    # Check seek markers
    types = [m["type"] for m in markers]
    assert "failure" in types
    assert "self_healed" in types


def test_compile_playback_timeline_report():
    step_records = [
        {"step_no": 1, "action": "click", "status": "passed", "duration_ms": 300.0},
        {"step_no": 2, "action": "swipe", "status": "passed", "duration_ms": 600.0},
        {"step_no": 3, "action": "assert_text", "status": "failed", "duration_ms": 1000.0, "error_message": "失败"},
    ]

    report = compile_playback_timeline_report(
        session_id="play_report_01",
        platform="android",
        step_records=step_records,
        video_url="http://minio/videos/run_101.mp4",
        video_duration_seconds=30.0,
        fps=30.0,
    )

    assert report["session_id"] == "play_report_01"
    assert report["platform"] == "android"
    assert report["video_summary"]["video_url"] == "http://minio/videos/run_101.mp4"
    assert report["video_summary"]["total_frames"] == 900
    assert report["execution_summary"]["total_steps"] == 3
    assert report["execution_summary"]["passed_steps"] == 2
    assert report["execution_summary"]["failed_steps"] == 1
    assert report["execution_summary"]["overall_status"] == "failed"
    assert len(report["timeline"]) == 3


@pytest.mark.asyncio
async def test_compile_report_for_active_session():
    mock_u2 = MagicMock()
    adapter = AndroidPlaybackAdapter("emulator-5554", "com.app", mock_driver=mock_u2)
    session = await initialize_playback_session(
        "android",
        device_id=1,
        serial_or_udid="emulator-5554",
        target_app="com.app",
        custom_adapter=adapter,
        session_id="play_sess_report_test",
    )

    await session.execute_step({"action": "click", "params": {"text": "首页"}}, step_no=1)
    await session.execute_step({"action": "wait", "params": {"seconds": 0.1}}, step_no=2)

    report = compile_report_for_active_session(
        "play_sess_report_test",
        video_url="http://minio/videos/test.mp4",
        video_duration_seconds=15.0,
    )

    assert report is not None
    assert report["session_id"] == "play_sess_report_test"
    assert report["execution_summary"]["total_steps"] == 2
    assert report["execution_summary"]["passed_steps"] == 2
    assert report["execution_summary"]["overall_status"] == "passed"
