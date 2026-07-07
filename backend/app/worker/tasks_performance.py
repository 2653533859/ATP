"""Celery tasks for HTTP performance testing."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from app.models.bootstrap import load_all_models
from app.worker.async_runner import run_async
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

load_all_models()


@celery_app.task(bind=True, name="run_performance_test")
def run_performance_test(self, run_id: int):
    from app.core.database import AsyncSessionLocal
    from app.models.performance import PerformanceRun, PerformanceRunStatus, PerformanceTest
    from app.services.performance import run_k6_script

    async def _execute():
        async with AsyncSessionLocal() as db:
            run = await db.get(PerformanceRun, run_id)
            if run is None:
                logger.error("PerformanceRun %s not found", run_id)
                return

            test = await db.get(PerformanceTest, run.performance_test_id)
            if test is None:
                run.status = PerformanceRunStatus.failed.value
                run.error_message = "Performance test not found"
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
                return

            run.status = PerformanceRunStatus.running.value
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

            try:
                summary, raw_object_name, duration_ms = run_k6_script(
                    run_id=run.id,
                    script_object_name=test.script_object_name,
                    options=run.options_snapshot,
                )
                run.summary = summary
                run.raw_result_object_name = raw_object_name
                run.duration_ms = duration_ms
                run.status = (
                    PerformanceRunStatus.success.value
                    if summary.get("exit_code") == 0
                    else PerformanceRunStatus.failed.value
                )
                run.error_message = summary.get("k6_error")
            except Exception as exc:
                logger.exception("Performance run %s failed", run_id)
                run.status = PerformanceRunStatus.failed.value
                run.error_message = str(exc)[:1000]
            finally:
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()

    run_async(_execute())
