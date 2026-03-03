from app.worker.celery_app import celery_app
from app.worker.executors.api_executor import run_api_case
from app.models.case import CaseType
import asyncio
import logging

logger = logging.getLogger(__name__)


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
                if case.case_type == CaseType.api:
                    await run_api_case(db, run, case, extra_vars)
                else:
                    run.status = RunStatus.error
                    run.error_message = f"执行器尚未实现: {case.case_type}"
                    await db.commit()
            except Exception as e:
                logger.exception(f"Run {run_id} failed with error: {e}")
                run.status = RunStatus.error
                run.error_message = str(e)
                await db.commit()

    asyncio.run(_execute())
