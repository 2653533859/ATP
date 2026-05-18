"""cases 包 - 执行触发与 run 查询端点。"""
from __future__ import annotations

import app.api.v1.cases as _cases
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.encryption import decrypt_env_vars
from app.models.case import RunStatus, TestCase, TestRun
from app.models.environment import Environment, EnvVariable
from app.models.user import User
from app.schemas.case import PaginatedRunsOut, RunTriggerRequest, TestRunOut

router = APIRouter(tags=["用例管理"])


@router.post("/cases/{case_id}/run", response_model=TestRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    case_id: int,
    body: RunTriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    _cases._assert_can_trigger_run(case)

    env_name: str | None = None
    merged_vars = dict(body.extra_vars)
    if body.env_id is not None:
        env = await db.get(Environment, body.env_id)
        if not env:
            raise HTTPException(status_code=404, detail="环境不存在")
        env_name = env.name
        result = await db.execute(select(EnvVariable).where(EnvVariable.env_id == env.id))
        env_vars = decrypt_env_vars(result.scalars().all())
        merged_vars = {**env_vars, **body.extra_vars}

    run = TestRun(
        case_id=case_id,
        triggered_by=current_user.id,
        trace_id=_cases.get_trace_id() or None,
        status=RunStatus.pending,
        environment=env_name,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    _cases.run_test_case.delay(run.id, merged_vars, run.trace_id)
    result = await db.execute(select(TestRun).where(TestRun.id == run.id).options(selectinload(TestRun.steps)))
    return TestRunOut.model_validate(result.scalar_one())


@router.get("/runs", response_model=PaginatedRunsOut)
async def list_runs(
    case_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    base = select(TestRun)
    if case_id:
        base = base.where(TestRun.case_id == case_id)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    query = base.options(selectinload(TestRun.steps)).order_by(TestRun.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return PaginatedRunsOut(
        items=result.scalars().all(),
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/runs/{run_id}", response_model=TestRunOut)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(TestRun).where(TestRun.id == run_id).options(selectinload(TestRun.steps)))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return run
