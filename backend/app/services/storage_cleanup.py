from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import minio_client
from app.core.config import settings
from app.core.object_refs import extract_object_name
from app.models.apk import Apk
from app.models.case import StepResult, TestCase
from app.models.mobile_special import MobileIncident, MobileRunArtifact
from app.models.performance import PerformanceRun, PerformanceTest
from app.models.storage_policy import StoragePolicy
from app.models.suite import TestSuite
from app.schemas.storage import (
    StorageCleanupExecuteOut,
    StorageCleanupPreviewOut,
    StorageObjectPreviewItem,
    StoragePrefixStatItem,
    StorageReferenceItem,
    StorageStatsOut,
)

logger = logging.getLogger(__name__)

DEFAULT_CLEANUP_PREFIXES = ("screenshots/", "reports/", "apks/", "scripts/", "performance/")


@dataclass
class PolicyEntry:
    prefix: str
    retention_days: int
    max_size_gb: float | None = None


def load_active_policies(session: Session) -> list[PolicyEntry]:
    rows = session.execute(
        select(
            StoragePolicy.prefix,
            StoragePolicy.retention_days,
            StoragePolicy.max_size_gb,
        ).where(StoragePolicy.enabled.is_(True))
    ).all()
    entries: list[PolicyEntry] = []
    for prefix, retention, max_size_gb in rows:
        normalized = (prefix or "").strip().lstrip("/")
        if not normalized:
            continue
        if not normalized.endswith("/"):
            normalized = f"{normalized}/"
        entries.append(
            PolicyEntry(
                prefix=normalized,
                retention_days=int(retention),
                max_size_gb=float(max_size_gb) if max_size_gb is not None else None,
            )
        )
    return entries


@dataclass
class ObjectReference:
    reference_type: str
    record_id: int
    field_name: str
    object_name: str
    repairable: bool

    def to_schema(self) -> StorageReferenceItem:
        return StorageReferenceItem(
            reference_type=self.reference_type,
            record_id=self.record_id,
            field_name=self.field_name,
            object_name=self.object_name,
            repairable=self.repairable,
        )


def _normalize_prefixes(prefixes: Iterable[str] | None) -> list[str]:
    values = prefixes or DEFAULT_CLEANUP_PREFIXES
    normalized: list[str] = []
    for value in values:
        prefix = (value or "").strip().lstrip("/")
        if not prefix:
            continue
        if not prefix.endswith("/"):
            prefix = f"{prefix}/"
        if prefix not in normalized:
            normalized.append(prefix)
    return normalized or list(DEFAULT_CLEANUP_PREFIXES)


def _cutoff(retention_days: int | None) -> datetime:
    days = retention_days or settings.FILE_RETENTION_DAYS
    return datetime.now(timezone.utc) - timedelta(days=days)


def _iter_case_script_references(session: Session) -> list[ObjectReference]:
    rows = session.execute(select(TestCase.id, TestCase.config)).all()
    references: list[ObjectReference] = []
    for case_id, config in rows:
        object_name = extract_object_name((config or {}).get("script_path"))
        if object_name:
            references.append(
                ObjectReference(
                    reference_type="test_case",
                    record_id=case_id,
                    field_name="config.script_path",
                    object_name=object_name,
                    repairable=True,
                )
            )
        apk_object_name = extract_object_name((config or {}).get("apk_object_name"))
        if apk_object_name:
            references.append(
                ObjectReference(
                    reference_type="test_case",
                    record_id=case_id,
                    field_name="config.apk_object_name",
                    object_name=apk_object_name,
                    repairable=True,
                )
            )
    return references


def _iter_suite_parameterization_references(session: Session) -> list[ObjectReference]:
    rows = session.execute(select(TestSuite.id, TestSuite.parameterization)).all()
    references: list[ObjectReference] = []
    for suite_id, parameterization in rows:
        object_name = extract_object_name((parameterization or {}).get("object_name"))
        if object_name:
            references.append(
                ObjectReference(
                    reference_type="test_suite",
                    record_id=suite_id,
                    field_name="parameterization.object_name",
                    object_name=object_name,
                    repairable=True,
                )
            )
    return references


