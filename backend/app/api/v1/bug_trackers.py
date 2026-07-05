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
from app.core.minio_client import read_bytes
from app.models.bug_tracker import BugTracker
from app.models.case import TestRun, StepResult, TestCase
from app.models.project import Project, Module
from app.schemas.bug_tracker import (
    BugTrackerConnectionTestOut,
    BugTrackerConnectionTestRequest,
    BugStatusOut,
    BugTrackerCreate, BugTrackerUpdate, BugTrackerOut,
    CreateBugRequest, LinkBugRequest, BugResultOut,
)
from app.api.deps import assert_project_access, require_engineer, get_current_user
from app.models.user_project import ProjectRole
from app.services.bug_reporter import (
    create_bug,
    build_bug_description,
    find_duplicate_bug,
    get_bug_status,
    test_connection,
    upload_attachment,
)
from app.services.audit import write_audit_log
from app.core.encryption import mask_config, encrypt_config, decrypt_config

router = APIRouter(tags=["缺陷跟踪"])


def _mask_tracker(tracker: BugTracker) -> dict:
    data = BugTrackerOut.model_validate(tracker).model_dump()
    data["config"] = mask_config(data.get("config", {}))
    data["field_mapping"] = data.get("field_mapping", {})
    return data


def _merge_sensitive_config(existing_config: dict, incoming_config: dict) -> dict:
    merged = dict(existing_config)
    merged.update(incoming_config)
    for key in ("api_token", "password", "secret", "token", "webhook_url"):
        if key not in incoming_config or incoming_config.get(key) == "******":
            merged[key] = existing_config.get(key, "")
    return merged


def _get_tracker_or_404(tracker: BugTracker | None) -> BugTracker:
    if not tracker:
        raise HTTPException(status_code=404, detail="缺陷跟踪配置不存在")
    return tracker


# ── CRUD ──────────────────────────────────────────────────

@router.post("/bug-trackers", response_model=BugTrackerOut, status_code=status.HTTP_201_CREATED)
async def create_bug_tracker(
    body: BugTrackerCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.owner)
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    tracker = BugTracker(
        name=body.name,
        project_id=body.project_id,
        tracker_type=body.tracker_type,
        config=encrypt_config(body.config),
        field_mapping=body.field_mapping,
        is_enabled=body.is_enabled,
    )
    db.add(tracker)
    await db.commit()
    await db.refresh(tracker)
    await write_audit_log(
        db,
        action="bug_tracker_create",
        resource_type="bug_tracker",
        resource_id=tracker.id,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", ""),
        project_id=tracker.project_id,
        detail=f"创建缺陷跟踪配置: {tracker.name} ({tracker.tracker_type.value})",
    )
    await db.commit()
    return _mask_tracker(tracker)


