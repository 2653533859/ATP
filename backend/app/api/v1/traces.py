from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.case import TestRun
from app.models.plan import PlanRun
from app.models.suite import SuiteRun
from app.models.user import User
from app.schemas.trace import TraceDetailOut

router = APIRouter(tags=["链路追踪"])


class TracingConfigOut(BaseModel):
    jaeger_ui_url: str


@router.get("/traces/config", response_model=TracingConfigOut)
async def get_tracing_config(_: User = Depends(get_current_user)):
    """返回前端展示"在 Jaeger 中打开"按钮所需的 UI 基础 URL。

    `JAEGER_UI_URL` 为空时按钮在前端隐藏。
    """
    return TracingConfigOut(jaeger_ui_url=settings.JAEGER_UI_URL or "")


@router.get("/traces/{trace_id}", response_model=TraceDetailOut)
async def get_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    case_runs = (
        (
            await db.execute(
                select(TestRun)
                .options(selectinload(TestRun.steps))
                .where(TestRun.trace_id == trace_id)
                .order_by(TestRun.created_at.asc(), TestRun.id.asc())
            )
        )
        .scalars()
        .all()
    )
    suite_runs = (
        (
            await db.execute(
                select(SuiteRun)
                .where(SuiteRun.trace_id == trace_id)
                .order_by(SuiteRun.created_at.asc(), SuiteRun.id.asc())
            )
        )
        .scalars()
        .all()
    )
    plan_runs = (
        (
            await db.execute(
                select(PlanRun).where(PlanRun.trace_id == trace_id).order_by(PlanRun.created_at.asc(), PlanRun.id.asc())
            )
        )
        .scalars()
        .all()
    )

    total_runs = len(case_runs) + len(suite_runs) + len(plan_runs)
    if total_runs == 0:
        raise HTTPException(status_code=404, detail="Trace 不存在")

    timestamps = [run.created_at for run in [*case_runs, *suite_runs, *plan_runs] if run.created_at is not None]

    return TraceDetailOut(
        trace_id=trace_id,
        total_runs=total_runs,
        created_at=min(timestamps) if timestamps else None,
        last_seen_at=max(timestamps) if timestamps else None,
        case_runs=case_runs,
        suite_runs=suite_runs,
        plan_runs=plan_runs,
    )
