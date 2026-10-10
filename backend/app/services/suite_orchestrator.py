import asyncio
import logging
from app.core.config import settings
from app.services.local_group_control import is_group_cancelled
from app.services.api_hooks import ApiHookError, execute_api_hooks

logger = logging.getLogger(__name__)


def _record_run_outcome(entity_type: str, status: object) -> None:
    """Best-effort Prometheus signal for run success-rate SLOs."""
    status_value = getattr(status, "value", str(status))
    if status_value not in {"passed", "failed", "error", "skipped", "cancelled"}:
        return
    try:
        from app.core.metrics import RUN_OUTCOMES

        RUN_OUTCOMES.labels(entity_type=entity_type, status=status_value).inc()
    except Exception:
        logger.exception("Failed to record run outcome metric")


def normalize_suite_config(config: dict | None) -> dict:
    raw = config if isinstance(config, dict) else {}
    execution_mode = raw.get("execution_mode")
    if execution_mode not in {"sequential", "parallel"}:
        execution_mode = "sequential"
    if settings.ATP_LOCAL_MODE:
        execution_mode = "sequential"

    max_workers = raw.get("max_workers", 5)
    try:
        max_workers = int(max_workers)
    except (TypeError, ValueError):
        max_workers = 5
    max_workers = max(1, min(max_workers, 20))

    fail_strategy = raw.get("fail_strategy")
    if fail_strategy not in {"fast-fail", "continue", "require-minimum-pass-rate"}:
        fail_strategy = "continue"

    min_pass_rate = raw.get("min_pass_rate", 0.8)
    try:
        min_pass_rate = float(min_pass_rate)
    except (TypeError, ValueError):
        min_pass_rate = 0.8
    min_pass_rate = max(0.0, min(min_pass_rate, 1.0))

    return {
        "execution_mode": execution_mode,
        "max_workers": max_workers,
        "fail_strategy": fail_strategy,
        "min_pass_rate": min_pass_rate,
    }


def suite_run_should_stop(counts: dict, total: int, fail_strategy: str, min_pass_rate: float) -> bool:
    if total <= 0:
        return False
    if fail_strategy == "fast-fail":
        return counts["failed"] > 0 or counts["error"] > 0
    if fail_strategy != "require-minimum-pass-rate":
        return False

    remaining = total - counts["total"]
    max_possible_passed = counts["passed"] + remaining
    return (max_possible_passed / total) < min_pass_rate


async def create_case_run(db, suite_run, case_id: int):
    from app.models.case import RunStatus, TestRun

    case_run = TestRun(
        case_id=case_id,
        triggered_by=suite_run.triggered_by,
        trace_id=suite_run.trace_id,
        status=RunStatus.pending,
        environment=suite_run.environment,
    )
    db.add(case_run)
    await db.flush()
    from app.services.group_execution import record_child

    await record_child(db, kind="suite", parent=suite_run, child=case_run)
    await db.commit()
    await db.refresh(case_run)
    if settings.ATP_LOCAL_MODE:
        suite_run.case_run_ids = [
            *(suite_run.case_run_ids or []),
            {"case_id": case_id, "run_id": case_run.id, "status": "pending"},
        ]
        await db.commit()
    return case_run


