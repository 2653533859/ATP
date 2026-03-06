"""
测试套件管理 API

POST   /suites              创建套件
GET    /suites              套件列表
GET    /suites/{id}         套件详情
PATCH  /suites/{id}         更新套件
DELETE /suites/{id}         删除套件
POST   /suites/{id}/run     触发套件执行
GET    /suite-runs           套件执行记录列表
GET    /suite-runs/{id}     套件执行记录详情
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.suite import TestSuite, SuiteRun, SuiteRunStatus
from app.models.project import Project
from app.models.environment import Environment, EnvVariable
from app.models.user import User
from app.schemas.suite import (
    TestSuiteCreate, TestSuiteUpdate, TestSuiteOut,
    SuiteRunTrigger, SuiteRunOut,
)
from app.api.deps import get_current_user, require_engineer

router = APIRouter(tags=["测试套件"])


@router.post("/suites", response_model=TestSuiteOut, status_code=status.HTTP_201_CREATED)
async def create_suite(
    body: TestSuiteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    suite = TestSuite(
        name=body.name,
        description=body.description,
        project_id=body.project_id,
        case_ids=[item.model_dump() for item in body.case_ids],
        parameterization=body.parameterization,
        config=body.config,
        creator_id=current_user.id,
    )
    db.add(suite)
    await db.commit()
    await db.refresh(suite)
    return suite


@router.get("/suites", response_model=list[TestSuiteOut])
async def list_suites(
    project_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(TestSuite).order_by(TestSuite.created_at.desc())
    if project_id is not None:
        q = q.where(TestSuite.project_id == project_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/suites/{suite_id}", response_model=TestSuiteOut)
async def get_suite(
    suite_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")
    return suite


@router.patch("/suites/{suite_id}", response_model=TestSuiteOut)
async def update_suite(
    suite_id: int,
    body: TestSuiteUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")

    update_data = body.model_dump(exclude_none=True)
    if "case_ids" in update_data:
        update_data["case_ids"] = [
            item if isinstance(item, dict) else item.model_dump()
            for item in update_data["case_ids"]
        ]
    for k, v in update_data.items():
        setattr(suite, k, v)
    await db.commit()
    await db.refresh(suite)
    return suite


@router.delete("/suites/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_suite(
    suite_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")
    await db.delete(suite)
    await db.commit()


@router.post("/suites/{suite_id}/run", response_model=SuiteRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_suite_run(
    suite_id: int,
    body: SuiteRunTrigger,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")
    if not suite.case_ids:
        raise HTTPException(status_code=400, detail="套件中没有用例")

    # 解析环境变量
    env_name: str | None = None
    merged_vars = dict(body.extra_vars)
    if body.env_id is not None:
        env = await db.get(Environment, body.env_id)
        if not env:
            raise HTTPException(status_code=404, detail="环境不存在")
        env_name = env.name
        result = await db.execute(
            select(EnvVariable).where(EnvVariable.env_id == env.id)
        )
        env_vars = {v.key: v.value for v in result.scalars().all()}
        merged_vars = {**env_vars, **body.extra_vars}

    suite_run = SuiteRun(
        suite_id=suite_id,
        triggered_by=current_user.id,
        status=SuiteRunStatus.pending,
        environment=env_name,
    )
    db.add(suite_run)
    await db.commit()
    await db.refresh(suite_run)

    # 触发 Celery 任务
    from app.worker.tasks import run_test_suite
    run_test_suite.delay(suite_run.id, merged_vars)

    return suite_run


@router.get("/suite-runs", response_model=list[SuiteRunOut])
async def list_suite_runs(
    suite_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(SuiteRun).order_by(SuiteRun.created_at.desc())
    if suite_id is not None:
        q = q.where(SuiteRun.suite_id == suite_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/suite-runs/{run_id}", response_model=SuiteRunOut)
async def get_suite_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    suite_run = await db.get(SuiteRun, run_id)
    if not suite_run:
        raise HTTPException(status_code=404, detail="套件执行记录不存在")
    return suite_run
