"""cases 包 - 审批工作流 + 快照/回滚。"""
from __future__ import annotations

import copy
from datetime import datetime, timezone

import app.api.v1.cases as _cases
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.case import CaseSnapshot, CaseStatus, CaseType
from app.models.user import User
from app.schemas.case import (
    CaseCloneFromSnapshotRequest,
    CaseSnapshotDiffOut,
    CaseSnapshotImport,
    CaseSnapshotManualCreate,
    CaseSnapshotOut,
    CaseWorkflowRequest,
    PaginatedSnapshotsOut,
    TestCaseDetailOut,
)

router = APIRouter(tags=["用例管理"])


@router.post("/cases/{case_id}/submit-review", response_model=TestCaseDetailOut)
async def submit_review(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    if case.status == CaseStatus.deprecated:
        raise HTTPException(status_code=409, detail="废弃用例不能提交审核")
    case.review_status = "pending"
    case.submitted_at = datetime.now(timezone.utc)
    case.reviewed_at = None
    case.reviewed_by = None
    case.review_comment = body.comment
    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/approve", response_model=TestCaseDetailOut)
async def approve_case(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    if case.review_status != "pending":
        raise HTTPException(status_code=409, detail="只有待审核用例可批准")
    if case.status == CaseStatus.deprecated:
        raise HTTPException(status_code=409, detail="废弃用例不能批准")
    case.review_status = "approved"
    case.status = CaseStatus.active
    case.reviewed_at = datetime.now(timezone.utc)
    case.reviewed_by = current_user.id
    case.review_comment = body.comment
    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/reject", response_model=TestCaseDetailOut)
async def reject_case(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    if case.review_status != "pending":
        raise HTTPException(status_code=409, detail="只有待审核用例可驳回")
    case.review_status = "rejected"
    case.status = CaseStatus.draft
    case.reviewed_at = datetime.now(timezone.utc)
    case.reviewed_by = current_user.id
    case.review_comment = body.comment
    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/deprecate", response_model=TestCaseDetailOut)
async def deprecate_case(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    if case.status == CaseStatus.deprecated:
        raise HTTPException(status_code=409, detail="用例已经废弃")
    case.status = CaseStatus.deprecated
    case.review_comment = body.comment or case.review_comment
    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/reactivate", response_model=TestCaseDetailOut)
async def reactivate_case(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    if case.status != CaseStatus.deprecated:
        raise HTTPException(status_code=409, detail="只有废弃用例可重新激活")
    if case.review_status != "approved":
        raise HTTPException(status_code=409, detail="仅审核通过的用例可重新激活")
    case.status = CaseStatus.active
    case.review_comment = body.comment or case.review_comment
    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)


@router.get("/cases/{case_id}/snapshots", response_model=PaginatedSnapshotsOut)
async def list_snapshots(
    case_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="按版本号或快照 name 模糊匹配"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    await _cases._get_case_detail_or_404(db, case_id)

    base_where = [CaseSnapshot.case_id == case_id]
    if q:
        keyword = q.strip()
        if keyword:
            conds = [CaseSnapshot.name.ilike(f"%{keyword}%")]
            if keyword.isdigit():
                conds.append(CaseSnapshot.version == int(keyword))
            base_where.append(or_(*conds))

    total = await db.scalar(
        select(func.count()).select_from(
            select(CaseSnapshot.id).where(*base_where).subquery()
        )
    )
    result = await db.execute(
        select(CaseSnapshot, User.username)
        .outerjoin(User, CaseSnapshot.updated_by == User.id)
        .where(*base_where)
        .order_by(CaseSnapshot.version.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for snapshot, username in result.all():
        out = CaseSnapshotOut.model_validate(snapshot)
        out.updated_by_name = username or ""
        items.append(out)
    return PaginatedSnapshotsOut(items=items, total=total or 0, page=page, page_size=page_size)


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
    case = await _cases._get_case_detail_or_404(db, case_id)
    snapshot = await db.get(CaseSnapshot, snapshot_id)
    if not snapshot or snapshot.case_id != case_id:
        raise HTTPException(status_code=404, detail="快照不存在")

    db.add(_cases._build_snapshot(case, await _cases._next_snapshot_version(db, case_id), current_user.id))
    await _cases._enforce_snapshot_retention(db, case_id)

    data = snapshot.snapshot_data or {}
    case.name = data.get("name", snapshot.name)
    case.description = data.get("description", snapshot.description)
    case.summary = data.get("summary", case.name)
    case.case_type = CaseType(data.get("case_type", case.case_type.value))
    case.status = CaseStatus(data.get("status", case.status.value))
    case.priority = data.get("priority", case.priority)
    case.case_level = data.get("case_level", case.case_level)
    case.review_status = data.get("review_status", case.review_status)
    case.automation_status = data.get("automation_status", case.automation_status)
    case.owner_id = data.get("owner_id", case.owner_id)
    case.preconditions = _cases._normalize_string_list(data.get("preconditions", []))
    case.postconditions = _cases._normalize_string_list(data.get("postconditions", []))
    case.tags = _cases._normalize_string_list(data.get("tags", snapshot.tags or []))
    case.config = copy.deepcopy(data.get("config", snapshot.config or {}))
    await _cases._replace_case_steps(
        db,
        case,
        data.get("steps") or _cases._derive_steps_from_config(case.case_type, case.config, case.name),
    )
    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)


# ============================================================================
# D.1 用例快照增强 — 手动创建 / Diff / 导出 / 导入 / 克隆
# ============================================================================


@router.post("/cases/{case_id}/snapshots", response_model=CaseSnapshotOut, status_code=201)
async def create_snapshot_manual(
    case_id: int,
    body: CaseSnapshotManualCreate | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动创建当前用例的版本快照（不依赖编辑触发）。"""
    case = await _cases._get_case_detail_or_404(db, case_id)
    snapshot = _cases._build_snapshot(case, await _cases._next_snapshot_version(db, case_id), current_user.id)
    if body and body.remark:
        sd = dict(snapshot.snapshot_data or {})
        sd["remark"] = body.remark
        snapshot.snapshot_data = sd
    db.add(snapshot)
    await db.flush()
    await _cases._enforce_snapshot_retention(db, case_id)
    await db.commit()
    refreshed = await db.get(CaseSnapshot, snapshot.id)
    out = CaseSnapshotOut.model_validate(refreshed)
    out.updated_by_name = current_user.username or ""
    return out


@router.get("/cases/{case_id}/snapshots/diff", response_model=CaseSnapshotDiffOut)
async def diff_snapshots(
    case_id: int,
    from_version: int = Query(..., alias="from", ge=1),
    to_version: int = Query(..., alias="to", ge=1),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """比较两个版本，返回字段级 diff。to_version=0 时与当前用例对比。"""
    await _cases._get_case_detail_or_404(db, case_id)

    from_snap = (await db.execute(
        select(CaseSnapshot).where(CaseSnapshot.case_id == case_id, CaseSnapshot.version == from_version)
    )).scalar_one_or_none()
    if not from_snap:
        raise HTTPException(status_code=404, detail=f"快照版本 {from_version} 不存在")
    to_snap = (await db.execute(
        select(CaseSnapshot).where(CaseSnapshot.case_id == case_id, CaseSnapshot.version == to_version)
    )).scalar_one_or_none()
    if not to_snap:
        raise HTTPException(status_code=404, detail=f"快照版本 {to_version} 不存在")

    src = from_snap.snapshot_data or {}
    dst = to_snap.snapshot_data or {}
    changes: dict = {}
    keys = set(src.keys()) | set(dst.keys())
    for key in sorted(keys):
        if src.get(key) != dst.get(key):
            changes[key] = {"from": src.get(key), "to": dst.get(key)}
    return CaseSnapshotDiffOut(from_version=from_version, to_version=to_version, changes=changes)


@router.get("/cases/{case_id}/snapshots/{snapshot_id}/export")
async def export_snapshot(
    case_id: int,
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """导出单个快照为 JSON 附件。"""
    snapshot = await db.get(CaseSnapshot, snapshot_id)
    if not snapshot or snapshot.case_id != case_id:
        raise HTTPException(status_code=404, detail="快照不存在")
    payload = {
        "case_id": snapshot.case_id,
        "version": snapshot.version,
        "name": snapshot.name,
        "description": snapshot.description,
        "tags": snapshot.tags,
        "config": snapshot.config,
        "snapshot_data": snapshot.snapshot_data,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
    filename = f"case-{case_id}-snapshot-v{snapshot.version}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/cases/{case_id}/snapshots/import", response_model=CaseSnapshotOut, status_code=201)
async def import_snapshot(
    case_id: int,
    body: CaseSnapshotImport,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从 JSON 内容导入为新版本（不改变当前用例数据）。"""
    case = await _cases._get_case_detail_or_404(db, case_id)
    version = await _cases._next_snapshot_version(db, case_id)
    snap_data = body.snapshot_data or {}
    snapshot = CaseSnapshot(
        case_id=case_id,
        version=version,
        name=body.name or snap_data.get("name") or case.name,
        description=body.description or snap_data.get("description"),
        tags=_cases._normalize_string_list(body.tags or snap_data.get("tags") or []),
        config=copy.deepcopy(body.config or snap_data.get("config") or {}),
        snapshot_data=snap_data,
        updated_by=current_user.id,
    )
    db.add(snapshot)
    await db.flush()
    await _cases._enforce_snapshot_retention(db, case_id)
    await db.commit()
    refreshed = await db.get(CaseSnapshot, snapshot.id)
    out = CaseSnapshotOut.model_validate(refreshed)
    out.updated_by_name = current_user.username or ""
    return out


@router.post("/cases/{case_id}/snapshots/{snapshot_id}/clone", response_model=TestCaseDetailOut, status_code=201)
async def clone_case_from_snapshot(
    case_id: int,
    snapshot_id: int,
    body: CaseCloneFromSnapshotRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从历史快照创建新用例（不修改原用例）。"""
    from app.models.case import TestCase

    snapshot = await db.get(CaseSnapshot, snapshot_id)
    if not snapshot or snapshot.case_id != case_id:
        raise HTTPException(status_code=404, detail="快照不存在")
    source = await _cases._get_case_detail_or_404(db, case_id)

    data = snapshot.snapshot_data or {}
    module_id = (body.module_id if body else None) or source.module_id
    module = await _cases._get_module_for_case_code(db, module_id)
    case_type = CaseType(data.get("case_type", source.case_type.value))
    new_code = await _cases._generate_case_code(db, module, case_type)
    new_name = (body.name if body else None) or f"{data.get('name', source.name)} (clone v{snapshot.version})"

    new_case = TestCase(
        name=new_name,
        description=data.get("description", source.description),
        case_code=new_code,
        summary=data.get("summary", new_name) or new_name,
        preconditions=_cases._normalize_string_list(data.get("preconditions") or []),
        postconditions=_cases._normalize_string_list(data.get("postconditions") or []),
        case_type=case_type,
        status=CaseStatus.draft,
        priority=data.get("priority", source.priority),
        case_level=data.get("case_level", source.case_level),
        review_status="pending",
        automation_status=data.get("automation_status", source.automation_status),
        tags=_cases._normalize_string_list(data.get("tags") or []),
        module_id=module.id,
        creator_id=current_user.id,
        owner_id=current_user.id,
        config=copy.deepcopy(data.get("config") or {}),
    )
    db.add(new_case)
    await db.flush()
    await _cases._replace_case_steps(
        db,
        new_case,
        data.get("steps") or _cases._derive_steps_from_config(new_case.case_type, new_case.config, new_case.name),
    )
    await db.commit()
    return await _cases._get_case_detail_or_404(db, new_case.id)