async def execute_case_run(
    db,
    suite_run,
    case,
    extra_vars: dict,
    *,
    route_to_worker: bool = False,
    run_case_task=None,
    dispatch_case_fn=None,
    record_outcome_fn=None,
) -> dict:
    from app.models.case import RunStatus

    case_run = await create_case_run(db, suite_run, case.id)

    try:
        if route_to_worker:
            from app.services.execution_routing import enqueue_case_run

            if run_case_task is None:
                from app.worker.tasks import run_test_case

                run_case_task = run_test_case

            await db.commit()
            enqueue_case_run(run_case_task, case_run.id, extra_vars, suite_run.trace_id, case.case_type)
            deadline = asyncio.get_running_loop().time() + max(1, settings.SUITE_CHILD_TASK_TIMEOUT_SECONDS)
            while asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.2)
                await db.refresh(case_run)
                if case_run.status in {
                    RunStatus.passed,
                    RunStatus.failed,
                    RunStatus.error,
                    RunStatus.skipped,
                    RunStatus.cancelled,
                }:
                    break
            else:
                case_run.status = RunStatus.error
                case_run.error_message = "专用 Worker 执行超时，请检查设备 Worker 是否在线并监听正确队列"
                await db.commit()
        else:
            if dispatch_case_fn is None:
                from app.worker.case_dispatch import dispatch_case

                dispatch_case_fn = dispatch_case

            case_run.status = RunStatus.running
            await db.commit()
            await dispatch_case_fn(db, case_run, case, extra_vars)
        await db.refresh(case_run)
        (record_outcome_fn or _record_run_outcome)("case", case_run.status)
    except Exception as e:
        logger.exception(f"Suite case {case.id} run failed: {e}")
        case_run.status = RunStatus.error
        case_run.error_message = str(e)[:500]
        await db.commit()
        (record_outcome_fn or _record_run_outcome)("case", case_run.status)

    await db.refresh(case_run)
    return {
        "case_id": case.id,
        "case_name": case.name,
        "run_id": case_run.id,
        "status": case_run.status.value,
    }


async def mark_flaky_case_results(db, case_run_results: list[dict]) -> None:
    from app.services.flaky_detector import get_flaky_stats_for_cases

    case_ids = [cid for cid in (item.get("case_id") for item in case_run_results) if isinstance(cid, int)]
    if not case_ids:
        return

    # 运行刚结束，缓存里的统计不含本次子运行；此处必须读库，否则会把运行前的
    # flaky 结论写进本次结果（缓存 TTL 见 flaky_detector）。
    stats = await get_flaky_stats_for_cases(db, case_ids, use_cache=False)

    for result in case_run_results:
        case_id = result.get("case_id")
        if not isinstance(case_id, int):
            continue
        item_stats = stats.get(case_id)
        if not item_stats:
            continue
        result["flaky"] = bool(item_stats.get("is_flaky", False))
        result["flaky_failure_rate"] = float(item_stats.get("failure_rate", 0.0))


def _new_parallel_session():
    from app.core.database import AsyncSessionLocal

    return AsyncSessionLocal()


