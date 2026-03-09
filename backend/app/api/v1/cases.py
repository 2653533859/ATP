from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.models.case import TestCase, TestRun, RunStatus, CaseSnapshot
from app.models.project import Module
from app.models.environment import Environment, EnvVariable
from app.core.encryption import decrypt_env_vars
from app.services.audit import write_audit_log
from app.schemas.case import (
    TestCaseCreate, TestCaseUpdate, TestCaseOut, TestCaseDetailOut,
    RunTriggerRequest, TestRunOut, CaseSnapshotOut, PaginatedRunsOut,
    PaginatedSnapshotsOut,
)
from app.api.deps import get_current_user
from app.worker.tasks import run_test_case

router = APIRouter(tags=["用例管理"])


async def _next_snapshot_version(db: AsyncSession, case_id: int) -> int:
    await db.execute(
        select(TestCase.id)
        .where(TestCase.id == case_id)
        .with_for_update()
    )
    max_ver = await db.scalar(
        select(func.coalesce(func.max(CaseSnapshot.version), 0))
        .where(CaseSnapshot.case_id == case_id)
    )
    return (max_ver or 0) + 1


@router.get("/cases", response_model=list[TestCaseOut])
async def list_cases(
    project_id: int | None = Query(None),
    module_id: int | None = Query(None),
    case_type: str | None = Query(None),
    tag: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(TestCase)
    if project_id:
        q = q.join(Module, TestCase.module_id == Module.id).where(Module.project_id == project_id)
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
    await write_audit_log(
        db, action="create", resource_type="test_case", resource_id=case.id,
        user_id=current_user.id, username=current_user.username,
        detail=f"创建用例: {case.name}",
    )
    await db.commit()
    return case


@router.get("/cases/{case_id}", response_model=TestCaseDetailOut)
async def get_case(case_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    return case


@router.patch("/cases/{case_id}", response_model=TestCaseDetailOut)
async def update_case(
    case_id: int,
    body: TestCaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    # 自动保存快照（记录修改前的状态）
    snapshot = CaseSnapshot(
        case_id=case_id,
        version=await _next_snapshot_version(db, case_id),
        name=case.name,
        description=case.description,
        tags=case.tags or [],
        config=case.config or {},
        updated_by=current_user.id,
    )
    db.add(snapshot)

    for k, v in body.model_dump(exclude_none=True).items():
        setattr(case, k, v)
    await db.commit()
    await db.refresh(case)
    return case


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    case_name = case.name
    await db.delete(case)
    await write_audit_log(
        db, action="delete", resource_type="test_case", resource_id=case_id,
        user_id=current_user.id, username=current_user.username,
        detail=f"删除用例: {case_name}",
    )
    await db.commit()


# ── 版本历史 ────────────────────────────────────────────────
@router.get("/cases/{case_id}/snapshots", response_model=PaginatedSnapshotsOut)
async def list_snapshots(
    case_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    total = await db.scalar(
        select(func.count()).select_from(
            select(CaseSnapshot.id).where(CaseSnapshot.case_id == case_id).subquery()
        )
    )

    result = await db.execute(
        select(CaseSnapshot, User.username)
        .outerjoin(User, CaseSnapshot.updated_by == User.id)
        .where(CaseSnapshot.case_id == case_id)
        .order_by(CaseSnapshot.version.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = []
    for snap, username in result.all():
        out = CaseSnapshotOut.model_validate(snap)
        out.updated_by_name = username or ""
        items.append(out)

    return PaginatedSnapshotsOut(
        items=items,
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/cases/{case_id}/snapshots/{snapshot_id}", response_model=CaseSnapshotOut)
async def get_snapshot(
    case_id: int,
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    snapshot = await db.get(CaseSnapshot, snapshot_id)
    if not snapshot or snapshot.case_id != case_id:
        raise HTTPException(status_code=404, detail="快照不存在")
    return snapshot


@router.post("/cases/{case_id}/rollback/{snapshot_id}", response_model=TestCaseDetailOut)
async def rollback_case(
    case_id: int,
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    snapshot = await db.get(CaseSnapshot, snapshot_id)
    if not snapshot or snapshot.case_id != case_id:
        raise HTTPException(status_code=404, detail="快照不存在")

    # 回滚前先保存当前状态为新快照
    rollback_snapshot = CaseSnapshot(
        case_id=case_id,
        version=await _next_snapshot_version(db, case_id),
        name=case.name,
        description=case.description,
        tags=case.tags or [],
        config=case.config or {},
        updated_by=current_user.id,
    )
    db.add(rollback_snapshot)

    # 用快照内容覆盖用例
    case.name = snapshot.name
    case.description = snapshot.description
    case.tags = snapshot.tags
    case.config = snapshot.config
    await db.commit()
    await db.refresh(case)
    return case


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
        env_vars = decrypt_env_vars(result.scalars().all())
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
    result = await db.execute(
        select(TestRun).where(TestRun.id == run.id).options(selectinload(TestRun.steps))
    )
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

    q = base.options(selectinload(TestRun.steps)).order_by(TestRun.created_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)

    return PaginatedRunsOut(
        items=result.scalars().all(),
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/runs/{run_id}", response_model=TestRunOut)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(TestRun).where(TestRun.id == run_id).options(selectinload(TestRun.steps))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return run
