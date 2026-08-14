"""
通知配置管理 API

POST   /notifications           创建通知配置
GET    /notifications           通知配置列表
GET    /notifications/{id}      通知配置详情
PATCH  /notifications/{id}      更新通知配置
DELETE /notifications/{id}      删除通知配置
POST   /notifications/{id}/test 测试通知发送
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.notification import NotificationConfig, NotificationDelivery
from app.models.project import Project
from app.schemas.notification import (
    NotificationConfigCreate,
    NotificationConfigUpdate,
    NotificationConfigOut,
    NotificationDeliveryOut,
)
from app.api.deps import assert_project_access, require_engineer
from app.services.project_scope import scope_to_visible_projects
from app.models.user_project import ProjectRole
from app.services.audit import write_audit_log

from app.core.encryption import SENSITIVE_KEYS, mask_config, encrypt_config, decrypt_config
from app.services.notifier import _safe_delivery_error, validate_notification_channel_config

router = APIRouter(tags=["通知配置"])


@router.get("/notifications/deliveries", response_model=list[NotificationDeliveryOut])
async def list_notification_deliveries(
    project_id: int | None = Query(None),
    config_id: int | None = Query(None, ge=1),
    delivery_status: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    """查询项目范围内的脱敏通知投递记录。"""

    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    q = select(NotificationDelivery, NotificationConfig.name).outerjoin(
        NotificationConfig, NotificationConfig.id == NotificationDelivery.notification_config_id
    )
    q = scope_to_visible_projects(q, NotificationDelivery.project_id, user, project_id)
    if config_id is not None:
        q = q.where(NotificationDelivery.notification_config_id == config_id)
    if delivery_status:
        q = q.where(NotificationDelivery.status == delivery_status)
    q = q.order_by(NotificationDelivery.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).all()
    return [
        NotificationDeliveryOut(
            id=delivery.id,
            project_id=delivery.project_id,
            notification_config_id=delivery.notification_config_id,
            notification_name=name or "已删除通知",
            channel=delivery.channel,
            status=delivery.status,
            attempts=delivery.attempts,
            summary=delivery.summary or {},
            error_message=_safe_delivery_error(delivery.error_message),
            created_at=delivery.created_at,
        )
        for delivery, name in rows
    ]


@router.post("/notifications", response_model=NotificationConfigOut, status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: NotificationConfigCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.owner)
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        validate_notification_channel_config(body.channel, body.config)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    cfg = NotificationConfig(
        name=body.name,
        project_id=body.project_id,
        channel=body.channel,
        config=encrypt_config(body.config),
        is_enabled=body.is_enabled,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    await write_audit_log(
        db,
        action="notification_config_create",
        resource_type="notification_config",
        resource_id=cfg.id,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", ""),
        project_id=cfg.project_id,
        detail=f"创建通知配置: {cfg.name} ({cfg.channel.value})",
    )
    await db.commit()
    return _mask_notification(cfg)


def _mask_notification(cfg: NotificationConfig) -> dict:
    data = NotificationConfigOut.model_validate(cfg).model_dump()
    data["config"] = mask_config(data.get("config", {}))
    return data


@router.get("/notifications", response_model=list[NotificationConfigOut])
async def list_notifications(
    project_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    q = scope_to_visible_projects(select(NotificationConfig), NotificationConfig.project_id, user, project_id).order_by(
        NotificationConfig.created_at.desc()
    )
    result = await db.execute(q)
    return [_mask_notification(c) for c in result.scalars().all()]


@router.get("/notifications/{cfg_id}", response_model=NotificationConfigOut)
async def get_notification(
    cfg_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    cfg = await db.get(NotificationConfig, cfg_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="通知配置不存在")
    await assert_project_access(db, user, cfg.project_id, ProjectRole.viewer)
    return _mask_notification(cfg)


@router.patch("/notifications/{cfg_id}", response_model=NotificationConfigOut)
async def update_notification(
    cfg_id: int,
    body: NotificationConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    cfg = await db.get(NotificationConfig, cfg_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="通知配置不存在")
    await assert_project_access(db, user, cfg.project_id, ProjectRole.owner)

    updates = body.model_dump(exclude_none=True)
    next_channel = updates.get("channel", cfg.channel)
    next_config = decrypt_config(cfg.config or {})
    if "config" in updates and isinstance(updates["config"], dict):
        merged = dict(next_config)
        for config_key, config_value in updates["config"].items():
            if config_key in SENSITIVE_KEYS and config_value == "******":
                continue
            merged[config_key] = config_value
        next_config = merged
    if "config" in updates or "channel" in updates:
        try:
            validate_notification_channel_config(next_channel, next_config)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    if "config" in updates:
        updates["config"] = encrypt_config(next_config)
    for k, v in updates.items():
        setattr(cfg, k, v)
    await db.commit()
    await db.refresh(cfg)
    await write_audit_log(
        db,
        action="notification_config_update",
        resource_type="notification_config",
        resource_id=cfg.id,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", ""),
        project_id=cfg.project_id,
        detail=f"更新通知配置: {cfg.name}",
    )
    await db.commit()
    return _mask_notification(cfg)


@router.delete("/notifications/{cfg_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    cfg_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    cfg = await db.get(NotificationConfig, cfg_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="通知配置不存在")
    await assert_project_access(db, user, cfg.project_id, ProjectRole.owner)
    project_id = cfg.project_id
    cfg_name = cfg.name
    await db.delete(cfg)
    await write_audit_log(
        db,
        action="notification_config_delete",
        resource_type="notification_config",
        resource_id=cfg_id,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", ""),
        project_id=project_id,
        detail=f"删除通知配置: {cfg_name}",
    )
    await db.commit()


@router.post("/notifications/{cfg_id}/test", status_code=status.HTTP_200_OK)
async def test_notification(
    cfg_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    """发送测试通知"""
    cfg = await db.get(NotificationConfig, cfg_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="通知配置不存在")
    await assert_project_access(db, user, cfg.project_id, ProjectRole.editor)

    from app.services.notifier import _safe_exception_message, persist_notification_delivery, send_notification_channel

    test_summary = {
        "title": "ATP 通知测试",
        "status": "passed",
        "total": 10,
        "passed": 9,
        "failed": 1,
        "error": 0,
        "duration_ms": 5000,
        "trigger_type": "manual",
    }
    try:
        real_config = decrypt_config(cfg.config)
        language = real_config.get("language")
        test_summary["title"] = "ATP notification test" if language == "en-US" else "ATP 通知测试"
        attempts = await send_notification_channel(cfg.channel, real_config, test_summary)
        await persist_notification_delivery(db, cfg, test_summary, status="sent", attempts=attempts)
        return {"message": "测试通知已发送", "attempts": attempts}
    except Exception as e:
        await persist_notification_delivery(
            db,
            cfg,
            test_summary,
            status="failed",
            attempts=getattr(e, "attempts", 1),
            error_message=_safe_exception_message(e),
        )
        raise HTTPException(status_code=500, detail=f"通知发送失败: {_safe_exception_message(e)}")
