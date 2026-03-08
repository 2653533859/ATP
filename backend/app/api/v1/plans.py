"""
测试计划管理 API

POST   /plans                创建测试计划
GET    /plans                计划列表
GET    /plans/{id}           计划详情
PATCH  /plans/{id}           更新计划
DELETE /plans/{id}           删除计划
POST   /plans/{id}/run       手动触发执行
POST   /plans/webhook        Webhook 触发执行
GET    /plan-runs            计划执行记录列表
GET    /plan-runs/{id}       计划执行记录详情
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.plan import TestPlan, PlanRun, PlanRunStatus, ScheduleType, TriggerType
from app.models.project import Project
from app.models.environment import Environment, EnvVariable
from app.core.encryption import decrypt_env_vars
from app.models.user import User
from app.schemas.plan import (
    TestPlanCreate, TestPlanUpdate, TestPlanOut,
    PlanRunTrigger, PlanRunOut, WebhookTriggerRequest,
)
from app.api.deps import get_current_user, require_engineer

router = APIRouter(tags=["测试计划"])


@router.post("/plans", response_model=TestPlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: TestPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    plan = TestPlan(
        name=body.name,
        description=body.description,
        project_id=body.project_id,
        suite_ids=[item.model_dump() for item in body.suite_ids],
        schedule_type=body.schedule_type,
        cron_expression=body.cron_expression,
        is_enabled=body.is_enabled,
        env_id=body.env_id,
        creator_id=current_user.id,
    )
    # Webhook 类型自动生成 secret
    if body.schedule_type == ScheduleType.webhook:
        plan.generate_webhook_secret()
    # Cron 类型计算下次执行时间
    if body.schedule_type == ScheduleType.cron and body.cron_expression:
        plan.next_run_at = _calc_next_run(body.cron_expression)

    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.get("/plans", response_model=list[TestPlanOut])
async def list_plans(
    project_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(TestPlan).order_by(TestPlan.created_at.desc())
    if project_id is not None:
        q = q.where(TestPlan.project_id == project_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/plans/{plan_id}", response_model=TestPlanOut)
async def get_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    plan = await db.get(TestPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")
    return plan


@router.patch("/plans/{plan_id}", response_model=TestPlanOut)
async def update_plan(
    plan_id: int,
    body: TestPlanUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    plan = await db.get(TestPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    update_data = body.model_dump(exclude_none=True)
    if "suite_ids" in update_data:
        update_data["suite_ids"] = [
            item if isinstance(item, dict) else item.model_dump()
            for item in update_data["suite_ids"]
        ]
    for k, v in update_data.items():
        setattr(plan, k, v)

    # 切换为 webhook 时自动生成 secret
    if body.schedule_type == ScheduleType.webhook and not plan.webhook_secret:
        plan.generate_webhook_secret()
    # 更新 cron 时重新计算下次执行时间
    if plan.schedule_type == ScheduleType.cron and plan.cron_expression:
        plan.next_run_at = _calc_next_run(plan.cron_expression)
    else:
        plan.next_run_at = None

    await db.commit()
    await db.refresh(plan)
    return plan


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    plan = await db.get(TestPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")
    await db.delete(plan)
    await db.commit()


@router.post("/plans/{plan_id}/run", response_model=PlanRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_plan_run(
    plan_id: int,
    body: PlanRunTrigger,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = await db.get(TestPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")
    if not plan.suite_ids:
        raise HTTPException(status_code=400, detail="计划中没有测试套件")

    # 解析环境变量
    env_id = body.env_id if body.env_id is not None else plan.env_id
    merged_vars = dict(body.extra_vars)
    if env_id is not None:
        env = await db.get(Environment, env_id)
        if not env:
            raise HTTPException(status_code=404, detail="环境不存在")
        result = await db.execute(
            select(EnvVariable).where(EnvVariable.env_id == env.id)
        )
        env_vars = decrypt_env_vars(result.scalars().all())
        merged_vars = {**env_vars, **body.extra_vars}

    plan_run = PlanRun(
        plan_id=plan_id,
        triggered_by=current_user.id,
        trigger_type=TriggerType.manual,
        status=PlanRunStatus.pending,
    )
    db.add(plan_run)
    await db.commit()
    await db.refresh(plan_run)

    from app.worker.tasks import run_test_plan
    run_test_plan.delay(plan_run.id, merged_vars)

    return plan_run


@router.post("/plans/webhook", response_model=PlanRunOut, status_code=status.HTTP_202_ACCEPTED)
async def webhook_trigger(
    body: WebhookTriggerRequest,
    x_webhook_secret: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Webhook 触发执行（无需登录，通过 secret 认证）"""
    plan = await db.get(TestPlan, body.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")
    if plan.schedule_type != ScheduleType.webhook:
        raise HTTPException(status_code=400, detail="该计划不支持 Webhook 触发")
    if not plan.webhook_secret or plan.webhook_secret != x_webhook_secret:
        raise HTTPException(status_code=403, detail="Webhook Secret 验证失败")
    if not plan.suite_ids:
        raise HTTPException(status_code=400, detail="计划中没有测试套件")

    # 解析环境变量
    merged_vars = dict(body.extra_vars)
    if plan.env_id:
        env = await db.get(Environment, plan.env_id)
        if env:
            result = await db.execute(
                select(EnvVariable).where(EnvVariable.env_id == env.id)
            )
            env_vars = decrypt_env_vars(result.scalars().all())
            merged_vars = {**env_vars, **body.extra_vars}

    plan_run = PlanRun(
        plan_id=plan.id,
        triggered_by=None,
        trigger_type=TriggerType.webhook,
        status=PlanRunStatus.pending,
    )
    db.add(plan_run)
    await db.commit()
    await db.refresh(plan_run)

    from app.worker.tasks import run_test_plan
    run_test_plan.delay(plan_run.id, merged_vars)

    return plan_run


@router.get("/plan-runs", response_model=list[PlanRunOut])
async def list_plan_runs(
    plan_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(PlanRun).order_by(PlanRun.created_at.desc())
    if plan_id is not None:
        q = q.where(PlanRun.plan_id == plan_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/plan-runs/{run_id}", response_model=PlanRunOut)
async def get_plan_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    plan_run = await db.get(PlanRun, run_id)
    if not plan_run:
        raise HTTPException(status_code=404, detail="计划执行记录不存在")
    return plan_run


def _calc_next_run(cron_expression: str):
    """计算 cron 表达式的下次执行时间"""
    try:
        from croniter import croniter
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        cron = croniter(cron_expression, now)
        return cron.get_next(datetime)
    except Exception:
        return None
