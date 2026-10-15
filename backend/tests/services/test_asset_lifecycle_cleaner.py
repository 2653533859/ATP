"""Unit tests for Q4.2 Test Asset Storage Lifecycle and Automated Archive Cleanup.

Tests:
1. Category retention defaults match PRD and domain rules
2. scan_and_clean_expired_assets dry-run calculates expired items and reclaimable space
3. scan_and_clean_expired_assets executes file deletion and cleans database references
4. scan_and_clean_expired_assets honors custom category retention overrides
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.models.bootstrap import load_all_models
from app.models.case import StepResult
from app.models.mobile_special import MobileIncident, MobileRunArtifact
from app.services.asset_lifecycle_cleaner import (
    DEFAULT_ASSET_RETENTION_DAYS,
    scan_and_clean_expired_assets,
)

load_all_models()


def test_category_retention_defaults():
    assert DEFAULT_ASSET_RETENTION_DAYS["videos"] == 7
    assert DEFAULT_ASSET_RETENTION_DAYS["screenshots"] == 14
    assert DEFAULT_ASSET_RETENTION_DAYS["traces"] == 14
    assert DEFAULT_ASSET_RETENTION_DAYS["reports"] == 30
    assert DEFAULT_ASSET_RETENTION_DAYS["logs"] == 30


def test_scan_and_clean_expired_assets_dry_run():
    now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)

    # Mock MinIO objects
    # 1. Video: 10 days old (> 7d default) -> Expired
    obj_video_old = SimpleNamespace(
        object_name="videos/run_100_screen.mp4",
        size=10 * 1024 * 1024,  # 10 MB
        last_modified=now - timedelta(days=10),
    )
    # 2. Video: 3 days old (< 7d default) -> Valid
    obj_video_new = SimpleNamespace(
        object_name="videos/run_101_screen.mp4",
        size=8 * 1024 * 1024,  # 8 MB
        last_modified=now - timedelta(days=3),
    )
    # 3. Screenshot: 20 days old (> 14d default) -> Expired
    obj_screen_old = SimpleNamespace(
        object_name="screenshots/step_200.png",
        size=500 * 1024,  # 500 KB
        last_modified=now - timedelta(days=20),
    )
    # 4. Screenshot: 5 days old (< 14d default) -> Valid
    obj_screen_new = SimpleNamespace(
        object_name="screenshots/step_201.png",
        size=400 * 1024,  # 400 KB
        last_modified=now - timedelta(days=5),
    )

    def mock_list_objects(prefix=""):
        if prefix.startswith("videos"):
            return [obj_video_old, obj_video_new]
        elif prefix.startswith("screenshots"):
            return [obj_screen_old, obj_screen_new]
        return []

    with patch("app.core.minio_client.list_objects", side_effect=mock_list_objects):
        report = scan_and_clean_expired_assets(
            session=None,
            dry_run=True,
            target_categories=["videos", "screenshots"],
            now=now,
        )

        assert report["dry_run"] is True
        assert report["total_scanned_count"] == 4
        assert report["total_expired_count"] == 2
        assert report["deleted_count"] == 0  # Dry run doesn't delete

        # Reclaimable bytes: 10MB + 500KB
        expected_bytes = 10 * 1024 * 1024 + 500 * 1024
        assert report["total_reclaimable_bytes"] == expected_bytes
        assert report["total_reclaimable_mb"] > 10.0

        cats = {c["category"]: c for c in report["categories"]}
        assert cats["videos"]["expired_count"] == 1
        assert "videos/run_100_screen.mp4" in cats["videos"]["sample_expired_files"]
        assert cats["screenshots"]["expired_count"] == 1
        assert "screenshots/step_200.png" in cats["screenshots"]["sample_expired_files"]


def test_scan_and_clean_expired_assets_execute():
    now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)

    obj_expired_screenshot = SimpleNamespace(
        object_name="screenshots/failed_step_99.png",
        size=200 * 1024,
        last_modified=now - timedelta(days=25),
    )
    obj_expired_video = SimpleNamespace(
        object_name="videos/incident_99.mp4",
        size=15 * 1024 * 1024,
        last_modified=now - timedelta(days=12),
    )

    def mock_list(prefix=""):
        if prefix.startswith("screenshots"):
            return [obj_expired_screenshot]
        elif prefix.startswith("videos"):
            return [obj_expired_video]
        return []

    step = StepResult(id=1, run_id=1, step_index=0, screenshot_url="http://minio/screenshots/failed_step_99.png")
    incident = MobileIncident(id=2, artifact_path="videos/incident_99.mp4")
    artifact = MobileRunArtifact(id=3, file_path="videos/incident_99.mp4")

    class _MockSession:
        def __init__(self):
            self.committed = False
            self.deleted = []

        def delete(self, obj):
            self.deleted.append(obj)

        def execute(self, stmt):
            sql = str(stmt).lower()
            if "from step_results" in sql:
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [step]))
            if "from mobile_incidents" in sql:
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [incident]))
            if "from mobile_run_artifacts" in sql:
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [artifact]))
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

        def commit(self):
            self.committed = True

    deleted_files: list[str] = []

    def mock_delete(obj_name: str):
        deleted_files.append(obj_name)

    mock_session: Any = _MockSession()

    with (
        patch("app.core.minio_client.list_objects", side_effect=mock_list),
        patch("app.core.minio_client.delete_file", side_effect=mock_delete),
    ):
        report = scan_and_clean_expired_assets(
            session=mock_session,
            dry_run=False,
            target_categories=["screenshots", "videos"],
            now=now,
        )

        assert report["dry_run"] is False
        assert report["deleted_count"] == 2
        assert "screenshots/failed_step_99.png" in deleted_files
        assert "videos/incident_99.mp4" in deleted_files

        # Verify DB references cleared
        assert step.screenshot_url is None
        assert incident.artifact_path is None
        assert artifact in mock_session.deleted
        assert mock_session.committed is True
        assert report["db_cleanup_summary"]["step_results_cleared"] == 1
        assert report["db_cleanup_summary"]["mobile_incidents_cleared"] == 1
        assert report["db_cleanup_summary"]["mobile_artifacts_cleared"] == 1


def test_scan_and_clean_custom_retention_override():
    now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)

    # Video is 5 days old (would be kept under default 7d, but expired under custom 3d)
    obj_video = SimpleNamespace(
        object_name="videos/fast_expire.mp4",
        size=1024,
        last_modified=now - timedelta(days=5),
    )

    with patch("app.core.minio_client.list_objects", return_value=[obj_video]):
        # 1. Default retention: not expired
        res_default = scan_and_clean_expired_assets(
            dry_run=True,
            target_categories=["videos"],
            now=now,
        )
        assert res_default["total_expired_count"] == 0

        # 2. Custom retention 3 days: expired!
        res_custom = scan_and_clean_expired_assets(
            dry_run=True,
            target_categories=["videos"],
            custom_retention_days={"videos": 3},
            now=now,
        )
        assert res_custom["total_expired_count"] == 1