async def execute_suite_cases(
    db,
    suite_run,
    suite,
    extra_vars: dict,
    *,
    execution_queue: str = "default",
    run_case_task=None,
    execute_case_fn=None,
    mark_flaky_fn=None,
    is_cancelled_fn=None,
    new_parallel_session_fn=None,
):
    if execute_case_fn is None:
        execute_case_fn = execute_case_run
    if mark_flaky_fn is None:
        mark_flaky_fn = mark_flaky_case_results
    if is_cancelled_fn is None:
        is_cancelled_fn = is_group_cancelled
    if new_parallel_session_fn is None:
        new_parallel_session_fn = _new_parallel_session
    from app.models.case import TestCase
    from app.models.suite import SuiteRunStatus

    case_items = sorted(suite.case_ids or [], key=lambda x: x.get("sort", 0))
    suite_config = normalize_suite_config(suite.config)
    total_cases = len(case_items)
    case_run_results: list[dict] = []
    counts = {"total": 0, "passed": 0, "failed": 0, "error": 0, "skipped": 0}
    raw_config = suite.config if isinstance(suite.config, dict) else {}
    shared_variables = (
        raw_config.get("shared_variables") if isinstance(raw_config.get("shared_variables"), dict) else {}
    )
    fixture_context: dict = {**(shared_variables or {}), **(extra_vars or {})}
    fixtures = raw_config.get("fixtures") if isinstance(raw_config.get("fixtures"), dict) else {}
    setup_summary: list[dict] = []
    teardown_summary: list[dict] = []
    fixture_error: str | None = None
    try:
        if not is_cancelled_fn("suite", suite_run.id, suite_run.identity_token):
            setup_summary = execute_api_hooks(
                fixtures.get("setup") if isinstance(fixtures, dict) else None, fixture_context
            )
    except ApiHookError as exc:
        fixture_error = f"Suite Fixture setup 失败: {exc}"

    case_queue_by_id: dict[int, str] = {}
    for item in case_items:
        case_id = item.get("case_id")
        if not case_id:
            continue
        case = await db.get(TestCase, case_id)
        if case is not None:
            from app.services.execution_routing import execution_queue_for_case_type

            case_queue_by_id[case_id] = execution_queue_for_case_type(getattr(case, "case_type", None))
    remote_case_ids = {
        case_id for case_id, queue in case_queue_by_id.items() if queue != "default" and queue != execution_queue
    }
    if settings.ATP_LOCAL_MODE:
        remote_case_ids = set()

    async def execute_case_on_db(case_db, item: dict) -> dict:
        case_id = item.get("case_id")
        if not case_id:
            return {"ignored": True}

        case = await case_db.get(TestCase, case_id)
        if not case:
            return {
                "case_id": case_id,
                "run_id": None,
                "status": "error",
                "error": "用例不存在",
            }

        if case.id in remote_case_ids:
            return await execute_case_fn(case_db, suite_run, case, fixture_context, route_to_worker=True)
        return await execute_case_fn(case_db, suite_run, case, fixture_context)

    async def run_one(item: dict) -> dict:
        if is_cancelled_fn("suite", suite_run.id, suite_run.identity_token):
            return {"case_id": item.get("case_id"), "run_id": None, "status": "skipped", "error": "用户请求取消"}
        if suite_config["execution_mode"] == "parallel" and hasattr(db, "run_sync"):
            async with new_parallel_session_fn() as case_db:
                return await execute_case_on_db(case_db, item)
        return await execute_case_on_db(db, item)

    async def consume_result(result: dict) -> bool:
        if result.get("ignored"):
            return False
        case_run_results.append(result)
        status_str = result.get("status", "error")
        counts["total"] += 1
        if status_str in counts:
            counts[status_str] += 1
        elif status_str == "skipped":
            counts["skipped"] += 1
        elif status_str == "cancelled":
            counts["error"] += 1
        if settings.ATP_LOCAL_MODE:
            suite_run.case_run_ids = list(case_run_results)
            suite_run.result_summary = {**counts, **suite_config, "total": total_cases}
            await db.commit()
        return suite_run_should_stop(
            counts,
            total_cases,
            suite_config["fail_strategy"],
            suite_config["min_pass_rate"],
        )

    if fixture_error:
        for fixture_index, item in enumerate(case_items):
            case_id = item.get("case_id")
            if case_id:
                status_value = "error" if fixture_index == 0 else "skipped"
                case_run_results.append(
                    {"case_id": case_id, "run_id": None, "status": status_value, "error": fixture_error}
                )
                counts["total"] += 1
                counts[status_value] += 1
    elif suite_config["execution_mode"] == "parallel":
        for start in range(0, total_cases, suite_config["max_workers"]):
            if is_cancelled_fn("suite", suite_run.id, suite_run.identity_token):
                break
            batch = case_items[start : start + suite_config["max_workers"]]
            for result in await asyncio.gather(*(run_one(item) for item in batch)):
                await consume_result(result)
            if suite_run_should_stop(
                counts,
                total_cases,
                suite_config["fail_strategy"],
                suite_config["min_pass_rate"],
            ):
                break
    else:
        for item in case_items:
            if is_cancelled_fn("suite", suite_run.id, suite_run.identity_token):
                break
            should_stop = await consume_result(await run_one(item))
            if should_stop:
                break

    skipped_items = [] if fixture_error else case_items[counts["total"] :]
    for item in skipped_items:
        case_id = item.get("case_id")
        if not case_id:
            continue
        case_run_results.append(
            {
                "case_id": case_id,
                "run_id": None,
                "status": "skipped",
                "error": "用户请求取消"
                if is_cancelled_fn("suite", suite_run.id, suite_run.identity_token)
                else "已根据套件失败策略提前停止",
            }
        )
        counts["total"] += 1
        counts["skipped"] += 1

    try:
        teardown_summary = execute_api_hooks(
            fixtures.get("teardown") if isinstance(fixtures, dict) else None, fixture_context
        )
    except ApiHookError as exc:
        fixture_error = f"Suite Fixture teardown 失败: {exc}"
        counts["error"] += 1

    all_passed = counts["failed"] == 0 and counts["error"] == 0
    suite_run.status = SuiteRunStatus.passed if all_passed else SuiteRunStatus.failed
    if is_cancelled_fn("suite", suite_run.id, suite_run.identity_token):
        suite_run.status = SuiteRunStatus.error
        suite_run.error_message = "套件已请求停止或执行归属无法确认；已启动子任务/批次已结束，后续用例未继续执行"
    await mark_flaky_fn(db, case_run_results)
    suite_run.case_run_ids = case_run_results
    suite_run.result_summary = {
        **counts,
        **suite_config,
        "fixtures": {
            "setup": setup_summary,
            "teardown": teardown_summary,
            "status": "failed" if fixture_error else "passed",
            "error": fixture_error,
        },
    }