def _iter_performance_references(session: Session) -> list[ObjectReference]:
    references: list[ObjectReference] = []
    test_rows = session.execute(select(PerformanceTest.id, PerformanceTest.script_object_name)).all()
    for record_id, value in test_rows:
        object_name = extract_object_name(value)
        if object_name:
            references.append(
                ObjectReference(
                    reference_type="performance_test",
                    record_id=record_id,
                    field_name="script_object_name",
                    object_name=object_name,
                    repairable=False,
                )
            )

    run_rows = session.execute(select(PerformanceRun.id, PerformanceRun.raw_result_object_name)).all()
    for record_id, value in run_rows:
        object_name = extract_object_name(value)
        if object_name:
            references.append(
                ObjectReference(
                    reference_type="performance_run",
                    record_id=record_id,
                    field_name="raw_result_object_name",
                    object_name=object_name,
                    repairable=True,
                )
            )
    return references


def collect_db_references(session: Session) -> list[ObjectReference]:
    references: list[ObjectReference] = []

    apk_rows = session.execute(select(Apk.id, Apk.object_name)).all()
    for record_id, value in apk_rows:
        object_name = extract_object_name(value)
        if object_name:
            references.append(
                ObjectReference(
                    reference_type="apk",
                    record_id=record_id,
                    field_name="object_name",
                    object_name=object_name,
                    repairable=False,
                )
            )

    screenshot_rows = session.execute(select(StepResult.id, StepResult.screenshot_url)).all()
    for record_id, value in screenshot_rows:
        object_name = extract_object_name(value)
        if object_name:
            references.append(
                ObjectReference(
                    reference_type="step_result",
                    record_id=record_id,
                    field_name="screenshot_url",
                    object_name=object_name,
                    repairable=True,
                )
            )

    references.extend(_iter_case_script_references(session))
    references.extend(_iter_suite_parameterization_references(session))
    references.extend(_iter_performance_references(session))

    incident_rows = session.execute(select(MobileIncident.id, MobileIncident.artifact_path)).all()
    for record_id, value in incident_rows:
        object_name = extract_object_name(value)
        if object_name:
            references.append(
                ObjectReference(
                    reference_type="mobile_incident",
                    record_id=record_id,
                    field_name="artifact_path",
                    object_name=object_name,
                    repairable=True,
                )
            )

    artifact_rows = session.execute(select(MobileRunArtifact.id, MobileRunArtifact.file_path)).all()
    for record_id, value in artifact_rows:
        object_name = extract_object_name(value)
        if object_name:
            references.append(
                ObjectReference(
                    reference_type="mobile_run_artifact",
                    record_id=record_id,
                    field_name="file_path",
                    object_name=object_name,
                    repairable=True,
                )
            )

    return references


def get_storage_stats(
    _session: Session,
    *,
    prefixes: Iterable[str] | None = None,
) -> StorageStatsOut:
    normalized_prefixes = _normalize_prefixes(prefixes)
    prefix_stats: list[StoragePrefixStatItem] = []
    total_object_count = 0
    total_bytes = 0

    for prefix in normalized_prefixes:
        objects = minio_client.list_objects(prefix=prefix)
        object_count = len(objects)
        prefix_bytes = sum(getattr(obj, "size", 0) or 0 for obj in objects)
        total_object_count += object_count
        total_bytes += prefix_bytes
        prefix_stats.append(
            StoragePrefixStatItem(
                prefix=prefix,
                object_count=object_count,
                total_bytes=prefix_bytes,
            )
        )

    return StorageStatsOut(
        bucket=settings.MINIO_BUCKET,
        total_object_count=total_object_count,
        total_bytes=total_bytes,
        prefixes=prefix_stats,
    )


