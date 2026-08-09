"""cases 包 - 执行触发与 run 查询端点。"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Union

import app.api.v1.cases as _cases
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.core.encryption import decrypt_env_vars
from app.models.case import CaseType, RunStatus, TestCase, TestRun
from app.models.environment import Environment, EnvVariable
from app.models.project import Module
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.case import (
    FailureDiagnosisOut,
    HealingFeedbackRequest,
    PaginatedRunsOut,
    RunCursorPage,
    RunTriggerRequest,
    TestRunOut,
)
from app.services.failure_diagnosis import generate_failure_diagnosis

router = APIRouter(tags=["用例管理"])


def _encode_cursor(created_at: datetime, run_id: int) -> str:
    payload = f"{created_at.isoformat()}|{run_id}"
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, id_str = decoded.rsplit("|", 1)
        return datetime.fromisoformat(ts_str), int(id_str)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="cursor 格式无效") from exc


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
    module = await db.get(Module, case.module_id)
    if module:
        await assert_project_access(db, current_user, module.project_id, ProjectRole.editor)
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

    if case.case_type == CaseType.ios:
        _cases.run_test_case.apply_async(args=(run.id, merged_vars, run.trace_id), queue="ios")
    else:
        _cases.run_test_case.delay(run.id, merged_vars, run.trace_id)
    result = await db.execute(select(TestRun).where(TestRun.id == run.id).options(selectinload(TestRun.steps)))
    return TestRunOut.model_validate(result.scalar_one())


@router.get("/runs", response_model=Union[PaginatedRunsOut, RunCursorPage])
async def list_runs(
    case_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, description="Keyset 分页游标；传则忽略 page/page_size"),
    limit: int = Query(20, ge=1, le=100, description="Keyset 分页页大小"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    base = select(TestRun)
    if case_id:
        base = base.where(TestRun.case_id == case_id)

    if cursor is not None:
        cursor_ts, cursor_id = _decode_cursor(cursor)
        keyset_query = (
            base.where(
                (TestRun.created_at < cursor_ts) | ((TestRun.created_at == cursor_ts) & (TestRun.id < cursor_id))
            )
            .order_by(TestRun.created_at.desc(), TestRun.id.desc())
            .limit(limit + 1)
        )
        result = await db.execute(keyset_query)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
        return RunCursorPage(items=rows, next_cursor=next_cursor, has_more=has_more)

    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    query = base.order_by(TestRun.created_at.desc())
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


@router.post("/runs/{run_id}/failure-diagnosis", response_model=FailureDiagnosisOut)
async def diagnose_run_failure(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    case = await db.get(TestCase, run.case_id)
    module = await db.get(Module, case.module_id) if case else None
    if module:
        await assert_project_access(db, current_user, module.project_id, ProjectRole.viewer)

    diagnosis = await generate_failure_diagnosis(db, run_id)
    if diagnosis is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return diagnosis


@router.post(
    "/runs/{run_id}/steps/{step_id}/healing/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def submit_healing_feedback(
    run_id: int,
    step_id: int,
    body: HealingFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """对单 step 的 AI 诊断建议给采纳/拒绝反馈（iter3）。

    幂等：重复提交覆盖上一次值；要求 step 的 healing_status=done 才允许反馈。
    """
    from datetime import datetime, timezone

    from app.models.case import StepResult

    result = await db.execute(select(StepResult).where(StepResult.id == step_id, StepResult.run_id == run_id))
    step = result.scalar_one_or_none()
    if step is None:
        raise HTTPException(status_code=404, detail="step 不存在或不属于该 run")
    if step.healing_status != "done":
        raise HTTPException(status_code=400, detail="仅 healing_status=done 的 step 可反馈")

    step.healing_feedback = body.action
    step.healing_feedback_at = datetime.now(timezone.utc)
    await db.commit()
    return None
