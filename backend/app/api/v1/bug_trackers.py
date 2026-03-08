"""
缺陷跟踪集成 API

POST   /bug-trackers            创建配置
GET    /bug-trackers             配置列表
GET    /bug-trackers/{id}        配置详情
PATCH  /bug-trackers/{id}        更新配置
DELETE /bug-trackers/{id}        删除配置
POST   /runs/{run_id}/create-bug 一键创建缺陷
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.bug_tracker import BugTracker
from app.models.case import TestRun, StepResult, TestCase
from app.models.project import Project, Module
from app.schemas.bug_tracker import (
    BugTrackerCreate, BugTrackerUpdate, BugTrackerOut,
    CreateBugRequest, BugResultOut,
)
from app.api.deps import require_engineer, get_current_user
from app.services.bug_reporter import create_bug, build_bug_description
from app.core.encryption import mask_config, encrypt_config, decrypt_config

router = APIRouter(tags=["缺陷跟踪"])


def _mask_tracker(tracker: BugTracker) -> dict:
    data = BugTrackerOut.model_validate(tracker).model_dump()
    data["config"] = mask_config(data.get("config", {}))
    return data


# ── CRUD ──────────────────────────────────────────────────

@router.post("/bug-trackers", response_model=BugTrackerOut, status_code=status.HTTP_201_CREATED)
async def create_bug_tracker(
    body: BugTrackerCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    tracker = BugTracker(
        name=body.name,
        project_id=body.project_id,
        tracker_type=body.tracker_type,
        config=encrypt_config(body.config),
        is_enabled=body.is_enabled,
    )
    db.add(tracker)
    await db.commit()
    await db.refresh(tracker)
    return tracker


@router.get("/bug-trackers", response_model=list[BugTrackerOut])
async def list_bug_trackers(
    project_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    q = select(BugTracker).order_by(BugTracker.created_at.desc())
    if project_id is not None:
        q = q.where(BugTracker.project_id == project_id)
    result = await db.execute(q)
    return [_mask_tracker(t) for t in result.scalars().all()]


@router.get("/bug-trackers/{tracker_id}", response_model=BugTrackerOut)
async def get_bug_tracker(
    tracker_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    tracker = await db.get(BugTracker, tracker_id)
    if not tracker:
        raise HTTPException(status_code=404, detail="缺陷跟踪配置不存在")
    return _mask_tracker(tracker)


@router.patch("/bug-trackers/{tracker_id}", response_model=BugTrackerOut)
async def update_bug_tracker(
    tracker_id: int,
    body: BugTrackerUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    tracker = await db.get(BugTracker, tracker_id)
    if not tracker:
        raise HTTPException(status_code=404, detail="缺陷跟踪配置不存在")

    for k, v in body.model_dump(exclude_none=True).items():
        if k == "config" and isinstance(v, dict):
            # 保留未修改的已加密敏感字段
            existing = tracker.config or {}
            for sk in ("api_token", "password", "secret", "webhook_url"):
                if v.get(sk) == "******":
                    v[sk] = existing.get(sk, "")
            v = encrypt_config(v)
        setattr(tracker, k, v)
    await db.commit()
    await db.refresh(tracker)
    return tracker


@router.delete("/bug-trackers/{tracker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bug_tracker(
    tracker_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    tracker = await db.get(BugTracker, tracker_id)
    if not tracker:
        raise HTTPException(status_code=404, detail="缺陷跟踪配置不存在")
    await db.delete(tracker)
    await db.commit()


# ── 一键创建缺陷 ─────────────────────────────────────────

@router.post("/runs/{run_id}/create-bug", response_model=BugResultOut)
async def create_bug_from_run(
    run_id: int,
    body: CreateBugRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """从执行记录一键创建缺陷到 Jira / 禅道"""
    # 获取执行记录
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    # 获取 bug tracker 配置
    tracker = await db.get(BugTracker, body.tracker_id)
    if not tracker:
        raise HTTPException(status_code=404, detail="缺陷跟踪配置不存在")
    if not tracker.is_enabled:
        raise HTTPException(status_code=400, detail="该缺陷跟踪配置已禁用")

    # 获取用例名称
    case = await db.get(TestCase, run.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    module = await db.get(Module, case.module_id)
    if not module:
        raise HTTPException(status_code=404, detail="用例所属模块不存在")
    if module.project_id != tracker.project_id:
        raise HTTPException(status_code=400, detail="缺陷跟踪配置不属于该执行记录所在项目")

    case_name = case.name

    # 准备错误信息
    error_message = run.error_message
    step_name = None
    step_index = None
    request_data = None
    response_data = None

    if body.step_index is not None:
        result = await db.execute(
            select(StepResult).where(
                StepResult.run_id == run_id,
                StepResult.step_index == body.step_index,
            )
        )
        step = result.scalar_one_or_none()
        if step:
            error_message = step.error_message or error_message
            step_name = step.name
            step_index = step.step_index
            request_data = step.request_data
            response_data = step.response_data

    # 构建标题和描述
    title = f"[ATP] {case_name}"
    if step_name:
        title += f" - {step_name}"
    title += " 执行失败"

    description = build_bug_description(
        run_id=run.id,
        case_name=case_name,
        environment=run.environment,
        error_message=error_message,
        step_name=step_name,
        step_index=step_index,
        request_data=request_data,
        response_data=response_data,
    )

    # 调用服务创建缺陷
    try:
        result = await create_bug(
            tracker_type=tracker.tracker_type.value,
            config=decrypt_config(tracker.config),
            title=title,
            description=description,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"创建缺陷失败: {str(e)}")

    # 将缺陷信息写回 result_summary 以便前端持久展示
    summary = dict(run.result_summary or {})
    summary["bug"] = {
        "bug_id": result["bug_id"],
        "bug_url": result["bug_url"],
        "title": title,
    }
    run.result_summary = summary
    await db.commit()

    return BugResultOut(**result)
