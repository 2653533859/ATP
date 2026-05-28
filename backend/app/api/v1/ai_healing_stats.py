from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.cache_decorator import cached_json
from app.core.database import get_db
from app.core.redis_client import get_json_cache, set_json_cache
from app.models.user import User
from app.schemas.ai_healing_stats import AIHealingStatsOut
from app.services.ai_healing_stats import build_ai_healing_stats

router = APIRouter(prefix="/ai-healing", tags=["AI 自愈统计"])
logger = logging.getLogger(__name__)


def _cache_key(**kwargs) -> str:
    return f"atp:ai-healing:stats:days={kwargs.get('days')}"


async def _safe_get_cache(key: str):
    try:
        return await get_json_cache(key)
    except Exception:
        logger.warning("failed to get ai healing stats cache: %s", key, exc_info=True)
        return None


async def _safe_set_cache(key: str, value) -> None:
    try:
        await set_json_cache(key, value, ttl_seconds=300)
    except Exception:
        logger.warning("failed to set ai healing stats cache: %s", key, exc_info=True)


@router.get("/stats", response_model=AIHealingStatsOut)
@cached_json(
    key_builder=_cache_key,
    serializer=lambda result: result.model_dump(),
    deserializer=lambda payload: AIHealingStatsOut(**payload),
    read_cache=_safe_get_cache,
    write_cache=_safe_set_cache,
)
async def get_ai_healing_stats(
    days: int = Query(30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await build_ai_healing_stats(db, days=days)
