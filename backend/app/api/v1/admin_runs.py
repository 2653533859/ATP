from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin_runs import (
    RunRetentionExecuteIn,
    RunRetentionExecuteOut,
    RunRetentionPerProjectOut,
    RunRetentionPreviewOut,
)
from app.services.run_retention import (
    execute_old_runs_cleanup,
    preview_old_runs,
    preview_old_runs_by_project,
)

router = APIRouter(tags=["admin-runs"])


@router.get("/admin/runs/retention/preview", response_model=RunRetentionPreviewOut)
async def runs_retention_preview(
    days: int | None = Query(None, ge=1, le=3650),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    effective_days = days or settings.RUN_RETENTION_DAYS
    payload = await db.run_sync(lambda session: preview_old_runs(session, effective_days))
    return RunRetentionPreviewOut(**payload)


@router.get("/admin/runs/retention/per-project-preview")
async def runs_retention_per_project_preview(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """P1.4：列出全局预览 + 所有设置了 run_retention_days_override 的项目按其覆盖天数的清理预览。

    返回结构沿用 service 层 dict（含 'global' 与 'projects' 两键）。
    """
    payload = await db.run_sync(
        lambda session: preview_old_runs_by_project(session, settings.RUN_RETENTION_DAYS)
    )
    return payload


@router.post("/admin/runs/retention/run", response_model=RunRetentionExecuteOut)
async def runs_retention_run(
    body: RunRetentionExecuteIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    effective_days = body.days or settings.RUN_RETENTION_DAYS
    payload = await db.run_sync(
        lambda session: execute_old_runs_cleanup(
            session,
            days=effective_days,
            batch_size=settings.RUN_CLEANUP_BATCH_SIZE,
        )
    )
    return RunRetentionExecuteOut(**payload)
