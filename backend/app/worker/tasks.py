from app.worker.celery_app import celery_app
from app.worker.case_dispatch import dispatch_case
from app.models.bootstrap import load_all_models
from app.core.redis_client import publish_run_event, delete_json_cache_pattern
from app.core.encryption import decrypt_env_vars
import logging
from app.worker.async_runner import run_async

logger = logging.getLogger(__name__)

load_all_models()


async def _safe_publish_run_event(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        logger.exception(f"Failed to publish run event for run {run_id}: {payload.get('type')}")


async def _safe_invalidate_stats_cache() -> None:
    try:
        await delete_json_cache_pattern("atp:stats:*")
    except Exception:
        logger.exception("Failed to invalidate stats cache")


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

                dispatched = await dispatch_case(db, run, case, extra_vars)
                if not dispatched:
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
            finally:
                await _safe_invalidate_stats_cache()

    run_async(_execute())


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

                    await dispatch_case(db, case_run, case, extra_vars)
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

            # 发送通知
            try:
                from app.services.notifier import send_notifications
                await send_notifications(db, suite.project_id, {
                    "title": f"测试套件「{suite.name}」执行完成",
                    "status": suite_run.status.value,
                    **counts,
                    "duration_ms": total_ms,
                    "trigger_type": "manual",
                })
            except Exception as e:
                logger.warning(f"Suite notification failed: {e}")
            finally:
                await _safe_invalidate_stats_cache()

    run_async(_execute())


@celery_app.task(bind=True, name="run_test_plan")
def run_test_plan(self, plan_run_id: int, extra_vars: dict):
    """测试计划执行入口：按顺序依次执行计划内所有套件"""
    from app.core.database import AsyncSessionLocal
    from app.models.plan import TestPlan, PlanRun, PlanRunStatus
    from app.models.suite import TestSuite, SuiteRun, SuiteRunStatus
    import time
    from datetime import datetime, timezone

    async def _execute():
        async with AsyncSessionLocal() as db:
            plan_run = await db.get(PlanRun, plan_run_id)
            if not plan_run:
                logger.error(f"PlanRun {plan_run_id} not found")
                return

            plan = await db.get(TestPlan, plan_run.plan_id)
            if not plan:
                plan_run.status = PlanRunStatus.error
                plan_run.error_message = "测试计划不存在"
                await db.commit()
                return

            plan_run.status = PlanRunStatus.running
            await db.commit()

            total_start = time.monotonic()
            suite_items = sorted(plan.suite_ids or [], key=lambda x: x.get("sort", 0))
            suite_run_results: list[dict] = []
            counts = {"total": 0, "passed": 0, "failed": 0, "error": 0}

            for item in suite_items:
                suite_id = item.get("suite_id")
                if not suite_id:
                    continue

                suite = await db.get(TestSuite, suite_id)
                if not suite:
                    suite_run_results.append({
                        "suite_id": suite_id, "suite_run_id": None,
                        "status": "error", "error": "套件不存在",
                    })
                    counts["error"] += 1
                    counts["total"] += 1
                    continue

                suite_run = SuiteRun(
                    suite_id=suite_id,
                    triggered_by=(
                        plan_run.triggered_by
                        if plan_run.triggered_by is not None
                        else plan.creator_id
                    ),
                    status=SuiteRunStatus.pending,
                )
                db.add(suite_run)
                await db.commit()
                await db.refresh(suite_run)

                try:
                    await _execute_suite_inline(db, suite_run, suite, extra_vars)
                except Exception as e:
                    logger.exception(f"Plan suite {suite_id} run failed: {e}")
                    suite_run.status = SuiteRunStatus.error
                    suite_run.error_message = str(e)[:500]
                    await db.commit()

                await db.refresh(suite_run)
                status_str = suite_run.status.value
                suite_run_results.append({
                    "suite_id": suite_id,
                    "suite_name": suite.name,
                    "suite_run_id": suite_run.id,
                    "status": status_str,
                })
                counts["total"] += 1
                if status_str in counts:
                    counts[status_str] += 1

            total_ms = int((time.monotonic() - total_start) * 1000)
            all_passed = counts["failed"] == 0 and counts["error"] == 0
            plan_run.status = PlanRunStatus.passed if all_passed else PlanRunStatus.failed
            plan_run.duration_ms = total_ms
            plan_run.suite_run_ids = suite_run_results
            plan_run.result_summary = counts

            if plan.auto_create_bugs and suite_run_results:
                try:
                    from app.models.bug_tracker import BugTracker
                    from app.services.bug_reporter import create_bug, find_duplicate_bug, upload_attachment, build_bug_description
                    from app.core.minio_client import read_bytes
                    from app.core.encryption import decrypt_config
                    from app.api.v1.exports import _extract_minio_object
                    bug_trackers_result = await db.execute(
                        select(BugTracker).where(BugTracker.project_id == plan.project_id, BugTracker.is_enabled == True)
                    )
                    tracker = bug_trackers_result.scalars().first()
                    bug_results = []
                    if tracker:
                        for suite_result in suite_run_results:
                            suite_run_id = suite_result.get("suite_run_id")
                            if not suite_run_id:
                                continue
                            suite_run = await db.get(SuiteRun, suite_run_id)
                            for case_result in suite_run.case_run_ids or []:
                                if case_result.get("status") not in {"failed", "error"}:
                                    continue
                                case_run_id = case_result.get("run_id")
                                case_run = await db.get(TestRun, case_run_id) if case_run_id else None
                                if not case_run:
                                    continue
                                case = await db.get(TestCase, case_result.get("case_id"))
                                if not case:
                                    continue
                                title = f"[ATP] {case.name} 执行失败"
                                duplicate = await find_duplicate_bug(
                                    tracker.tracker_type.value,
                                    decrypt_config(tracker.config),
                                    title,
                                )
                                if duplicate:
                                    bug_results.append({"case_id": case.id, "bug_id": duplicate["bug_id"], "duplicate": True})
                                    continue
                                description = build_bug_description(
                                    run_id=case_run.id,
                                    case_name=case.name,
                                    environment=case_run.environment,
                                    error_message=case_run.error_message,
                                )
                                created = await create_bug(
                                    tracker.tracker_type.value,
                                    decrypt_config(tracker.config),
                                    title,
                                    description,
                                    tracker.field_mapping or {},
                                )
                                attachment_uploaded = False
                                screenshot_url = None
                                step_result_query = await db.execute(
                                    select(__import__('app.models.case', fromlist=['StepResult']).StepResult)
                                    .where(__import__('app.models.case', fromlist=['StepResult']).StepResult.run_id == case_run.id,
                                           __import__('app.models.case', fromlist=['StepResult']).StepResult.screenshot_url.isnot(None))
                                )
                                first_step = step_result_query.scalars().first()
                                screenshot_url = first_step.screenshot_url if first_step else None
                                if screenshot_url:
                                    object_name = _extract_minio_object(screenshot_url)
                                    if object_name:
                                        try:
                                            attachment_uploaded = await upload_attachment(
                                                tracker.tracker_type.value,
                                                decrypt_config(tracker.config),
                                                created["bug_id"],
                                                f"run-{case_run.id}-screenshot.png",
                                                read_bytes(object_name),
                                            )
                                        except Exception:
                                            attachment_uploaded = False
                                bug_results.append({
                                    "case_id": case.id,
                                    "bug_id": created["bug_id"],
                                    "bug_url": created["bug_url"],
                                    "duplicate": False,
                                    "attachment_uploaded": attachment_uploaded,
                                })
                    plan_run.result_summary = {**counts, "auto_bugs": bug_results}
                except Exception as e:
                    logger.warning(f"Auto create bugs for plan failed: {e}")
                    plan_run.result_summary = {**counts, "auto_bugs_error": str(e)[:500]}

            plan.last_run_at = datetime.now(timezone.utc)
            if plan.schedule_type.value == "cron" and plan.cron_expression:
                try:
                    from croniter import croniter
                    cron = croniter(plan.cron_expression, datetime.now(timezone.utc))
                    plan.next_run_at = cron.get_next(datetime)
                except Exception:
                    pass
            await db.commit()

            # 发送通知
            try:
                from app.services.notifier import send_notifications
                await send_notifications(db, plan.project_id, {
                    "title": f"测试计划「{plan.name}」执行完成",
                    "status": plan_run.status.value,
                    **counts,
                    "duration_ms": total_ms,
                    "trigger_type": plan_run.trigger_type.value,
                })
            except Exception as e:
                logger.warning(f"Plan notification failed: {e}")
            finally:
                await _safe_invalidate_stats_cache()

    run_async(_execute())


async def _execute_suite_inline(db, suite_run, suite, extra_vars):
    """内联执行套件（在 plan 上下文中直接调用，避免嵌套 Celery 任务）"""
    from app.models.case import TestCase, TestRun, RunStatus
    from app.models.suite import SuiteRunStatus
    import time

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

        case_run = TestRun(
            case_id=case_id,
            triggered_by=suite_run.triggered_by,
            status=RunStatus.pending,
            environment=suite_run.environment,
        )
        db.add(case_run)
        await db.commit()
        await db.refresh(case_run)

        try:
            case_run.status = RunStatus.running
            await db.commit()

            await dispatch_case(db, case_run, case, extra_vars)
        except Exception as e:
            logger.exception(f"Plan->Suite case {case_id} run failed: {e}")
            case_run.status = RunStatus.error
            case_run.error_message = str(e)[:500]
            await db.commit()

        await db.refresh(case_run)
        status_str = case_run.status.value
        case_run_results.append({
            "case_id": case_id, "case_name": case.name,
            "run_id": case_run.id, "status": status_str,
        })
        counts["total"] += 1
        if status_str in counts:
            counts[status_str] += 1

    total_ms = int((time.monotonic() - total_start) * 1000)
    all_passed = counts["failed"] == 0 and counts["error"] == 0
    suite_run.status = SuiteRunStatus.passed if all_passed else SuiteRunStatus.failed
    suite_run.duration_ms = total_ms
    suite_run.case_run_ids = case_run_results
    suite_run.result_summary = counts
    await db.commit()


@celery_app.task(name="check_cron_plans")
def check_cron_plans():
    """每分钟检查启用的 Cron 计划，到期则触发执行"""
    from app.core.database import AsyncSessionLocal
    from app.models.plan import TestPlan, PlanRun, PlanRunStatus, ScheduleType, TriggerType
    from sqlalchemy import select
    from datetime import datetime, timezone

    async def _check():
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            q = select(TestPlan).where(
                TestPlan.schedule_type == ScheduleType.cron,
                TestPlan.is_enabled == True,  # noqa: E712
                TestPlan.cron_expression.isnot(None),
                TestPlan.next_run_at.isnot(None),
                TestPlan.next_run_at <= now,
            )
            result = await db.execute(q)
            plans = result.scalars().all()

            for plan in plans:
                if not plan.suite_ids:
                    continue

                merged_vars: dict = {}
                if plan.env_id:
                    from app.models.environment import Environment, EnvVariable
                    env = await db.get(Environment, plan.env_id)
                    if env:
                        ev_result = await db.execute(
                            select(EnvVariable).where(EnvVariable.env_id == env.id)
                        )
                        merged_vars = decrypt_env_vars(ev_result.scalars().all())

                plan_run = PlanRun(
                    plan_id=plan.id,
                    triggered_by=None,
                    trigger_type=TriggerType.cron,
                    status=PlanRunStatus.pending,
                )
                db.add(plan_run)
                await db.commit()
                await db.refresh(plan_run)

                try:
                    from croniter import croniter
                    cron = croniter(plan.cron_expression, now)
                    plan.next_run_at = cron.get_next(datetime)
                except Exception:
                    plan.is_enabled = False
                await db.commit()

                run_test_plan.delay(plan_run.id, merged_vars)
                logger.info(f"Cron triggered plan {plan.id} -> PlanRun {plan_run.id}")

    run_async(_check())
