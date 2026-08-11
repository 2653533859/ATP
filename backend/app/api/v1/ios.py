"""iOS device and IPA asset APIs.

The API deliberately keeps Appium/XCUITest execution behind a worker boundary;
the web process only registers devices/assets and manages leases.
"""

from __future__ import annotations

import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user, require_engineer
from app.services.project_scope import scope_to_visible_projects
from app.core.database import get_db
from app.core.minio_client import delete_file, ensure_bucket, presigned_url, upload_file
from app.models.ios import IosApp, IosDevice, IosDeviceStatus
from app.models.project import Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.device_lease import DeviceLeaseAcquireIn, DeviceLeaseOut, DeviceLeaseTokenIn
from app.schemas.ios import IosAppOut, IosAppUpdate, IosDeviceCreate, IosDeviceOut, IosDeviceUpdate
from app.services.ios_device_leases import (
    IosDeviceLeaseConflict,
    acquire_ios_device_lease,
    heartbeat_ios_device_lease,
    release_ios_device_lease,
)

router = APIRouter(tags=["iOS/Appium"])

_MAX_IPA_SIZE = 500 * 1024 * 1024
_UPLOAD_CHUNK_SIZE = 1024 * 1024


def _lease_error(exc: IosDeviceLeaseConflict) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


async def _save_upload(file: UploadFile) -> tuple[str, int]:
    temp = tempfile.NamedTemporaryFile(prefix="ios-upload-", suffix=".ipa", delete=False)
    total = 0
    try:
        with temp:
            while chunk := await file.read(_UPLOAD_CHUNK_SIZE):
                total += len(chunk)
                if total > _MAX_IPA_SIZE:
                    raise HTTPException(status_code=413, detail="IPA 文件超过 500MB 限制")
                temp.write(chunk)
        return temp.name, total
    except Exception:
        try:
            os.remove(temp.name)
        except OSError:
            pass
        raise


def _ipa_object_name(project_id: int, filename: str) -> str:
    return f"ios-apps/projects/{project_id}/{uuid.uuid4().hex[:8]}_{filename}"


@router.get("/ios-devices", response_model=list[IosDeviceOut])
async def list_ios_devices(
    status_filter: IosDeviceStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(IosDevice).order_by(IosDevice.status.asc(), IosDevice.updated_at.desc())
    if status_filter is not None:
        query = query.where(IosDevice.status == status_filter)
    return (await db.execute(query)).scalars().all()


@router.post("/ios-devices", response_model=IosDeviceOut, status_code=status.HTTP_201_CREATED)
async def create_ios_device(
    body: IosDeviceCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_engineer),
):
    existing = (await db.execute(select(IosDevice).where(IosDevice.udid == body.udid))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="UDID 已注册")
    device = IosDevice(**body.model_dump(exclude={"appium_server_url"}), appium_server_url=str(body.appium_server_url))
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


@router.patch("/ios-devices/{device_id}", response_model=IosDeviceOut)
async def update_ios_device(
    device_id: int,
    body: IosDeviceUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_engineer),
):
    device = await db.get(IosDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="iOS 设备不存在")
    values = body.model_dump(exclude_none=True)
    if "appium_server_url" in values:
        values["appium_server_url"] = str(values["appium_server_url"])
    for key, value in values.items():
        setattr(device, key, value)
    await db.commit()
    await db.refresh(device)
    return device


@router.delete("/ios-devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ios_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_engineer),
):
    device = await db.get(IosDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="iOS 设备不存在")
    await db.delete(device)
    await db.commit()


@router.post("/ios-devices/{device_id}/lease", response_model=DeviceLeaseOut)
async def acquire_ios_lease(
    device_id: int,
    body: DeviceLeaseAcquireIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    try:
        lease = await acquire_ios_device_lease(
            db,
            device_id,
            owner_id=current_user.id,
            owner_label=body.owner_label,
            ttl_seconds=body.ttl_seconds,
        )
    except (IosDeviceLeaseConflict, LookupError) as exc:
        raise _lease_error(exc) from exc
    await db.commit()
    await db.refresh(lease)
    return lease


@router.post("/ios-devices/{device_id}/lease/heartbeat", response_model=DeviceLeaseOut)
async def heartbeat_ios_lease(
    device_id: int,
    body: DeviceLeaseTokenIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_engineer),
):
    try:
        lease = await heartbeat_ios_device_lease(db, device_id, body.lease_token)
    except IosDeviceLeaseConflict as exc:
        raise _lease_error(exc) from exc
    await db.commit()
    await db.refresh(lease)
    response = DeviceLeaseOut.model_validate(lease)
    response.lease_token = None
    return response


@router.delete("/ios-devices/{device_id}/lease", status_code=status.HTTP_204_NO_CONTENT)
async def release_ios_lease(
    device_id: int,
    body: DeviceLeaseTokenIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_engineer),
):
    if not await release_ios_device_lease(db, device_id, body.lease_token):
        raise HTTPException(status_code=404, detail="iOS 设备租约不存在")
    await db.commit()


@router.post("/ios-apps", response_model=IosAppOut, status_code=status.HTTP_201_CREATED)
async def upload_ios_app(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    bundle_id: str | None = Form(None),
    version_name: str | None = Form(None),
    signing_identity: str | None = Form(None),
    provisioning_profile: str | None = Form(None),
    description: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    filename = file.filename or "unknown.ipa"
    if not filename.lower().endswith(".ipa"):
        raise HTTPException(status_code=400, detail="仅支持 .ipa 文件")
    temp_path = ""
    object_name = _ipa_object_name(project_id, filename)
    try:
        temp_path, file_size = await _save_upload(file)
        ensure_bucket()
        upload_file(object_name, temp_path, content_type="application/octet-stream")
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass
        await file.close()
    app = IosApp(
        project_id=project_id,
        filename=filename,
        bundle_id=bundle_id,
        version_name=version_name,
        file_size=file_size,
        object_name=object_name,
        signing_identity=signing_identity,
        provisioning_profile=provisioning_profile,
        description=description,
        uploaded_by=current_user.id,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


@router.get("/ios-apps", response_model=list[IosAppOut])
async def list_ios_apps(
    project_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    query = scope_to_visible_projects(select(IosApp), IosApp.project_id, user, project_id).order_by(
        IosApp.created_at.desc()
    )
    return (await db.execute(query)).scalars().all()


@router.get("/ios-apps/{app_id}", response_model=IosAppOut)
async def get_ios_app(app_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    app = await db.get(IosApp, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="iOS 应用不存在")
    await assert_project_access(db, user, app.project_id, ProjectRole.viewer)
    return app


@router.patch("/ios-apps/{app_id}", response_model=IosAppOut)
async def update_ios_app(
    app_id: int,
    body: IosAppUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    app = await db.get(IosApp, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="iOS 应用不存在")
    await assert_project_access(db, user, app.project_id, ProjectRole.editor)
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(app, key, value)
    await db.commit()
    await db.refresh(app)
    return app


@router.delete("/ios-apps/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ios_app(app_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_engineer)):
    app = await db.get(IosApp, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="iOS 应用不存在")
    await assert_project_access(db, user, app.project_id, ProjectRole.editor)
    try:
        delete_file(app.object_name)
    except Exception:
        pass
    await db.delete(app)
    await db.commit()


@router.get("/ios-apps/{app_id}/download")
async def download_ios_app(app_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    app = await db.get(IosApp, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="iOS 应用不存在")
    await assert_project_access(db, user, app.project_id, ProjectRole.viewer)
    return {"url": presigned_url(app.object_name, expires_seconds=3600), "filename": app.filename}
