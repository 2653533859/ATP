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
from app.models.notification import NotificationConfig
from app.models.project import Project
from app.schemas.notification import (
    NotificationConfigCreate,
    NotificationConfigUpdate,
    NotificationConfigOut,
)
from app.api.deps import assert_project_access, require_engineer
from app.models.user_project import ProjectRole
from app.services.audit import write_audit_log

from app.core.encryption import SENSITIVE_KEYS, mask_config, encrypt_config, decrypt_config

router = APIRouter(tags=["通知配置"])


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
    return cfg


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
    q = select(NotificationConfig).order_by(NotificationConfig.created_at.desc())
    if project_id is not None:
        q = q.where(NotificationConfig.project_id == project_id)
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

    for k, v in body.model_dump(exclude_none=True).items():
        if k == "config" and isinstance(v, dict):
            existing_plain = decrypt_config(cfg.config or {})
            merged = dict(existing_plain)
            for config_key, config_value in v.items():
                if config_key in SENSITIVE_KEYS and config_value == "******":
                    continue
                merged[config_key] = config_value
            v = encrypt_config(merged)
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
    return cfg


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

    from app.services.notifier import _send_email, _send_wechat, _send_dingtalk
    from app.models.notification import NotifyChannel

    try:
        real_config = decrypt_config(cfg.config)
        language = real_config.get("language")
        test_summary = {
            "title": "ATP notification test" if language == "en-US" else "ATP 通知测试",
            "status": "passed",
            "total": 10,
            "passed": 9,
            "failed": 1,
            "error": 0,
            "duration_ms": 5000,
            "trigger_type": "manual",
        }
        if cfg.channel == NotifyChannel.email:
            await _send_email(real_config, test_summary)
        elif cfg.channel == NotifyChannel.wechat:
            await _send_wechat(real_config, test_summary)
        elif cfg.channel == NotifyChannel.dingtalk:
            await _send_dingtalk(real_config, test_summary)
        return {"message": "测试通知已发送"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"通知发送失败: {str(e)}")
