"""MinIO 存储使用率告警。

设计要点：
- 当 bucket 总大小（GB）超过 ``settings.STORAGE_ALERT_SIZE_GB`` 时，写入 Redis 告警状态
- 同一告警状态在 ``settings.STORAGE_ALERT_INTERVAL_SECONDS`` 内仅生效一次
- 当大小回落到阈值以下时，清空告警状态
- 仅作为只读信号供前端 Dashboard / API 查询，不直接触发邮件，避免与按项目的 NotificationConfig 体系耦合
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core import minio_client
from app.core.config import settings
from app.core.redis_client import delete_json_cache, get_json_cache, set_json_cache

logger = logging.getLogger(__name__)

ALERT_CACHE_KEY = "atp:storage:alert"
_BYTES_PER_GB = 1024**3


def _bucket_total_bytes() -> tuple[int, bool]:
    """返回 (total_bytes, exceeded_scan_limit)。

    若扫描对象数超过 ``settings.STORAGE_ALERT_MAX_SCAN_OBJECTS``，
    返回 ``exceeded_scan_limit=True``，调用方应放弃本次告警判断。
    """
    limit = max(0, int(settings.STORAGE_ALERT_MAX_SCAN_OBJECTS))
    total = 0
    scanned = 0
    for obj in minio_client.list_objects(prefix=""):
        if limit and scanned >= limit:
            return total, True
        total += getattr(obj, "size", 0) or 0
        scanned += 1
    return total, False


async def check_and_record_alert() -> dict | None:
    """根据 bucket 当前大小写入或清除告警状态，返回当前状态。"""
    threshold_gb = float(settings.STORAGE_ALERT_SIZE_GB or 0)
    if threshold_gb <= 0:
        # 关闭告警时也清掉残留告警状态
        existing = await get_json_cache(ALERT_CACHE_KEY)
        if existing is not None:
            await delete_json_cache(ALERT_CACHE_KEY)
        return None

    total_bytes, exceeded = _bucket_total_bytes()
    if exceeded:
        logger.warning(
            "Storage alert skipped: bucket object count exceeded scan limit %d",
            settings.STORAGE_ALERT_MAX_SCAN_OBJECTS,
        )
        return None

    total_gb = total_bytes / _BYTES_PER_GB

    if total_gb < threshold_gb:
        existing = await get_json_cache(ALERT_CACHE_KEY)
        if existing is not None:
            await delete_json_cache(ALERT_CACHE_KEY)
            logger.info(
                "Storage alert cleared: usage=%.2fGB threshold=%.2fGB",
                total_gb,
                threshold_gb,
            )
        return None

    cached = await get_json_cache(ALERT_CACHE_KEY)
    if cached:
        return cached

    payload = {
        "bucket": settings.MINIO_BUCKET,
        "total_bytes": total_bytes,
        "total_gb": round(total_gb, 2),
        "threshold_gb": threshold_gb,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }
    ttl = max(60, int(settings.STORAGE_ALERT_INTERVAL_SECONDS))
    await set_json_cache(ALERT_CACHE_KEY, payload, ttl_seconds=ttl)
    logger.warning(
        "Storage alert raised: usage=%.2fGB exceeds threshold=%.2fGB",
        total_gb,
        threshold_gb,
    )
    return payload


async def get_current_alert() -> dict | None:
    return await get_json_cache(ALERT_CACHE_KEY)
