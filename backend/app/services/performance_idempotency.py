"""Idempotency helpers for performance run creation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from sqlalchemy import select

from app.models.performance import PerformanceRun


class PerformanceIdempotencyConflict(ValueError):
    """Raised when a key is reused for a different performance request."""


def normalize_idempotency_key(value: str | None) -> str | None:
    """Normalize an optional client supplied run key and reject blank values."""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("幂等键不能为空")
    return normalized


def build_idempotency_fingerprint(
    *,
    source: str,
    environment_id: int | None,
    performance_node_id: int | None,
    performance_node_ids: Sequence[int] | None,
    options: Mapping,
    extra_vars: Mapping | None = None,
) -> str:
    """Create a stable hash of request fields that affect a run."""

    payload = {
        "source": source,
        "environment_id": environment_id,
        "performance_node_id": performance_node_id,
        "performance_node_ids": list(performance_node_ids or []),
        "options": options,
        "extra_vars": extra_vars or {},
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def find_idempotent_run(
    db,
    *,
    project_id: int,
    performance_test_id: int,
    key: str,
    fingerprint: str,
) -> PerformanceRun | None:
    """Find the parent run associated with a client idempotency key."""

    result = await db.execute(
        select(PerformanceRun)
        .where(
            PerformanceRun.project_id == project_id,
            PerformanceRun.performance_test_id == performance_test_id,
            PerformanceRun.idempotency_key == key,
            PerformanceRun.parent_run_id.is_(None),
        )
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        stored_fingerprint = getattr(existing, "idempotency_fingerprint", None)
        if stored_fingerprint and stored_fingerprint != fingerprint:
            raise PerformanceIdempotencyConflict("幂等键已被其他压测请求使用")
    return existing
