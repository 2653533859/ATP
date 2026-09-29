"""Public, non-sensitive runtime identity for mode-aware Windows clients."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/runtime", tags=["运行模式"])


class RuntimeIdentity(BaseModel):
    mode: str
    database: str
    storage: str
    execution: str


@router.get("", response_model=RuntimeIdentity)
def get_runtime_identity() -> RuntimeIdentity:
    if settings.ATP_LOCAL_MODE:
        return RuntimeIdentity(mode="local", database="sqlite", storage="filesystem", execution="local")
    return RuntimeIdentity(mode="server", database="postgresql", storage="minio", execution="celery")
