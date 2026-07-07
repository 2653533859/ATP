"""Current-user settings API.

Used as the server-side home for preferences that previously lived only in
localStorage, such as dashboard layout, language, default project, and table
columns. Values are intentionally scoped by key to avoid one large mutable blob.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.user_setting import UserSetting
from app.schemas.user_setting import UserSettingOut, UserSettingUpdateIn

router = APIRouter(prefix="/users/me/settings", tags=["用户偏好"])

_MAX_SETTING_VALUE_BYTES = 64 * 1024


def _validate_key(key: str) -> str:
    normalized = key.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="setting key 不能为空")
    if len(normalized) > 128:
        raise HTTPException(status_code=400, detail="setting key 超过 128 字符")
    return normalized


def _validate_value(value: dict) -> None:
    import json

    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > _MAX_SETTING_VALUE_BYTES:
        raise HTTPException(status_code=400, detail="setting value 超过 64KB")


@router.get("", response_model=list[UserSettingOut])
async def list_my_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserSetting).where(UserSetting.user_id == current_user.id).order_by(UserSetting.key.asc())
    )
    return result.scalars().all()


@router.get("/{key}", response_model=UserSettingOut)
async def get_my_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    normalized = _validate_key(key)
    result = await db.execute(
        select(UserSetting).where(
            UserSetting.user_id == current_user.id,
            UserSetting.key == normalized,
        )
    )
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail="setting 不存在")
    return setting


@router.put("/{key}", response_model=UserSettingOut)
async def upsert_my_setting(
    key: str,
    body: UserSettingUpdateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    normalized = _validate_key(key)
    _validate_value(body.value)
    result = await db.execute(
        select(UserSetting).where(
            UserSetting.user_id == current_user.id,
            UserSetting.key == normalized,
        )
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = body.value
    else:
        setting = UserSetting(user_id=current_user.id, key=normalized, value=body.value)
        db.add(setting)
    await db.commit()
    await db.refresh(setting)
    return setting


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    normalized = _validate_key(key)
    result = await db.execute(
        select(UserSetting).where(
            UserSetting.user_id == current_user.id,
            UserSetting.key == normalized,
        )
    )
    setting = result.scalar_one_or_none()
    if setting:
        await db.delete(setting)
        await db.commit()
    return None
