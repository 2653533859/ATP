from app.worker.celery_app import celery_app
from app.worker.executors.api_executor import run_api_case
from app.worker.executors.web_executor import run_web_case
from app.worker.executors.web_lowcode_executor import run_web_lowcode
from app.worker.dispatch import is_web_lowcode_config
from app.models.case import CaseType
from app.core.redis_client import publish_run_event
import asyncio
import logging

logger = logging.getLogger(__name__)


async def _safe_publish_run_event(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        logger.exception(f"Failed to publish run event for run {run_id}: {payload.get('type')}")


@celery_app.task(bind=True, name="run_test_case")
def run_test_case(self, run_id: int, extra_vars: dict):
    """统一执行入口，根据用例类型路由到对应执行器"""
    from app.core.database import AsyncSessionLocal
    from app.models.case import TestRun, TestCase, RunStatus
    from sqlalchemy import select

    async def _execute():
        async with AsyncSessionLocal() as db:
            run = await db.get(TestRun, run_id)
            if not run:
                logger.error(f"Run {run_id} not found")
                return

            case = await db.get(TestCase, run.case_id)
            run.status = RunStatus.running
            await db.commit()

            try:
                # 通知前端开始执行（发布失败不影响执行状态）
                await _safe_publish_run_event(run_id, {"type": "run_status", "run_id": run_id, "status": "running"})

                if case.case_type == CaseType.api:
                    await run_api_case(db, run, case, extra_vars)
                elif case.case_type == CaseType.web:
                    # 低代码模式（config 中有 steps）vs 脚本模式（config 中有 script_path）
                    cfg = case.config or {}
                    if is_web_lowcode_config(cfg):
                        await run_web_lowcode(db, run, case, extra_vars)
                    else:
                        await run_web_case(db, run, case, extra_vars)
                else:
                    run.status = RunStatus.error
                    run.error_message = f"执行器尚未实现: {case.case_type}"
                    await db.commit()
                    await _safe_publish_run_event(run_id, {
                        "type": "completed", "run_id": run_id, "status": "error",
                    })
            except Exception as e:
                logger.exception(f"Run {run_id} failed with error: {e}")
                run.status = RunStatus.error
                run.error_message = str(e)
                await db.commit()
                await _safe_publish_run_event(run_id, {
                    "type": "completed", "run_id": run_id, "status": "error",
                })

    asyncio.run(_execute())
