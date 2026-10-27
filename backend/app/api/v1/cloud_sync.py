"""Cloud Result Center API: Result receiving, deduplication, and aggregation (D3)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.cloud_sync import CloudRunSummaryModel
from app.models.user import User, UserRole
from app.schemas.cloud_sync import CloudRunSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cloud-sync", tags=["云端结果汇总"])


async def require_cloud_sync_admin(user: User = Depends(get_current_user)) -> User:
    """Cloud summaries have no shared project membership; restrict them to admins."""
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cloud summary admin access required")
    return user


@router.post("/runs", status_code=status.HTTP_200_OK)
async def receive_run_summary(
    summary: CloudRunSummary,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_cloud_sync_admin),
) -> dict[str, Any]:
    """Receive a lightweight, PII-redacted test run summary and persist it idempotently."""
    stmt = select(CloudRunSummaryModel).where(CloudRunSummaryModel.unique_key == summary.unique_key)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    step_dicts = [s.model_dump() for s in summary.steps]

    if existing:
        existing.status = summary.status
        existing.finished_at = summary.finished_at
        existing.duration_ms = summary.duration_ms
        existing.metrics = summary.metrics
        existing.error_summary = summary.error_summary
        existing.steps_summary = step_dicts
        action = "updated"
    else:
        record = CloudRunSummaryModel(
            client_id=summary.client_id,
            machine_name=summary.machine_name,
            unique_key=summary.unique_key,
            run_type=summary.run_type,
            run_id=summary.run_id,
            project_name=summary.project_name,
            project_code=summary.project_code,
            title=summary.title,
            status=summary.status,
            started_at=summary.started_at,
            finished_at=summary.finished_at,
            duration_ms=summary.duration_ms,
            triggered_by=summary.triggered_by,
            environment=summary.environment,
            metrics=summary.metrics,
            error_summary=summary.error_summary,
            steps_summary=step_dicts,
        )
        db.add(record)
        action = "created"

    await db.commit()
    logger.info("Cloud sync received %s run %s (%s)", summary.run_type, summary.run_id, action)

    return {
        "status": "ok",
        "acknowledged": True,
        "unique_key": summary.unique_key,
        "action": action,
    }


@router.get("/runs")
async def list_cloud_runs(
    client_id: str | None = None,
    project_code: str | None = None,
    run_type: str | None = None,
    run_status: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_cloud_sync_admin),
) -> dict[str, Any]:
    """Query persisted cloud test run summaries with pagination and filters."""
    query = select(CloudRunSummaryModel)

    if client_id:
        query = query.where(CloudRunSummaryModel.client_id == client_id)
    if project_code:
        query = query.where(CloudRunSummaryModel.project_code == project_code)
    if run_type:
        query = query.where(CloudRunSummaryModel.run_type == run_type)
    if run_status:
        query = query.where(CloudRunSummaryModel.status == run_status)

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    query = query.order_by(CloudRunSummaryModel.reported_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    results = (await db.execute(query)).scalars().all()

    items = [
        {
            "id": r.id,
            "client_id": r.client_id,
            "machine_name": r.machine_name,
            "unique_key": r.unique_key,
            "run_type": r.run_type,
            "run_id": r.run_id,
            "project_name": r.project_name,
            "project_code": r.project_code,
            "title": r.title,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "duration_ms": r.duration_ms,
            "triggered_by": r.triggered_by,
            "environment": r.environment,
            "metrics": r.metrics,
            "error_summary": r.error_summary,
            "step_count": len(r.steps_summary or []),
            "reported_at": r.reported_at.isoformat() if r.reported_at else None,
        }
        for r in results
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/runs/{unique_key}")
async def get_cloud_run_detail(
    unique_key: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_cloud_sync_admin),
) -> dict[str, Any]:
    """Retrieve full details of a specific cloud summary including step breakdown."""
    stmt = select(CloudRunSummaryModel).where(CloudRunSummaryModel.unique_key == unique_key)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Cloud run summary not found")

    return {
        "id": record.id,
        "client_id": record.client_id,
        "machine_name": record.machine_name,
        "unique_key": record.unique_key,
        "run_type": record.run_type,
        "run_id": record.run_id,
        "project_name": record.project_name,
        "project_code": record.project_code,
        "title": record.title,
        "status": record.status,
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "finished_at": record.finished_at.isoformat() if record.finished_at else None,
        "duration_ms": record.duration_ms,
        "triggered_by": record.triggered_by,
        "environment": record.environment,
        "metrics": record.metrics,
        "error_summary": record.error_summary,
        "steps": record.steps_summary,
        "reported_at": record.reported_at.isoformat() if record.reported_at else None,
    }


@router.get("/stats")
async def get_cloud_sync_stats(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_cloud_sync_admin),
) -> dict[str, Any]:
    """Return aggregated stats across all reporting client desktop nodes."""
    total_runs = (await db.execute(select(func.count(CloudRunSummaryModel.id)))).scalar_one()

    # Group by status
    status_counts = (
        await db.execute(
            select(CloudRunSummaryModel.status, func.count(CloudRunSummaryModel.id)).group_by(
                CloudRunSummaryModel.status
            )
        )
    ).all()

    # Group by client_id
    client_counts = (
        await db.execute(
            select(
                CloudRunSummaryModel.client_id,
                CloudRunSummaryModel.machine_name,
                func.count(CloudRunSummaryModel.id),
            ).group_by(CloudRunSummaryModel.client_id, CloudRunSummaryModel.machine_name)
        )
    ).all()

    # Group by run_type
    type_counts = (
        await db.execute(
            select(CloudRunSummaryModel.run_type, func.count(CloudRunSummaryModel.id)).group_by(
                CloudRunSummaryModel.run_type
            )
        )
    ).all()

    return {
        "total_runs": total_runs,
        "status_distribution": {row[0]: row[1] for row in status_counts},
        "type_distribution": {row[0]: row[1] for row in type_counts},
        "connected_clients": [
            {"client_id": row[0], "machine_name": row[1], "runs_count": row[2]} for row in client_counts
        ],
    }


@router.get("/local/status")
async def get_local_sync_status(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve local Outbox sync queue status and client machine metadata."""
    from app.core.config import settings
    from app.core.local_machine_identity import get_machine_id, get_machine_name
    from app.services.sync_outbox import get_outbox_stats, list_outbox_items

    stats = {"pending": 0, "syncing": 0, "synced": 0, "failed": 0, "total": 0}
    recent: list[dict[str, Any]] = []

    if settings.ATP_LOCAL_MODE:
        try:
            from app.core.database import sync_engine

            with sync_engine.connect() as conn:
                stats = get_outbox_stats(conn)
                recent = list_outbox_items(conn, limit=10)
        except Exception as exc:
            logger.warning("Failed to query local outbox stats: %s", exc)

    return {
        "local_mode": settings.ATP_LOCAL_MODE,
        "machine_id": get_machine_id() if settings.ATP_LOCAL_MODE else None,
        "machine_name": get_machine_name() if settings.ATP_LOCAL_MODE else None,
        "cloud_sync_url": settings.CLOUD_SYNC_URL or "",
        "cloud_sync_enabled": bool(settings.CLOUD_SYNC_ENABLED or settings.CLOUD_SYNC_URL),
        "stats": stats,
        "recent_items": recent,
    }


