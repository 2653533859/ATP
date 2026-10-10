"""Public, non-sensitive runtime identity for mode-aware Windows clients."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/runtime", tags=["运行模式"])

LOCAL_FEATURES = [
    "api",
    "web",
    "android",
    "web_recording",
    "graphql",
    "websocket",
    "grpc",
    "suites",
    "plans",
    "requirements",
    "defects",
    "assets",
    "knowledge",
    "ai_generation",
    "hermes",
    "performance",
]


@router.get("/capabilities")
def get_runtime_capabilities() -> dict:
    return {
        "mode": "local" if settings.ATP_LOCAL_MODE else "server",
        "features": LOCAL_FEATURES if settings.ATP_LOCAL_MODE else [*LOCAL_FEATURES, "ios", "schedules", "nodes"],
        "group_execution": "sequential" if settings.ATP_LOCAL_MODE else "configurable",
        "group_cancellation": "after_current_child" if settings.ATP_LOCAL_MODE else "server",
        "schedule": not settings.ATP_LOCAL_MODE,
        "remote_nodes": not settings.ATP_LOCAL_MODE,
    }


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