@router.get("/bug-trackers", response_model=list[BugTrackerOut])
async def list_bug_trackers(
    project_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    q = select(BugTracker).order_by(BugTracker.created_at.desc())
    if project_id is not None:
        q = q.where(BugTracker.project_id == project_id)
    result = await db.execute(q)
    return [_mask_tracker(t) for t in result.scalars().all()]


@router.get("/bug-trackers/{tracker_id}", response_model=BugTrackerOut)
async def get_bug_tracker(
    tracker_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    tracker = _get_tracker_or_404(await db.get(BugTracker, tracker_id))
    await assert_project_access(db, user, tracker.project_id, ProjectRole.viewer)
    return _mask_tracker(tracker)


@router.patch("/bug-trackers/{tracker_id}", response_model=BugTrackerOut)
async def update_bug_tracker(
    tracker_id: int,
    body: BugTrackerUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    tracker = _get_tracker_or_404(await db.get(BugTracker, tracker_id))
    await assert_project_access(db, user, tracker.project_id, ProjectRole.owner)

    existing_config = decrypt_config(tracker.config or {})
    for k, v in body.model_dump(exclude_none=True).items():
        if k == "config" and isinstance(v, dict):
            v = encrypt_config(_merge_sensitive_config(existing_config, v))
        setattr(tracker, k, v)
    await db.commit()
    await db.refresh(tracker)
    await write_audit_log(
        db,
        action="bug_tracker_update",
        resource_type="bug_tracker",
        resource_id=tracker.id,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", ""),
        project_id=tracker.project_id,
        detail=f"更新缺陷跟踪配置: {tracker.name}",
    )
    await db.commit()
    return _mask_tracker(tracker)


@router.delete("/bug-trackers/{tracker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bug_tracker(
    tracker_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    tracker = _get_tracker_or_404(await db.get(BugTracker, tracker_id))
    await assert_project_access(db, user, tracker.project_id, ProjectRole.owner)
    project_id = tracker.project_id
    tracker_name = tracker.name
    await db.delete(tracker)
    await write_audit_log(
        db,
        action="bug_tracker_delete",
        resource_type="bug_tracker",
        resource_id=tracker_id,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", ""),
        project_id=project_id,
        detail=f"删除缺陷跟踪配置: {tracker_name}",
    )
    await db.commit()


@router.post("/bug-trackers/test-connection", response_model=BugTrackerConnectionTestOut)
async def test_bug_tracker_connection(
    body: BugTrackerConnectionTestRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    try:
        config = body.config
        if body.tracker_id is not None:
            tracker = _get_tracker_or_404(await db.get(BugTracker, body.tracker_id))
            if tracker.tracker_type != body.tracker_type:
                raise HTTPException(status_code=400, detail="缺陷跟踪平台类型不匹配")
            existing_config = decrypt_config(tracker.config or {})
            config = _merge_sensitive_config(existing_config, body.config)
        result = await test_connection(body.tracker_type.value, config)
        return BugTrackerConnectionTestOut(**result)
    except HTTPException as exc:
        return BugTrackerConnectionTestOut(ok=False, message=str(exc.detail))
    except Exception as exc:
        return BugTrackerConnectionTestOut(ok=False, message=str(exc))


@router.get("/runs/{run_id}/bug-status", response_model=BugStatusOut)
async def get_run_bug_status(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    bug_info = (run.result_summary or {}).get("bug")
    if not bug_info:
        raise HTTPException(status_code=404, detail="当前执行记录未关联缺陷")

    tracker_id = bug_info.get("tracker_id")
    if tracker_id is not None:
        tracker = _get_tracker_or_404(await db.get(BugTracker, tracker_id))
    else:
        result = await db.execute(
            select(BugTracker, Module)
            .join(Module, Module.project_id == BugTracker.project_id)
            .join(TestCase, TestCase.module_id == Module.id)
            .where(TestCase.id == run.case_id, BugTracker.is_enabled.is_(True))
            .limit(1)
        )
        tracker_row = result.first()
        if not tracker_row:
            raise HTTPException(status_code=404, detail="未找到可用的缺陷跟踪配置")
        tracker = tracker_row[0]

    tracker_config = decrypt_config(tracker.config)
    status_result = await get_bug_status(
        tracker_type=tracker.tracker_type.value,
        config=tracker_config,
        bug_id=bug_info["bug_id"],
    )

    summary = dict(run.result_summary or {})
    summary["bug"] = {
        **bug_info,
        "status": status_result["status"],
        "bug_url": status_result.get("bug_url") or bug_info.get("bug_url"),
    }
    run.result_summary = summary
    await write_audit_log(
        db,
        action="run_bug_link",
        resource_type="test_run",
        resource_id=run.id,
        user_id=getattr(_, "id", None),
        username=getattr(_, "username", ""),
        project_id=tracker.project_id,
        detail=f"执行记录 {run.id} 刷新缺陷状态: {bug_info['bug_id']}",
    )
    await db.commit()

    return BugStatusOut(**status_result)


# ── 一键创建缺陷 ─────────────────────────────────────────

@router.post("/runs/{run_id}/link-bug", response_model=BugStatusOut)
async def link_bug_to_run(
    run_id: int,
    body: LinkBugRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    tracker = _get_tracker_or_404(await db.get(BugTracker, body.tracker_id))
    case = await db.get(TestCase, run.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    module = await db.get(Module, case.module_id)
    if not module:
        raise HTTPException(status_code=404, detail="用例所属模块不存在")
    if module.project_id != tracker.project_id:
        raise HTTPException(status_code=400, detail="缺陷跟踪配置不属于该执行记录所在项目")
    await assert_project_access(db, current_user, module.project_id, ProjectRole.editor)

    bug_url = body.bug_url or ""
    status_text = body.status or "linked"
    summary = dict(run.result_summary or {})
    summary["bug"] = {
        "bug_id": body.bug_id,
        "bug_url": bug_url,
        "title": body.title or body.bug_id,
        "status": status_text,
        "tracker_id": tracker.id,
        "linked_manually": True,
    }
    run.result_summary = summary
    await db.commit()

    return BugStatusOut(bug_id=body.bug_id, status=status_text, bug_url=bug_url)

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
    tracker = _get_tracker_or_404(await db.get(BugTracker, body.tracker_id))
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

    tracker_config = decrypt_config(tracker.config)

    duplicate = await find_duplicate_bug(
        tracker_type=tracker.tracker_type.value,
        config=tracker_config,
        title=title,
    )
    if duplicate:
        summary = dict(run.result_summary or {})
        summary["bug"] = {
            "bug_id": duplicate["bug_id"],
            "bug_url": duplicate["bug_url"],
            "title": duplicate.get("title") or title,
            "duplicate_of": duplicate["bug_id"],
            "attachment_uploaded": False,
            "tracker_id": tracker.id,
        }
        run.result_summary = summary
        await write_audit_log(
            db,
            action="run_bug_create_duplicate",
            resource_type="test_run",
            resource_id=run.id,
            user_id=getattr(_, "id", None),
            username=getattr(_, "username", ""),
            project_id=tracker.project_id,
            detail=f"执行记录 {run.id} 命中重复缺陷: {duplicate['bug_id']}",
        )
        await db.commit()
        return BugResultOut(**duplicate, duplicate_of=duplicate["bug_id"], attachment_uploaded=False)

    # 调用服务创建缺陷
    try:
        result = await create_bug(
            tracker_type=tracker.tracker_type.value,
            config=tracker_config,
            title=title,
            description=description,
            field_mapping=tracker.field_mapping or {},
            override_product_id=body.override_product_id,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"创建缺陷失败: {str(e)}")

    attachment_uploaded = False
    screenshot_source = None
    if body.step_index is not None and step_name is not None:
        result_step = await db.execute(
            select(StepResult).where(
                StepResult.run_id == run_id,
                StepResult.step_index == body.step_index,
            )
        )
        step = result_step.scalar_one_or_none()
        screenshot_source = step.screenshot_url if step else None
    if not screenshot_source:
        result_step = await db.execute(
            select(StepResult).where(StepResult.run_id == run_id, StepResult.screenshot_url.isnot(None)).order_by(StepResult.step_index)
        )
        first_step_with_image = result_step.scalars().first()
        screenshot_source = first_step_with_image.screenshot_url if first_step_with_image else None

    if screenshot_source:
        from app.api.v1.exports import _extract_minio_object
        object_name = _extract_minio_object(screenshot_source)
        if object_name:
            try:
                attachment_uploaded = await upload_attachment(
                    tracker_type=tracker.tracker_type.value,
                    config=tracker_config,
                    bug_id=result["bug_id"],
                    filename=f"run-{run_id}-screenshot.png",
                    content=read_bytes(object_name),
                )
            except Exception:
                attachment_uploaded = False

    # 将缺陷信息写回 result_summary 以便前端持久展示
    summary = dict(run.result_summary or {})
    summary["bug"] = {
        "bug_id": result["bug_id"],
        "bug_url": result["bug_url"],
        "title": title,
        "duplicate_of": None,
        "attachment_uploaded": attachment_uploaded,
        "tracker_id": tracker.id,
    }
    run.result_summary = summary
    await write_audit_log(
        db,
        action="run_bug_create",
        resource_type="test_run",
        resource_id=run.id,
        user_id=getattr(_, "id", None),
        username=getattr(_, "username", ""),
        project_id=tracker.project_id,
        detail=f"执行记录 {run.id} 创建缺陷: {result['bug_id']}",
    )
    await db.commit()

    return BugResultOut(**result, duplicate_of=None, attachment_uploaded=attachment_uploaded)
