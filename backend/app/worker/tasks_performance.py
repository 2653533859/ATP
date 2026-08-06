"""Celery tasks for HTTP performance testing."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from sqlalchemy import select

from app.core.encryption import decrypt
from app.models.bootstrap import load_all_models
from app.services.performance_options import ENVIRONMENT_SNAPSHOT_KEY
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
                runtime_options = dict(run.options_snapshot or {})
                encrypted_environment = runtime_options.pop(ENVIRONMENT_SNAPSHOT_KEY, None)
                if encrypted_environment is not None:
                    if not isinstance(encrypted_environment, dict):
                        raise RuntimeError("压测环境快照格式无效")
                    environment_values = {str(key): decrypt(str(value)) for key, value in encrypted_environment.items()}
                    merged_env = dict(environment_values)
                    merged_env.update(runtime_options.get("env") or {})
                    if merged_env:
                        runtime_options["env"] = merged_env
                elif getattr(run, "environment_id", None):
                    # Backward compatibility for runs created before environment values
                    # were captured at trigger time. New runs always use the encrypted snapshot.
                    from app.core.encryption import decrypt_env_vars
                    from app.models.environment import EnvVariable

                    env_result = await db.execute(select(EnvVariable).where(EnvVariable.env_id == run.environment_id))
                    environment_values = decrypt_env_vars(env_result.scalars().all())
                    merged_env = dict(environment_values)
                    merged_env.update(runtime_options.get("env") or {})
                    if merged_env:
                        runtime_options["env"] = merged_env

                summary, raw_object_name, duration_ms = run_k6_script(
                    run_id=run.id,
                    script_object_name=test.script_object_name,
                    options=runtime_options,
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
