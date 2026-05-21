"""Celery 任务：AI 用例自愈诊断异步入口（P3.A）。

模块独立以便 executor 中 .delay() 时不引入 ai_healing 服务层重型依赖循环。
"""
from __future__ import annotations

import asyncio
import logging

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="diagnose_step_failure", bind=True, max_retries=0, acks_late=True)
def diagnose_step_failure(self, step_result_id: int) -> None:
    """异步诊断一个失败 step。失败时只记录日志，不重试（LLM 调用不幂等）。"""
    try:
        asyncio.run(_run(step_result_id))
    except Exception:
        logger.exception("diagnose_step_failure crashed for step_result_id=%s", step_result_id)


async def _run(step_result_id: int) -> None:
    from app.core.database import AsyncSessionLocal
    from app.services.ai_healing import run_diagnosis

    async with AsyncSessionLocal() as db:
        await run_diagnosis(db, step_result_id)
