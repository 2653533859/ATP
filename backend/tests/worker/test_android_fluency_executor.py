"""Tests for android_fluency_executor."""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules["app.core.minio_client"] = types.SimpleNamespace(
    download_file=lambda *args, **kwargs: None,
    upload_file=lambda *args, **kwargs: None,
    presigned_url=lambda *args, **kwargs: "http://example.com/artifact.json",
)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(
    publish_run_event=lambda *args, **kwargs: None,
    get_json_cache=lambda *args, **kwargs: None,
    set_json_cache=lambda *args, **kwargs: None,
    delete_json_cache=lambda *args, **kwargs: None,
    delete_json_cache_pattern=lambda *args, **kwargs: None,
)

from app.worker.executors import android_fluency_executor


class TestValidateInputs:
    def test_validate_inputs_requires_package(self):
        errors = android_fluency_executor._validate_inputs(
            device_serial="emulator-5554",
            app_package=None,
            config_json={},
        )
        assert any("package" in e.lower() for e in errors)

    def test_validate_inputs_accepts_valid_inputs(self):
        errors = android_fluency_executor._validate_inputs(
            device_serial="emulator-5554",
            app_package="com.example.app",
            config_json={"stages": [{"name": "launch", "action": "start_app"}]},
        )
        assert errors == []


class TestParseGfxInfo:
    def test_parse_framestats_extracts_fps(self):
        raw = """
        Applications Graphics:
        Frame info frameTime histogram:
        16.7 ms: 200
        33.4 ms: 50
        Total frames: 250
        Janky frames: 10
        """
        result = android_fluency_executor._parse_framestats(raw)
        assert result is not None
        # FPS is stored in metric_value
        assert result["metric_value"] > 0
        assert result["metric_type"] == "fps"

    def test_parse_framestats_returns_none_for_invalid(self):
        assert android_fluency_executor._parse_framestats("") is None
        assert android_fluency_executor._parse_framestats("not framestats") is None


class TestComputeSummary:
    def test_compute_summary_includes_fps_and_jank(self):
        samples = [
            {"metric_type": "fps", "metric_value": 55.0, "extra": {"jank_count": 2}},
            {"metric_type": "fps", "metric_value": 58.0, "extra": {"jank_count": 1}},
            {"metric_type": "fps", "metric_value": 52.0, "extra": {"jank_count": 3}},
        ]
        summary = android_fluency_executor._compute_summary(samples, crash_count=0, anr_count=0)

        assert summary["avg_fps"] == pytest.approx(55.0, rel=0.1)
        assert summary["total_jank_count"] == 6
        assert summary["crash_count"] == 0
