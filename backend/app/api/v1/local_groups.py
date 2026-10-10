"""Local-only group cancellation, with the existing project access boundary."""

from typing import Literal, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.plan import PlanRun, TestPlan
from app.models.suite import SuiteRun, TestSuite
from app.models.user_project import ProjectRole
from app.services.group_execution import execution_state, group_revision, request_cancel
from app.schemas.group_execution import GroupCancelIn, GroupCancelResult, GroupExecutionState

router = APIRouter(tags=["本地执行"])


@router.post("/local-groups/{kind}/{run_id}/cancel")
async def cancel_group(
    kind: Literal["suite", "plan"], run_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)
):
    if not settings.ATP_LOCAL_MODE:
        raise HTTPException(status_code=404, detail="仅本地模式提供此入口")
    model, owner_model, owner_key = (
        (SuiteRun, TestSuite, "suite_id") if kind == "suite" else (PlanRun, TestPlan, "plan_id")
    )
    run = await db.get(model, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    owner = await db.get(owner_model, getattr(run, owner_key))
    if owner is None:
        raise HTTPException(status_code=404, detail="执行定义不存在")
    await assert_project_access(db, user, owner.project_id, ProjectRole.editor)
    try:
        pending = await request_cancel(db, kind, run)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    await db.commit()
    return {"requested": True, "pending": pending, "message": "当前子任务结束后停止后续任务"}


async def _load_group(
    db: AsyncSession, user: Any, kind: Literal["suite", "plan"], run_id: int, role: ProjectRole
) -> Any:
    if kind == "suite":
        run = await db.get(SuiteRun, run_id)
        owner = await db.get(TestSuite, run.suite_id) if run else None
    else:
        run = await db.get(PlanRun, run_id)
        owner = await db.get(TestPlan, run.plan_id) if run else None
    if run is None or owner is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    await assert_project_access(db, user, owner.project_id, role)
    return run


@router.get("/execution-groups/{kind}/{run_id}", response_model=GroupExecutionState)
async def get_group_state(
    kind: Literal["suite", "plan"],
    run_id: int,
    limit: int = Query(200, ge=1, le=1000, description="单页最大子任务数量"),
    cursor: int | None = Query(None, description="子任务游标 ID"),
    offset: int = Query(0, ge=0, description="子任务偏移量"),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    run = await _load_group(db, user, kind, run_id, ProjectRole.viewer)
    return await execution_state(db, kind, run, limit=limit, cursor=cursor, offset=offset)


@router.post("/execution-groups/{kind}/{run_id}/cancel", response_model=GroupCancelResult)
async def cancel_execution_group(
    kind: Literal["suite", "plan"],
    run_id: int,
    data: GroupCancelIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    run = await _load_group(db, user, kind, run_id, ProjectRole.editor)
    if data.expected_revision != group_revision(kind, run):
        raise HTTPException(status_code=409, detail="运行身份已变化，请重新查看记录")
    try:
        pending = await request_cancel(db, kind, run)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    await db.commit()
    return GroupCancelResult(requested=True, pending=pending)
