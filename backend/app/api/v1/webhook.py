"""
CI/CD Webhook 触发接口

POST /webhook/trigger   通用 Webhook 触发（API Key 认证）
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.suite import TestSuite, SuiteRun, SuiteRunStatus
from app.models.plan import TestPlan, PlanRun, PlanRunStatus, TriggerType
from app.models.environment import Environment, EnvVariable
from app.core.encryption import decrypt_env_vars
from app.core.tracing import get_trace_id

router = APIRouter(tags=["Webhook"])


class WebhookTriggerBody(BaseModel):
    target_type: str  # "suite" | "plan"
    target_id: int
    env_id: int | None = None
    extra_vars: dict = {}


class WebhookTriggerResponse(BaseModel):
    run_id: int
    target_type: str
    target_id: int
    status: str


def _verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.WEBHOOK_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return x_api_key


@router.post(
    "/webhook/trigger",
    response_model=WebhookTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit(settings.RATE_LIMIT_WEBHOOK)
async def webhook_trigger(
    request: Request,
    body: WebhookTriggerBody,
    db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(_verify_api_key),
):
    """
    通用 CI/CD Webhook 触发接口。

    Header: `X-API-Key: <WEBHOOK_API_KEY>`

    Body:
    - target_type: "suite" 或 "plan"
    - target_id: 套件或计划的 ID
    - env_id: 可选，指定执行环境
    - extra_vars: 可选，额外变量
    """
    # 解析环境变量
    merged_vars = dict(body.extra_vars)
    if body.env_id is not None:
        env = await db.get(Environment, body.env_id)
        if not env:
            raise HTTPException(status_code=404, detail="环境不存在")
        result = await db.execute(select(EnvVariable).where(EnvVariable.env_id == env.id))
        env_vars = decrypt_env_vars(result.scalars().all())
        merged_vars = {**env_vars, **body.extra_vars}

    if body.target_type == "suite":
        suite = await db.get(TestSuite, body.target_id)
        if not suite:
            raise HTTPException(status_code=404, detail="套件不存在")
        if not suite.case_ids:
            raise HTTPException(status_code=400, detail="套件中没有用例")

        suite_run = SuiteRun(
            suite_id=suite.id,
            triggered_by=suite.creator_id,
            trace_id=get_trace_id() or None,
            status=SuiteRunStatus.pending,
        )
        db.add(suite_run)
        await db.commit()
        await db.refresh(suite_run)

        from app.worker.tasks import run_test_suite

        run_test_suite.delay(suite_run.id, merged_vars, suite_run.trace_id)

        return WebhookTriggerResponse(
            run_id=suite_run.id,
            target_type="suite",
            target_id=suite.id,
            status="pending",
        )

    elif body.target_type == "plan":
        plan = await db.get(TestPlan, body.target_id)
        if not plan:
            raise HTTPException(status_code=404, detail="测试计划不存在")
        if not plan.suite_ids:
            raise HTTPException(status_code=400, detail="计划中没有测试套件")

        plan_run = PlanRun(
            plan_id=plan.id,
            triggered_by=None,
            trace_id=get_trace_id() or None,
            trigger_type=TriggerType.webhook,
            status=PlanRunStatus.pending,
        )
        db.add(plan_run)
        await db.commit()
        await db.refresh(plan_run)

        from app.worker.tasks import run_test_plan

        run_test_plan.delay(plan_run.id, merged_vars, plan_run.trace_id)

        return WebhookTriggerResponse(
            run_id=plan_run.id,
            target_type="plan",
            target_id=plan.id,
            status="pending",
        )

    else:
        raise HTTPException(status_code=400, detail="target_type 必须是 suite 或 plan")
