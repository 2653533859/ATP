"""Remove local-only Web artifacts after their owning case runs are deleted."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import local_object_store
from app.models.case import TestRun

logger = logging.getLogger(__name__)


async def case_run_ids(db: AsyncSession, case_ids: list[int]) -> list[int]:
    if not case_ids:
        return []
    result = await db.scalars(select(TestRun.id).where(TestRun.case_id.in_(case_ids)))
    return list(result.all())


def delete_run_artifacts(run_ids: list[int]) -> None:
    for run_id in set(run_ids):
        prefixes = (
            f"screenshots/runs/{run_id}/",
            f"traces/runs/{run_id}/",
            f"videos/runs/{run_id}/",
            f"reports/run-{run_id}/",
        )
        for prefix in prefixes:
            for item in local_object_store.list_objects(prefix):
                try:
                    local_object_store.delete_file(item.object_name)
                except OSError:
                    logger.exception("Failed to remove local run artifact %s", item.object_name)