def preview_storage_cleanup(
    session: Session,
    *,
    prefixes: Iterable[str] | None = None,
    retention_days: int | None = None,
    policies: Iterable[PolicyEntry] | None = None,
) -> StorageCleanupPreviewOut:
    """生成清理预览。

    支持两种调用模式：
    - 旧模式：传 ``prefixes`` + ``retention_days``，所有 prefix 用同一 retention 阈值
    - 新模式：传 ``policies``（每个 prefix 独立 retention，且可设 ``max_size_gb`` 总量上限）

    新模式下 size 淘汰策略：单 prefix 内对象按 last_modified 升序累加 size，
    超出 ``max_size_gb`` 的最旧若干个会被加入淘汰集合（与 retention 取并集）。
    """
    policy_list = list(policies) if policies is not None else None

    if policy_list:
        normalized_prefixes = [entry.prefix for entry in policy_list]
        retention_by_prefix: dict[str, int] = {
            entry.prefix: entry.retention_days for entry in policy_list
        }
        max_size_by_prefix: dict[str, float | None] = {
            entry.prefix: entry.max_size_gb for entry in policy_list
        }
        effective_retention_days = max(retention_by_prefix.values()) if retention_by_prefix else (
            retention_days or settings.FILE_RETENTION_DAYS
        )
    else:
        normalized_prefixes = _normalize_prefixes(prefixes)
        effective_retention_days = retention_days or settings.FILE_RETENTION_DAYS
        retention_by_prefix = {p: effective_retention_days for p in normalized_prefixes}
        max_size_by_prefix = {p: None for p in normalized_prefixes}

    objects_by_name: dict[str, datetime | None] = {}
    objects_by_prefix: dict[str, list[tuple[str, datetime | None, int]]] = {}
    scanned_object_count = 0
    for prefix in normalized_prefixes:
        bucket: list[tuple[str, datetime | None, int]] = []
        for obj in minio_client.list_objects(prefix=prefix):
            scanned_object_count += 1
            last_modified = getattr(obj, "last_modified", None)
            size = int(getattr(obj, "size", 0) or 0)
            objects_by_name[obj.object_name] = last_modified
            bucket.append((obj.object_name, last_modified, size))
        objects_by_prefix[prefix] = bucket

    references = collect_db_references(session)
    refs_by_object: dict[str, list[ObjectReference]] = {}
    for ref in references:
        refs_by_object.setdefault(ref.object_name, []).append(ref)

    expired_names: set[str] = set()
    size_evicted_names: set[str] = set()
    for prefix, bucket in objects_by_prefix.items():
        prefix_retention = retention_by_prefix.get(prefix, effective_retention_days)
        cutoff = _cutoff(prefix_retention)
        for object_name, last_modified, _size in bucket:
            if last_modified is None or last_modified < cutoff:
                expired_names.add(object_name)

        max_gb = max_size_by_prefix.get(prefix)
        if max_gb and max_gb > 0:
            size_evicted_names.update(_select_size_eviction(bucket, int(max_gb * (1024 ** 3))))

    candidate_names = expired_names | size_evicted_names

    deletable_objects: list[StorageObjectPreviewItem] = []
    blocked_objects: list[StorageObjectPreviewItem] = []
    for object_name in candidate_names:
        item = StorageObjectPreviewItem(
            object_name=object_name,
            last_modified=objects_by_name.get(object_name),
            referenced_by_count=len(refs_by_object.get(object_name, [])),
        )
        if item.referenced_by_count:
            blocked_objects.append(item)
        else:
            deletable_objects.append(item)

    orphan_references = [
        ref.to_schema()
        for ref in references
        if ref.object_name not in objects_by_name
    ]

    return StorageCleanupPreviewOut(
        prefixes=normalized_prefixes,
        retention_days=effective_retention_days,
        scanned_object_count=scanned_object_count,
        expired_object_count=len(expired_names),
        deletable_count=len(deletable_objects),
        blocked_count=len(blocked_objects),
        orphan_reference_count=len(orphan_references),
        size_evicted_count=len(size_evicted_names),
        deletable_objects=sorted(deletable_objects, key=lambda item: item.object_name),
        blocked_objects=sorted(blocked_objects, key=lambda item: item.object_name),
        orphan_references=orphan_references,
    )


