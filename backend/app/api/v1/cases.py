from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.models.case import TestCase, TestRun, RunStatus
from app.models.environment import Environment, EnvVariable
from app.schemas.case import TestCaseCreate, TestCaseUpdate, TestCaseOut, TestCaseDetailOut, RunTriggerRequest, TestRunOut
from app.api.deps import get_current_user
from app.worker.tasks import run_test_case

router = APIRouter(tags=["用例管理"])


@router.get("/cases", response_model=list[TestCaseOut])
async def list_cases(
    module_id: int | None = Query(None),
    case_type: str | None = Query(None),
    tag: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(TestCase)
    if module_id:
        q = q.where(TestCase.module_id == module_id)
    if case_type:
        q = q.where(TestCase.case_type == case_type)
    result = await db.execute(q.order_by(TestCase.created_at.desc()))
    cases = result.scalars().all()
    if tag:
        cases = [c for c in cases if tag in (c.tags or [])]
    return cases


@router.post("/cases", response_model=TestCaseDetailOut, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = TestCase(**body.model_dump(), creator_id=current_user.id)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


@router.get("/cases/{case_id}", response_model=TestCaseDetailOut)
async def get_case(case_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    return case


@router.patch("/cases/{case_id}", response_model=TestCaseDetailOut)
async def update_case(
    case_id: int, body: TestCaseUpdate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)
):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(case, k, v)
    await db.commit()
    await db.refresh(case)
    return case


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(case_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    await db.delete(case)
    await db.commit()


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

    # Load environment variables if env_id is provided
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
        # Environment variables as base, extra_vars override
        merged_vars = {**env_vars, **body.extra_vars}

    run = TestRun(
        case_id=case_id,
        triggered_by=current_user.id,
        status=RunStatus.pending,
        environment=env_name,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # 异步发送给 Celery Worker
    run_test_case.delay(run.id, merged_vars)

    return run


@router.get("/runs", response_model=list[TestRunOut])
async def list_runs(
    case_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(TestRun).options(selectinload(TestRun.steps))
    if case_id:
        q = q.where(TestRun.case_id == case_id)
    result = await db.execute(q.order_by(TestRun.created_at.desc()))
    return result.scalars().all()


@router.get("/runs/{run_id}", response_model=TestRunOut)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(TestRun).where(TestRun.id == run_id).options(selectinload(TestRun.steps))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return run
