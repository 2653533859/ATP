"""
CI/CD Webhook 触发接口

POST /webhook/trigger   通用 Webhook 触发（API Key 认证）
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.suite import TestSuite, SuiteRun, SuiteRunStatus
from app.models.plan import TestPlan, PlanRun, PlanRunStatus, TriggerType
from app.models.performance import PerformanceRun, PerformanceRunStatus, PerformanceTest
from app.models.environment import Environment, EnvVariable
from app.core.encryption import decrypt_env_vars
from app.core.tracing import get_trace_id
from app.services.performance_report import build_performance_gate
from app.services.performance_runtime import build_options_snapshot

router = APIRouter(tags=["Webhook"])


class WebhookTriggerBody(BaseModel):
    target_type: str  # "suite" | "plan" | "performance_test"
    target_id: int
    env_id: int | None = None
    extra_vars: dict = Field(default_factory=dict)
    options: dict = Field(default_factory=dict)
    performance_node_id: int | None = Field(default=None, ge=1)


class WebhookTriggerResponse(BaseModel):
    run_id: int
    target_type: str
    target_id: int
    status: str


class WebhookPerformanceGateResponse(BaseModel):
    run_id: int
    status: str
    ready: bool
    run_status: str
    total: int
    passed: int
    failed: int


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
    - target_type: "suite"、"plan" 或 "performance_test"
    - target_id: 套件、计划或压测定义的 ID
    - env_id: 可选，指定执行环境
    - extra_vars: 可选，额外变量
    - options: 可选，performance_test 的本次 options 覆盖
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

    elif body.target_type == "performance_test":
        test = await db.get(PerformanceTest, body.target_id)
        if not test:
            raise HTTPException(status_code=404, detail="压测定义不存在")

        environment_values: dict = {}
        secret_keys: set[str] = set()
        if body.env_id is not None:
            environment = await db.get(Environment, body.env_id)
            if not environment:
                raise HTTPException(status_code=404, detail="环境不存在")
            if environment.project_id != test.project_id:
                raise HTTPException(status_code=400, detail="环境不属于当前项目")
            result = await db.execute(select(EnvVariable).where(EnvVariable.env_id == body.env_id))
            variables = result.scalars().all()
            environment_values = decrypt_env_vars(variables)
            secret_keys = {variable.key for variable in variables if variable.is_secret}

        from app.api.v1.performance import (
            _add_dataset_runtime_options,
            _resolve_performance_dataset,
            _resolve_performance_node,
            _validate_environment_overrides,
            _validate_performance_options,
        )

        _validate_environment_overrides(body.options)
        options_snapshot, runtime_options = build_options_snapshot(
            test.default_options,
            body.options,
            {**environment_values, **body.extra_vars},
            secret_keys | set(body.extra_vars),
        )
        dataset_binding = await _resolve_performance_dataset(db, getattr(test, "dataset_id", None), test.project_id)
        validation_options = await _add_dataset_runtime_options(db, runtime_options, dataset_binding)
        executor = getattr(test, "executor", "k6")
        _validate_performance_options(validation_options, executor)
        node = await _resolve_performance_node(db, body.performance_node_id, validation_options, executor)
        run = PerformanceRun(
            performance_test_id=test.id,
            project_id=test.project_id,
            environment_id=body.env_id,
            performance_node_id=node.id if node else None,
            dataset_id=dataset_binding[0] if dataset_binding else None,
            dataset_version=dataset_binding[1] if dataset_binding else None,
            status=PerformanceRunStatus.pending.value,
            triggered_by=None,
            options_snapshot=options_snapshot,
            summary={},
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        from app.worker.tasks_performance import run_performance_test

        from app.services.performance_node import enqueue_performance_run

        enqueue_performance_run(run_performance_test, run.id, node.queue_name if node else None)
        return WebhookTriggerResponse(
            run_id=run.id,
            target_type="performance_test",
            target_id=test.id,
            status=run.status,
        )

    else:
        raise HTTPException(status_code=400, detail="target_type 必须是 suite、plan 或 performance_test")


@router.get(
    "/webhook/performance-runs/{run_id}/gate",
    response_model=WebhookPerformanceGateResponse,
)
async def webhook_performance_gate(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(_verify_api_key),
):
    """供 CI 使用 API Key 轮询压测门禁结果。"""
    run = await db.get(PerformanceRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="压测执行不存在")
    return WebhookPerformanceGateResponse(run_id=run.id, **build_performance_gate(run.status, run.summary))