def _select_size_eviction(
    objects: list[tuple[str, datetime | None, int]],
    max_size_bytes: int,
) -> set[str]:
    """对单 prefix 内对象按 last_modified 升序，累计删除最旧的直到总量 ≤ max_size_bytes。"""
    if max_size_bytes <= 0 or not objects:
        return set()

    total = sum(size for _name, _ts, size in objects)
    if total <= max_size_bytes:
        return set()

    # 没有 last_modified 的视为最旧
    sorted_objs = sorted(
        objects,
        key=lambda x: x[1] or datetime.min.replace(tzinfo=timezone.utc),
    )
    evicted: set[str] = set()
    for name, _ts, size in sorted_objs:
        if total <= max_size_bytes:
            break
        evicted.add(name)
        total -= size
    return evicted


def _repair_reference(session: Session, ref: ObjectReference) -> bool:
    if ref.reference_type == "step_result":
        row = session.get(StepResult, ref.record_id)
        if not row:
            return False
        row.screenshot_url = None
        return True
    if ref.reference_type == "test_case":
        row = session.get(TestCase, ref.record_id)
        if not row:
            return False
        config = dict(row.config or {})
        if ref.field_name == "config.script_path":
            config.pop("script_path", None)
        elif ref.field_name == "config.apk_object_name":
            config.pop("apk_object_name", None)
        else:
            return False
        row.config = config
        return True
    if ref.reference_type == "test_suite":
        row = session.get(TestSuite, ref.record_id)
        if not row:
            return False
        parameterization = dict(row.parameterization or {})
        parameterization.pop("object_name", None)
        row.parameterization = parameterization
        return True
    if ref.reference_type == "mobile_incident":
        row = session.get(MobileIncident, ref.record_id)
        if not row:
            return False
        row.artifact_path = None
        return True
    if ref.reference_type == "mobile_run_artifact":
        row = session.get(MobileRunArtifact, ref.record_id)
        if not row:
            return False
        row.file_path = ""
        return True
    if ref.reference_type == "performance_run":
        row = session.get(PerformanceRun, ref.record_id)
        if not row:
            return False
        row.raw_result_object_name = None
        return True
    return False


def execute_storage_cleanup(
    session: Session,
    *,
    object_names: Iterable[str],
    repair_orphan_references: bool = False,
) -> StorageCleanupExecuteOut:
    normalized_object_names = []
    for value in object_names:
        object_name = extract_object_name(value)
        if object_name and object_name not in normalized_object_names:
            normalized_object_names.append(object_name)

    references = collect_db_references(session)
    refs_by_object: dict[str, list[ObjectReference]] = {}
    for ref in references:
        refs_by_object.setdefault(ref.object_name, []).append(ref)

    existing_objects = {
        obj.object_name
        for prefix in DEFAULT_CLEANUP_PREFIXES
        for obj in minio_client.list_objects(prefix=prefix)
    }

    deleted_objects: list[str] = []
    skipped_objects: list[str] = []
    missing_count = 0
    skipped_referenced_count = 0
    for object_name in normalized_object_names:
        if object_name not in existing_objects:
            missing_count += 1
            continue
        if refs_by_object.get(object_name):
            skipped_objects.append(object_name)
            skipped_referenced_count += 1
            continue
        try:
            minio_client.delete_file(object_name)
            deleted_objects.append(object_name)
        except Exception:
            logger.exception("Failed to delete object during storage cleanup: %s", object_name)
            skipped_objects.append(object_name)

    repaired_references: list[StorageReferenceItem] = []
    if repair_orphan_references:
        for ref in references:
            if ref.object_name in existing_objects or not ref.repairable:
                continue
            if _repair_reference(session, ref):
                repaired_references.append(ref.to_schema())

    session.commit()

    return StorageCleanupExecuteOut(
        requested_count=len(normalized_object_names),
        deleted_count=len(deleted_objects),
        skipped_referenced_count=skipped_referenced_count,
        missing_count=missing_count,
        repaired_reference_count=len(repaired_references),
        deleted_objects=deleted_objects,
        skipped_objects=skipped_objects,
        repaired_references=repaired_references,
    )
