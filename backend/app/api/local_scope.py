"""Explicit capability guard for the single-user local profile."""

from fastapi import HTTPException

from app.core.config import settings


def require_server_workspace(feature: str) -> None:
    if settings.ATP_LOCAL_MODE:
        raise HTTPException(status_code=409, detail=f"{feature}在 Windows 单项目模式下不可用")
