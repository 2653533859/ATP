from app.worker.celery_app import celery_app
from app.worker.executors.api_executor import run_api_case
from app.worker.executors.web_executor import run_web_case
from app.worker.executors.web_lowcode_executor import run_web_lowcode
from app.worker.executors.android_executor import run_android_case
from app.worker.executors.android_lowcode_executor import run_android_lowcode
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
                elif case.case_type == CaseType.android:
                    cfg = case.config or {}
                    if is_web_lowcode_config(cfg):
                        await run_android_lowcode(db, run, case, extra_vars)
                    else:
                        await run_android_case(db, run, case, extra_vars)
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


@celery_app.task(bind=True, name="run_test_suite")
def run_test_suite(self, suite_run_id: int, extra_vars: dict):
    """套件执行入口：按顺序依次执行套件内所有用例"""
    from app.core.database import AsyncSessionLocal
    from app.models.case import TestRun, TestCase, RunStatus
    from app.models.suite import TestSuite, SuiteRun, SuiteRunStatus
    import time

    async def _execute():
        async with AsyncSessionLocal() as db:
            suite_run = await db.get(SuiteRun, suite_run_id)
            if not suite_run:
                logger.error(f"SuiteRun {suite_run_id} not found")
                return

            suite = await db.get(TestSuite, suite_run.suite_id)
            if not suite:
                suite_run.status = SuiteRunStatus.error
                suite_run.error_message = "套件不存在"
                await db.commit()
                return

            suite_run.status = SuiteRunStatus.running
            await db.commit()

            total_start = time.monotonic()
            case_items = sorted(suite.case_ids or [], key=lambda x: x.get("sort", 0))
            case_run_results: list[dict] = []
            counts = {"total": 0, "passed": 0, "failed": 0, "error": 0, "skipped": 0}

            for item in case_items:
                case_id = item.get("case_id")
                if not case_id:
                    continue

                case = await db.get(TestCase, case_id)
                if not case:
                    case_run_results.append({
                        "case_id": case_id, "run_id": None,
                        "status": "error", "error": "用例不存在",
                    })
                    counts["error"] += 1
                    counts["total"] += 1
                    continue

                # 为每个用例创建独立的 TestRun
                case_run = TestRun(
                    case_id=case_id,
                    triggered_by=suite_run.triggered_by,
                    status=RunStatus.pending,
                    environment=suite_run.environment,
                )
                db.add(case_run)
                await db.commit()
                await db.refresh(case_run)

                # 同步执行（套件内顺序执行）
                try:
                    case_run.status = RunStatus.running
                    await db.commit()

                    if case.case_type == CaseType.api:
                        await run_api_case(db, case_run, case, extra_vars)
                    elif case.case_type == CaseType.web:
                        cfg = case.config or {}
                        if is_web_lowcode_config(cfg):
                            await run_web_lowcode(db, case_run, case, extra_vars)
                        else:
                            await run_web_case(db, case_run, case, extra_vars)
                    elif case.case_type == CaseType.android:
                        cfg = case.config or {}
                        if is_web_lowcode_config(cfg):
                            await run_android_lowcode(db, case_run, case, extra_vars)
                        else:
                            await run_android_case(db, case_run, case, extra_vars)
                    else:
                        case_run.status = RunStatus.error
                        case_run.error_message = f"执行器尚未实现: {case.case_type}"
                        await db.commit()
                except Exception as e:
                    logger.exception(f"Suite case {case_id} run failed: {e}")
                    case_run.status = RunStatus.error
                    case_run.error_message = str(e)[:500]
                    await db.commit()

                # 刷新获取最新状态
                await db.refresh(case_run)
                status_str = case_run.status.value
                case_run_results.append({
                    "case_id": case_id,
                    "case_name": case.name,
                    "run_id": case_run.id,
                    "status": status_str,
                })
                counts["total"] += 1
                if status_str in counts:
                    counts[status_str] += 1

            # 汇总结果
            total_ms = int((time.monotonic() - total_start) * 1000)
            all_passed = counts["failed"] == 0 and counts["error"] == 0
            suite_run.status = SuiteRunStatus.passed if all_passed else SuiteRunStatus.failed
            suite_run.duration_ms = total_ms
            suite_run.case_run_ids = case_run_results
            suite_run.result_summary = counts
            await db.commit()

    asyncio.run(_execute())
