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
from app.core.encryption import decrypt_env_vars
from app.core.tracing import get_trace_id
from app.models.environment import Environment, EnvVariable
from app.models.plan import TestPlan, PlanRun, PlanRunStatus, ScheduleType, TriggerType
from app.models.project import Project
from app.models.suite import TestSuite
from app.models.user import User
from app.schemas.plan import (
    TestPlanCreate,
    TestPlanUpdate,
    TestPlanOut,
    PlanRunTrigger,
    PlanRunOut,
    WebhookTriggerRequest,
    PlanBatchDeleteIn,
    PlanBatchToggleIn,
    PlanBatchOpOut,
)
from app.api.deps import assert_project_access, get_current_user, require_engineer
from app.models.user_project import ProjectRole
from app.services.execution_routing import enqueue_task, resolve_plan_execution_queue

router = APIRouter(tags=["测试计划"])


def _normalize_suite_items(suite_items: list[object]) -> list[dict]:
    return [item if isinstance(item, dict) else item.model_dump() for item in suite_items]


async def _validate_plan_suite_ids(db: AsyncSession, project_id: int, suite_items: list[object]) -> list[dict]:
    normalized = _normalize_suite_items(suite_items)
    suite_ids = [item["suite_id"] for item in normalized]

    if len(suite_ids) != len(set(suite_ids)):
        raise HTTPException(status_code=400, detail="计划中包含重复套件")

    if not suite_ids:
        return normalized

    result = await db.execute(select(TestSuite).where(TestSuite.id.in_(suite_ids)))
    suites = result.scalars().all()
    suite_map = {suite.id: suite for suite in suites}

    missing_suite_id = next((suite_id for suite_id in suite_ids if suite_id not in suite_map), None)
    if missing_suite_id is not None:
        raise HTTPException(status_code=400, detail=f"测试套件不存在: {missing_suite_id}")

    wrong_project_suite_id = next(
        (suite_id for suite_id in suite_ids if suite_map[suite_id].project_id != project_id),
        None,
    )
    if wrong_project_suite_id is not None:
        raise HTTPException(status_code=400, detail=f"测试套件 {wrong_project_suite_id} 不属于当前项目")

    return normalized


async def _validate_plan_environment(db: AsyncSession, project_id: int, env_id: int | None) -> None:
    if env_id is None:
        return

    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(status_code=404, detail="环境不存在")
    if env.project_id != project_id:
        raise HTTPException(status_code=400, detail=f"环境 {env_id} 不属于当前项目")


@router.post("/plans", response_model=TestPlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: TestPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    await assert_project_access(db, current_user, body.project_id, ProjectRole.editor)
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    suite_ids = await _validate_plan_suite_ids(db, body.project_id, body.suite_ids)
    await _validate_plan_environment(db, body.project_id, body.env_id)

    plan = TestPlan(
        name=body.name,
        description=body.description,
        project_id=body.project_id,
        suite_ids=suite_ids,
        schedule_type=body.schedule_type,
        cron_expression=body.cron_expression,
        is_enabled=body.is_enabled,
        auto_create_bugs=body.auto_create_bugs,
        env_id=body.env_id,
        config=body.config or {},
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
    user=Depends(get_current_user),
):
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    q = select(TestPlan).order_by(TestPlan.created_at.desc())
    if project_id is not None:
        q = q.where(TestPlan.project_id == project_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/plans/{plan_id}", response_model=TestPlanOut)
async def get_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    plan = await db.get(TestPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")
    await assert_project_access(db, user, plan.project_id, ProjectRole.viewer)
    return plan


@router.patch("/plans/{plan_id}", response_model=TestPlanOut)
async def update_plan(
    plan_id: int,
    body: TestPlanUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    plan = await db.get(TestPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")
    await assert_project_access(db, user, plan.project_id, ProjectRole.editor)

    update_data = body.model_dump(exclude_none=True)
    if "suite_ids" in update_data:
        update_data["suite_ids"] = await _validate_plan_suite_ids(db, plan.project_id, update_data["suite_ids"])
    if "env_id" in update_data:
        await _validate_plan_environment(db, plan.project_id, update_data["env_id"])
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
    user=Depends(require_engineer),
):
    plan = await db.get(TestPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")
    await assert_project_access(db, user, plan.project_id, ProjectRole.editor)
    await db.delete(plan)
    await db.commit()


@router.post("/plans/batch/delete", response_model=PlanBatchOpOut)
async def batch_delete_plans(
    body: PlanBatchDeleteIn,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    requested_ids = list(dict.fromkeys(body.plan_ids))
    rows = (await db.execute(select(TestPlan).where(TestPlan.id.in_(requested_ids)))).scalars().all()
    found_ids = {row.id for row in rows}
    skipped_ids = [pid for pid in requested_ids if pid not in found_ids]
    for plan in rows:
        await db.delete(plan)
    await db.commit()
    return PlanBatchOpOut(
        requested=len(requested_ids),
        processed=len(rows),
        skipped_ids=skipped_ids,
    )


@router.post("/plans/batch/toggle", response_model=PlanBatchOpOut)
async def batch_toggle_plans(
    body: PlanBatchToggleIn,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    requested_ids = list(dict.fromkeys(body.plan_ids))
    rows = (await db.execute(select(TestPlan).where(TestPlan.id.in_(requested_ids)))).scalars().all()
    found_ids = {row.id for row in rows}
    skipped_ids = [pid for pid in requested_ids if pid not in found_ids]
    changed: list[int] = []
    for plan in rows:
        if plan.is_enabled != body.is_enabled:
            plan.is_enabled = body.is_enabled
            changed.append(plan.id)
        else:
            skipped_ids.append(plan.id)
    await db.commit()
    return PlanBatchOpOut(
        requested=len(requested_ids),
        processed=len(changed),
        skipped_ids=skipped_ids,
    )


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
    await assert_project_access(db, current_user, plan.project_id, ProjectRole.editor)
    if not plan.suite_ids:
        raise HTTPException(status_code=400, detail="计划中没有测试套件")

    # 解析环境变量
    env_id = body.env_id if body.env_id is not None else plan.env_id
    merged_vars = dict(body.extra_vars)
    if env_id is not None:
        env = await db.get(Environment, env_id)
        if not env:
            raise HTTPException(status_code=404, detail="环境不存在")
        result = await db.execute(select(EnvVariable).where(EnvVariable.env_id == env.id))
        env_vars = decrypt_env_vars(result.scalars().all())
        merged_vars = {**env_vars, **body.extra_vars}

    plan_run = PlanRun(
        plan_id=plan_id,
        triggered_by=current_user.id,
        trace_id=get_trace_id() or None,
        trigger_type=TriggerType.manual,
        status=PlanRunStatus.pending,
    )
    db.add(plan_run)
    await db.commit()
    await db.refresh(plan_run)

    from app.worker.tasks import run_test_plan

    queue = await resolve_plan_execution_queue(db, plan)
    enqueue_task(run_test_plan, (plan_run.id, merged_vars, plan_run.trace_id), queue)

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
            result = await db.execute(select(EnvVariable).where(EnvVariable.env_id == env.id))
            env_vars = decrypt_env_vars(result.scalars().all())
            merged_vars = {**env_vars, **body.extra_vars}

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

    queue = await resolve_plan_execution_queue(db, plan)
    enqueue_task(run_test_plan, (plan_run.id, merged_vars, plan_run.trace_id), queue)

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