async def execute_suite_inline(
    db,
    suite_run,
    suite,
    extra_vars,
    *,
    execution_queue: str = "default",
    run_case_task=None,
    execute_case_fn=None,
    execute_suite_cases_fn=None,
    mark_flaky_fn=None,
    is_cancelled_fn=None,
    record_outcome_fn=None,
):
    """内联执行套件（在 plan 上下文中直接调用，避免嵌套 Celery 任务）"""
    import time
    from sqlalchemy import update
    from app.models.suite import SuiteRunStatus

    if is_cancelled_fn is None:
        is_cancelled_fn = is_group_cancelled
    if execute_suite_cases_fn is None:
        execute_suite_cases_fn = execute_suite_cases
    if record_outcome_fn is None:
        record_outcome_fn = _record_run_outcome
    """内联执行套件（在 plan 上下文中直接调用，避免嵌套 Celery 任务）"""
    import time
    from sqlalchemy import update
    from app.models.suite import SuiteRunStatus

    if is_cancelled_fn("suite", suite_run.id, suite_run.identity_token):
        suite_run.status = SuiteRunStatus.error
        suite_run.error_message = "套件已请求停止或执行归属无法确认"
        await db.commit()
        return

    claimed = await db.execute(
        update(type(suite_run))
        .where(
            type(suite_run).id == suite_run.id,
            type(suite_run).identity_token == suite_run.identity_token,
            type(suite_run).status == SuiteRunStatus.pending,
        )
        .values(status=SuiteRunStatus.running)
        .execution_options(synchronize_session=False)
    )
    if getattr(claimed, "rowcount", 0) != 1:
        await db.rollback()
        return
    await db.commit()
    await db.refresh(suite_run)

    total_start = time.monotonic()
    await execute_suite_cases_fn(
        db,
        suite_run,
        suite,
        extra_vars,
        execution_queue=execution_queue,
        run_case_task=run_case_task,
        execute_case_fn=execute_case_fn,
        mark_flaky_fn=mark_flaky_fn,
        is_cancelled_fn=is_cancelled_fn,
    )
    suite_run.duration_ms = int((time.monotonic() - total_start) * 1000)
    await db.commit()
    record_outcome_fn("suite", suite_run.status)


# Backward-compatibility aliases
_normalize_suite_config = normalize_suite_config
_suite_run_should_stop = suite_run_should_stop
_create_case_run = create_case_run
_execute_case_run = execute_case_run
_mark_flaky_case_results = mark_flaky_case_results
_execute_suite_cases = execute_suite_cases
_execute_suite_inline = execute_suite_inline
