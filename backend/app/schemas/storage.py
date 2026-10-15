from datetime import datetime
from pydantic import BaseModel, Field


class StorageObjectPreviewItem(BaseModel):
    object_name: str
    last_modified: datetime | None = None
    referenced_by_count: int = 0


class StorageReferenceItem(BaseModel):
    reference_type: str
    record_id: int
    field_name: str
    object_name: str
    repairable: bool = False


class StoragePrefixStatItem(BaseModel):
    prefix: str
    object_count: int
    total_bytes: int


class StorageStatsOut(BaseModel):
    bucket: str
    total_object_count: int
    total_bytes: int
    prefixes: list[StoragePrefixStatItem]


class StorageCleanupPreviewIn(BaseModel):
    prefixes: list[str] = Field(
        default_factory=lambda: [
            "screenshots/",
            "reports/",
            "apks/",
            "scripts/",
            "api-files/",
            "web-files/",
            "visual-baselines/",
            "videos/",
            "traces/",
        ]
    )
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    use_active_policies: bool = True


class StorageCleanupPreviewOut(BaseModel):
    prefixes: list[str]
    retention_days: int
    scanned_object_count: int
    expired_object_count: int
    deletable_count: int
    blocked_count: int
    orphan_reference_count: int
    size_evicted_count: int = 0
    deletable_objects: list[StorageObjectPreviewItem]
    blocked_objects: list[StorageObjectPreviewItem]
    orphan_references: list[StorageReferenceItem]


class StorageCleanupExecuteIn(BaseModel):
    object_names: list[str] = Field(default_factory=list)
    prefixes: list[str] | None = Field(default=None, max_length=64)
    repair_orphan_references: bool = False


class StorageCleanupExecuteOut(BaseModel):
    requested_count: int
    deleted_count: int
    skipped_referenced_count: int
    missing_count: int
    repaired_reference_count: int
    deleted_objects: list[str]
    skipped_objects: list[str]
    repaired_references: list[StorageReferenceItem]


# ── Asset Storage Lifecycle (Q4.2) ───────────────────────
class AssetLifecycleScanIn(BaseModel):
    dry_run: bool = True
    categories: list[str] | None = None
    custom_retention_days: dict[str, int] | None = None


class CategoryScanOut(BaseModel):
    category: str
    prefix: str
    retention_days: int
    scanned_count: int
    expired_count: int
    reclaimable_bytes: int
    reclaimable_mb: float
    sample_expired_files: list[str] = Field(default_factory=list)


class AssetLifecycleScanOut(BaseModel):
    dry_run: bool
    scanned_at: str
    total_scanned_count: int
    total_expired_count: int
    total_reclaimable_bytes: int
    total_reclaimable_mb: float
    total_reclaimable_gb: float
    deleted_count: int
    deletion_errors_count: int
    db_cleanup_summary: dict[str, int] = Field(default_factory=dict)
    categories: list[CategoryScanOut]
