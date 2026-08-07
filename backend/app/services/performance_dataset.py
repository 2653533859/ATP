"""Dataset binding helpers for deterministic k6 parameterization."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc, select

from app.models.dataset import TestDataset, TestDatasetVersion


class PerformanceDatasetBindingError(ValueError):
    """Raised when a performance test references an invalid dataset."""


async def resolve_dataset_binding(db: Any, dataset_id: int | None, project_id: int) -> tuple[int, int | None] | None:
    """Validate project ownership and return the latest immutable dataset version."""
    if dataset_id is None:
        return None
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise PerformanceDatasetBindingError("性能压测数据集不存在")
    if dataset.project_id != project_id:
        raise PerformanceDatasetBindingError("性能压测数据集不属于当前项目")
    result = await db.execute(
        select(TestDatasetVersion.version)
        .where(TestDatasetVersion.dataset_id == dataset_id)
        .order_by(desc(TestDatasetVersion.version))
        .limit(1)
    )
    version = result.scalar_one_or_none()
    return dataset_id, int(version) if version is not None else None


async def load_dataset_rows(db: Any, dataset_id: int | None, dataset_version: int | None) -> list[dict[str, Any]]:
    """Load the run's pinned dataset version, falling back to the current dataset for legacy rows."""
    if dataset_id is None:
        return []
    if dataset_version is not None:
        result = await db.execute(
            select(TestDatasetVersion)
            .where(
                TestDatasetVersion.dataset_id == dataset_id,
                TestDatasetVersion.version == dataset_version,
            )
            .limit(1)
        )
        version = result.scalar_one_or_none()
        if version is not None:
            return [row for row in (version.rows or []) if isinstance(row, dict)]
    dataset = await db.get(TestDataset, dataset_id)
    return [row for row in (getattr(dataset, "rows", None) or []) if isinstance(row, dict)] if dataset else []


def serialize_dataset_rows(rows: list[dict[str, Any]]) -> str:
    """Serialize rows for the worker-only environment variable consumed by generated k6 scripts."""
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