@router.post("/local/sync-now")
async def trigger_local_sync(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Manually trigger an immediate synchronization sweep from local Outbox to Cloud."""
    import asyncio
    from app.services.cloud_sync_client import sync_pending_outbox

    if not settings.ATP_LOCAL_MODE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local sync is unavailable")
    res = await asyncio.to_thread(sync_pending_outbox, force_retry=True)
    return res


@router.get("/local/runs/{run_type}/{run_id}")
async def get_local_run_sync_status(
    run_type: str,
    run_id: int,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the specific cloud synchronization status for a local run."""
    from app.core.config import settings
    from sqlalchemy import text

    if not settings.ATP_LOCAL_MODE:
        return {"sync_status": "server_mode"}

    try:
        from app.core.database import sync_engine

        with sync_engine.connect() as conn:
            res = conn.execute(
                text(
                    "SELECT status, synced_at, last_error, attempts, unique_key "
                    "FROM local_sync_outbox WHERE run_type = :run_type AND run_id = :run_id"
                ),
                {"run_type": run_type, "run_id": run_id},
            )
            row = res.mappings().first() if res is not None else None

            if row:
                return {
                    "sync_status": str(row["status"]),
                    "synced_at": str(row["synced_at"]) if row["synced_at"] else None,
                    "last_error": str(row["last_error"]) if row["last_error"] else None,
                    "attempts": int(row["attempts"] or 0),
                    "unique_key": str(row["unique_key"]),
                }
    except Exception as exc:
        logger.warning("Failed to query run sync status: %s", exc)

    return {"sync_status": "not_queued"}
