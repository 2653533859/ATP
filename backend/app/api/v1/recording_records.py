"""录制历史、草稿与 Web 录制产物（Trace / HAR / 报告）查询恢复接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.case import TestCase
from app.models.device import Device
from app.models.project import Module, Project
from app.models.recording_record import RecordingRecord
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.recording_record import (
    RecordingKind,
    RecordingRecordCreate,
    RecordingRecordOut,
    RecordingRecordUpdate,
    RecordingStatus,
)
from app.services.recording_records import (
    RecordingSessionConflictError,
    create_or_upsert_recording_record,
    delete_recording_record,
    list_recording_records,
    serialize_recording_record,
    update_recording_record,
)

router = APIRouter(prefix="/recording-records", tags=["录制记录"])


async def _ensure_project_exists(db: AsyncSession, project_id: int) -> None:
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")


async def _validate_case_project(db: AsyncSession, case_id: int, project_id: int) -> None:
    row = (
        await db.execute(
            select(TestCase.id, Module.project_id)
            .join(Module, TestCase.module_id == Module.id)
            .where(TestCase.id == case_id)
        )
    ).first()
    if row is None or row[1] != project_id:
        raise HTTPException(status_code=400, detail="关联用例不存在或不属于当前项目")


async def _validate_device_exists(db: AsyncSession, device_id: int) -> None:
    if await db.get(Device, device_id) is None:
        raise HTTPException(status_code=400, detail="关联设备不存在")


@router.get("", response_model=list[RecordingRecordOut])
async def get_recording_records(
    project_id: int = Query(..., gt=0),
    kind: RecordingKind | None = Query(default=None),
    status_filter: RecordingStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, project_id, ProjectRole.viewer)
    await _ensure_project_exists(db, project_id)
    records = await list_recording_records(
        db,
        project_id=project_id,
        kind=kind,
        status=status_filter,
        limit=limit,
    )
    return [await serialize_recording_record(item) for item in records]


@router.post("", response_model=RecordingRecordOut, status_code=status.HTTP_201_CREATED)
async def create_recording_record(
    payload: RecordingRecordCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, payload.project_id, ProjectRole.editor)
    await _ensure_project_exists(db, payload.project_id)
    if payload.case_id is not None:
        await _validate_case_project(db, payload.case_id, payload.project_id)
    if payload.device_id is not None:
        await _validate_device_exists(db, payload.device_id)
    try:
        record = await create_or_upsert_recording_record(db, payload, user.id)
    except RecordingSessionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await serialize_recording_record(record)


@router.get("/{record_id}", response_model=RecordingRecordOut)
async def get_recording_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    record = await db.get(RecordingRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="录制记录不存在")
    await assert_project_access(db, user, record.project_id, ProjectRole.viewer)
    return await serialize_recording_record(record)


@router.patch("/{record_id}", response_model=RecordingRecordOut)
async def patch_recording_record(
    record_id: int,
    payload: RecordingRecordUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    record = await db.get(RecordingRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="录制记录不存在")
    await assert_project_access(db, user, record.project_id, ProjectRole.editor)
    if payload.case_id is not None:
        await _validate_case_project(db, payload.case_id, record.project_id)
    if payload.device_id is not None:
        await _validate_device_exists(db, payload.device_id)
    updated = await update_recording_record(db, record, payload)
    return await serialize_recording_record(updated)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_recording_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    record = await db.get(RecordingRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="录制记录不存在")
    await assert_project_access(db, user, record.project_id, ProjectRole.editor)
    await delete_recording_record(db, record)
