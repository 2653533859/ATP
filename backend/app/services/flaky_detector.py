import logging
import time
from typing import Any
from sqlalchemy import func, select
from app.core.config import settings
from app.core.redis_client import get_json_cache, set_json_cache, delete_json_cache
from app.models.case import RunStatus, TestRun, TestCase

logger = logging.getLogger(__name__)

FLAKY_WINDOW_SIZE = 10
FLAKY_MIN_RUNS = 4
FLAKY_TERMINAL_STATUSES = [RunStatus.passed, RunStatus.failed, RunStatus.error]
FLAKY_CACHE_TTL_SECONDS = 120

# 本地轻量内存缓存（针对 Local 模式或高频连续调用）
_MEMORY_CACHE: dict[int, tuple[dict[str, Any], float]] = {}


def _empty_flaky_stats() -> dict[str, Any]:
    return {
        "is_flaky": False,
        "total_runs": 0,
        "passed_runs": 0,
        "failed_runs": 0,
        "error_runs": 0,
        "failure_rate": 0.0,
    }


def _cache_key(case_id: int) -> str:
    return f"atp:flaky:case:{case_id}"


async def get_flaky_stats_for_cases(
    db: Any,
    case_ids: list[int],
    *,
    use_cache: bool = True,
) -> dict[int, dict[str, Any]]:
    """批量高效获取用例的 Flaky 统计指标。

    结合两级缓存机制（内存 + Redis），大幅降低列表查询与套件完成后全表扫描 TestRun 窗口聚合慢 SQL。
    """
    valid_ids = sorted({cid for cid in case_ids if isinstance(cid, int)})
    if not valid_ids:
        return {}

    now = time.monotonic()
    result_map: dict[int, dict[str, Any]] = {}
    missing_ids: list[int] = []

    if use_cache:
        for cid in valid_ids:
            # 1. 检查内存缓存
            cached_mem = _MEMORY_CACHE.get(cid)
            if cached_mem and (now - cached_mem[1]) < FLAKY_CACHE_TTL_SECONDS:
                result_map[cid] = dict(cached_mem[0])
                continue

            # 2. 若无内存缓存且处于 Server 模式，检查 Redis 缓存
            if not settings.ATP_LOCAL_MODE:
                try:
                    cached_redis = await get_json_cache(_cache_key(cid))
                    if isinstance(cached_redis, dict):
                        result_map[cid] = cached_redis
                        _MEMORY_CACHE[cid] = (cached_redis, now)
                        continue
                except Exception as exc:
                    logger.debug("Redis cache read failed for case %s: %s", cid, exc)

            missing_ids.append(cid)
    else:
        missing_ids = list(valid_ids)

    # 3. 对缓存未命中的 case_ids 执行精准窗口聚合 SQL
    if missing_ids:
        db_stats = await _query_flaky_stats_from_db(db, missing_ids)
        for cid in missing_ids:
            stats = db_stats.get(cid, _empty_flaky_stats())
            result_map[cid] = stats
            if use_cache:
                _MEMORY_CACHE[cid] = (stats, now)
                if not settings.ATP_LOCAL_MODE:
                    try:
                        await set_json_cache(_cache_key(cid), stats, ttl_seconds=FLAKY_CACHE_TTL_SECONDS)
                    except Exception as exc:
                        logger.debug("Redis cache write failed for case %s: %s", cid, exc)

    return result_map


async def _query_flaky_stats_from_db(db: Any, case_ids: list[int]) -> dict[int, dict[str, Any]]:
    """从数据库执行窗口聚合查询。"""
    ranked = (
        select(
            TestRun.case_id.label("case_id"),
            TestRun.status.label("status"),
            func.row_number()
            .over(
                partition_by=TestRun.case_id,
                order_by=(TestRun.created_at.desc(), TestRun.id.desc()),
            )
            .label("rn"),
        )
        .where(
            TestRun.case_id.in_(case_ids),
            TestRun.status.in_(FLAKY_TERMINAL_STATUSES),
            TestRun.parent_run_id.is_(None),
        )
        .subquery()
    )

    rows = (await db.execute(select(ranked.c.case_id, ranked.c.status).where(ranked.c.rn <= FLAKY_WINDOW_SIZE))).all()

    stats_by_case = {case_id: _empty_flaky_stats() for case_id in case_ids}
    for row in rows:
        stats = stats_by_case[row.case_id]
        stats["total_runs"] += 1
        status = row.status.value if hasattr(row.status, "value") else str(row.status)
        if status == "passed":
            stats["passed_runs"] += 1
        elif status == "failed":
            stats["failed_runs"] += 1
        elif status == "error":
            stats["error_runs"] += 1

    for cid, stats in stats_by_case.items():
        failure_runs = stats["failed_runs"] + stats["error_runs"]
        if stats["total_runs"]:
            stats["failure_rate"] = round(failure_runs / stats["total_runs"] * 100, 1)
        stats["is_flaky"] = stats["total_runs"] >= FLAKY_MIN_RUNS and stats["passed_runs"] > 0 and failure_runs > 0

    return stats_by_case


async def attach_flaky_stats(db: Any, cases: Any) -> None:
    """批量为用例实体注入 flaky_stats 属性（复用两级缓存）。"""
    case_ids = [case.id for case in cases]
    if not case_ids:
        return

    stats_map = await get_flaky_stats_for_cases(db, case_ids)
    for case in cases:
        stats = stats_map.get(case.id, _empty_flaky_stats())
        setattr(case, "flaky_stats", stats)


async def invalidate_case_flaky_cache(case_id: int) -> None:
    """使指定用例的 Flaky 缓存失效。"""
    _MEMORY_CACHE.pop(case_id, None)
    if not settings.ATP_LOCAL_MODE:
        try:
            await delete_json_cache(_cache_key(case_id))
        except Exception:
            pass


def clear_memory_cache() -> None:
    """清空本地内存缓存（供测试清理使用）。"""
    _MEMORY_CACHE.clear()
