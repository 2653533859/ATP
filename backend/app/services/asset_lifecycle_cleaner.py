"""Test Asset Storage Lifecycle and Automated Archive Cleanup Service (Q4.2).

Provides:
1. Multi-category test asset retention policy management (videos, screenshots, reports, traces, logs).
2. Automated scanning of MinIO object storage for expired test artifacts.
3. Reclaimable storage space calculation (MB / GB) and dry-run preview.
4. Safe batch deletion of expired objects and cleanup of dangling database references.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import minio_client
from app.models.case import StepResult
from app.models.mobile_special import MobileIncident, MobileRunArtifact

logger = logging.getLogger(__name__)

# Default retention days per asset category
DEFAULT_ASSET_RETENTION_DAYS: dict[str, int] = {
    "videos": 7,  # Android screen recordings / MP4 video captures
    "screenshots": 14,  # UI step screenshots / failure captures
    "traces": 14,  # Network HAR / mobile trace zip packages
    "reports": 30,  # HTML / PDF / JSON test execution reports
    "logs": 30,  # Device logcat / system execution logs
}

CATEGORY_PREFIX_MAP: dict[str, str] = {
    "videos": "videos/",
    "screenshots": "screenshots/",
    "traces": "traces/",
    "reports": "reports/",
    "logs": "logs/",
}


@dataclass
class ExpiredAssetItem:
    object_name: str
    category: str
    size_bytes: int
    last_modified: datetime
    age_days: float


@dataclass
class CategoryScanResult:
    category: str
    prefix: str
    retention_days: int
    scanned_count: int = 0
    expired_count: int = 0
    reclaimable_bytes: int = 0
    expired_items: list[ExpiredAssetItem] = field(default_factory=list)

    @property
    def reclaimable_mb(self) -> float:
        return round(self.reclaimable_bytes / (1024 * 1024), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "prefix": self.prefix,
            "retention_days": self.retention_days,
            "scanned_count": self.scanned_count,
            "expired_count": self.expired_count,
            "reclaimable_bytes": self.reclaimable_bytes,
            "reclaimable_mb": self.reclaimable_mb,
            "sample_expired_files": [item.object_name for item in self.expired_items[:10]],
        }


def _clean_db_references_sync(session: Session, deleted_object_names: set[str]) -> dict[str, int]:
    """Clean or clear database fields referencing deleted MinIO objects."""
    if not deleted_object_names:
        return {"step_results_cleared": 0, "mobile_incidents_cleared": 0, "mobile_artifacts_cleared": 0}

    # 1. StepResult.screenshot_url
    step_cleared = 0
    screenshot_candidates = [name for name in deleted_object_names if name.startswith("screenshots/")]
    if screenshot_candidates:
        q_step = select(StepResult).where(StepResult.screenshot_url.is_not(None))
        step_rows = session.execute(q_step).scalars().all()
        for step in step_rows:
            if step.screenshot_url and any(cand in step.screenshot_url for cand in screenshot_candidates):
                step.screenshot_url = None
                step_cleared += 1

    # 2. MobileIncident.artifact_path
    incident_cleared = 0
    incident_candidates = [
        name
        for name in deleted_object_names
        if name.startswith("videos/") or name.startswith("traces/") or name.startswith("logs/")
    ]
    if incident_candidates:
        q_inc = select(MobileIncident).where(MobileIncident.artifact_path.is_not(None))
        inc_rows = session.execute(q_inc).scalars().all()
        for inc in inc_rows:
            if inc.artifact_path and any(cand in inc.artifact_path for cand in incident_candidates):
                inc.artifact_path = None
                incident_cleared += 1

    # 3. MobileRunArtifact.file_path
    artifact_cleared = 0
    if incident_candidates:
        q_art = select(MobileRunArtifact).where(MobileRunArtifact.file_path.is_not(None))
        art_rows = session.execute(q_art).scalars().all()
        for art in art_rows:
            if art.file_path and any(cand in art.file_path for cand in incident_candidates):
                session.delete(art)
                artifact_cleared += 1

    session.commit()
    return {
        "step_results_cleared": step_cleared,
        "mobile_incidents_cleared": incident_cleared,
        "mobile_artifacts_cleared": artifact_cleared,
    }


def scan_and_clean_expired_assets(
    session: Session | None = None,
    *,
    dry_run: bool = True,
    custom_retention_days: dict[str, int] | None = None,
    target_categories: list[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Scan MinIO storage objects by asset category and clean expired files based on retention policies.

    Args:
        session: Active synchronous SQLAlchemy DB session (for clearing DB references when dry_run=False).
        dry_run: If True, only preview expired candidates without deleting.
        custom_retention_days: Override retention days per category (e.g. {"videos": 3}).
        target_categories: List of categories to scan (e.g. ["videos", "screenshots"]). Defaults to all.
        now: Reference UTC datetime (defaults to current UTC time).

    Returns:
        Structured scan and cleanup summary.
    """
    ref_time = now or datetime.now(timezone.utc)
    retention_cfg = dict(DEFAULT_ASSET_RETENTION_DAYS)
    if custom_retention_days:
        retention_cfg.update(custom_retention_days)

    categories_to_scan = target_categories or list(CATEGORY_PREFIX_MAP.keys())

    total_scanned = 0
    total_expired = 0
    total_reclaimable_bytes = 0
    category_results: list[CategoryScanResult] = []
    all_expired_object_names: set[str] = set()

    for cat in categories_to_scan:
        prefix = CATEGORY_PREFIX_MAP.get(cat, f"{cat}/")
        retention_days = max(1, retention_cfg.get(cat, 30))
        cutoff_date = ref_time - timedelta(days=retention_days)

        cat_res = CategoryScanResult(category=cat, prefix=prefix, retention_days=retention_days)

        try:
            raw_objects = minio_client.list_objects(prefix=prefix)
        except Exception as exc:
            logger.warning("Failed to list MinIO objects for prefix %s: %s", prefix, exc)
            raw_objects = []

        for obj in raw_objects:
            cat_res.scanned_count += 1
            obj_name = getattr(obj, "object_name", None) or getattr(obj, "name", "")
            size = getattr(obj, "size", 0) or 0
            last_mod = getattr(obj, "last_modified", None)

            if not obj_name or last_mod is None:
                continue

            if last_mod.tzinfo is None:
                last_mod = last_mod.replace(tzinfo=timezone.utc)

            if last_mod < cutoff_date:
                age_days = round((ref_time - last_mod).total_seconds() / 86400.0, 1)
                item = ExpiredAssetItem(
                    object_name=obj_name,
                    category=cat,
                    size_bytes=size,
                    last_modified=last_mod,
                    age_days=age_days,
                )
                cat_res.expired_items.append(item)
                cat_res.expired_count += 1
                cat_res.reclaimable_bytes += size
                all_expired_object_names.add(obj_name)

        total_scanned += cat_res.scanned_count
        total_expired += cat_res.expired_count
        total_reclaimable_bytes += cat_res.reclaimable_bytes
        category_results.append(cat_res)

    deleted_count = 0
    deletion_errors: list[str] = []
    db_cleanup_summary: dict[str, int] = {}

    if not dry_run and all_expired_object_names:
        for obj_name in all_expired_object_names:
            try:
                minio_client.delete_file(obj_name)
                deleted_count += 1
            except Exception as exc:
                deletion_errors.append(f"{obj_name}: {exc}")

        if session is not None:
            try:
                db_cleanup_summary = _clean_db_references_sync(session, all_expired_object_names)
            except Exception as exc:
                logger.warning("Error cleaning database asset references: %s", exc)

    return {
        "dry_run": dry_run,
        "scanned_at": ref_time.isoformat(),
        "total_scanned_count": total_scanned,
        "total_expired_count": total_expired,
        "total_reclaimable_bytes": total_reclaimable_bytes,
        "total_reclaimable_mb": round(total_reclaimable_bytes / (1024 * 1024), 2),
        "total_reclaimable_gb": round(total_reclaimable_bytes / (1024 * 1024 * 1024), 3),
        "deleted_count": deleted_count,
        "deletion_errors_count": len(deletion_errors),
        "db_cleanup_summary": db_cleanup_summary,
        "categories": [c.to_dict() for c in category_results],
    }
