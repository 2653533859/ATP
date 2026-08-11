import asyncio
import logging

from app.worker.celery_app import celery_app
from app.worker.case_dispatch import dispatch_case
from app.models.bootstrap import load_all_models
from app.core.redis_client import publish_run_event, delete_json_cache_pattern
from app.core.encryption import decrypt_env_vars
from app.core.tracing import (
    attach_app_trace_id_to_current_span,
    generate_trace_id,
    reset_trace_id,
    set_trace_id,
)
from app.worker.async_runner import run_async

logger = logging.getLogger(__name__)

load_all_models()


async def _safe_publish_run_event(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        logger.exception(f"Failed to publish run event for run {run_id}: {payload.get('type')}")


def _normalize_suite_config(config: dict | None) -> dict:
    raw = config if isinstance(config, dict) else {}
    execution_mode = raw.get("execution_mode")
    if execution_mode not in {"sequential", "parallel"}:
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


def _suite_run_should_stop(counts: dict, total: int, fail_strategy: str, min_pass_rate: float) -> bool:
    if total <= 0:
        return False
    if fail_strategy == "fast-fail":
        return counts["failed"] > 0 or counts["error"] > 0
    if fail_strategy != "require-minimum-pass-rate":
        return False

    remaining = total - counts["total"]
    max_possible_passed = counts["passed"] + remaining
    return (max_possible_passed / total) < min_pass_rate


def _normalize_plan_config(config: dict | None) -> dict:
    """与 _normalize_suite_config 一致的结构，但默认 max_workers=3
    （计划内套件数通常远少于套件内用例数）。"""
    raw = config if isinstance(config, dict) else {}
    execution_mode = raw.get("execution_mode")
    if execution_mode not in {"sequential", "parallel"}:
        execution_mode = "sequential"

    max_workers = raw.get("max_workers", 3)
    try:
        max_workers = int(max_workers)
    except (TypeError, ValueError):
        max_workers = 3
    max_workers = max(1, min(max_workers, 10))

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


def _plan_run_should_stop(counts: dict, total: int, fail_strategy: str, min_pass_rate: float) -> bool:
    """plan 级停止策略，逻辑与 _suite_run_should_stop 一致。"""
    return _suite_run_should_stop(counts, total, fail_strategy, min_pass_rate)


def _celery_task_queue(task: object) -> str:
    """Return the queue that delivered a bound Celery task.

    Direct unit-test calls and older task contexts have no delivery metadata;
    those calls intentionally behave like the default orchestration Worker.
    """

    request = getattr(task, "request", None)
    delivery_info = getattr(request, "delivery_info", None)
    if not isinstance(delivery_info, dict):
        return "default"
    queue = delivery_info.get("routing_key") or delivery_info.get("queue")
    return str(queue).strip() if queue else "default"


async def _create_case_run(db, suite_run, case_id: int):
    from app.models.case import TestRun, RunStatus

    case_run = TestRun(
        case_id=case_id,
        triggered_by=suite_run.triggered_by,
        trace_id=suite_run.trace_id,
        status=RunStatus.pending,
        environment=suite_run.environment,
    )
    db.add(case_run)
    await db.commit()
    await db.refresh(case_run)
    return case_run


async def _execute_case_run(db, suite_run, case, extra_vars: dict, *, route_to_worker: bool = False) -> dict:
    from app.models.case import RunStatus

    case_run = await _create_case_run(db, suite_run, case.id)

    try:
        if route_to_worker:
            from app.core.config import settings
            from app.services.execution_routing import enqueue_case_run

            await db.commit()
            enqueue_case_run(run_test_case, case_run.id, extra_vars, suite_run.trace_id, case.case_type)
            deadline = asyncio.get_running_loop().time() + max(1, settings.SUITE_CHILD_TASK_TIMEOUT_SECONDS)
            while asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.2)
                await db.refresh(case_run)
                if case_run.status in {RunStatus.passed, RunStatus.failed, RunStatus.error, RunStatus.skipped}:
                    break
            else:
                case_run.status = RunStatus.error
                case_run.error_message = "专用 Worker 执行超时，请检查设备 Worker 是否在线并监听正确队列"
                await db.commit()
        else:
            case_run.status = RunStatus.running
            await db.commit()
            await dispatch_case(db, case_run, case, extra_vars)
        await db.refresh(case_run)
        _record_run_outcome("case", case_run.status)
    except Exception as e:
        logger.exception(f"Suite case {case.id} run failed: {e}")
        case_run.status = RunStatus.error
        case_run.error_message = str(e)[:500]
        await db.commit()
        _record_run_outcome("case", case_run.status)

    await db.refresh(case_run)
    return {
        "case_id": case.id,
        "case_name": case.name,
        "run_id": case_run.id,
        "status": case_run.status.value,
    }


async def _mark_flaky_case_results(db, case_run_results: list[dict]) -> None:
    from sqlalchemy import func, select

    from app.models.case import RunStatus, TestRun

    case_ids = sorted({item.get("case_id") for item in case_run_results if item.get("case_id")})
    if not case_ids:
        return

    window_size = 10
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
            TestRun.status.in_([RunStatus.passed, RunStatus.failed, RunStatus.error]),
            TestRun.parent_run_id.is_(None),
        )
        .subquery()
    )
    rows = (await db.execute(select(ranked.c.case_id, ranked.c.status).where(ranked.c.rn <= window_size))).all()
    stats = {case_id: {"total": 0, "passed": 0, "failed": 0, "error": 0} for case_id in case_ids}
    for row in rows:
        item = stats[row.case_id]
        item["total"] += 1
        status = row.status.value if hasattr(row.status, "value") else str(row.status)
        if status in item:
            item[status] += 1

    for result in case_run_results:
        case_id = result.get("case_id")
        item = stats.get(case_id)
        if not item:
            continue
        failure_runs = item["failed"] + item["error"]
        result["flaky"] = item["total"] >= 4 and item["passed"] > 0 and failure_runs > 0
        result["flaky_failure_rate"] = round(failure_runs / item["total"] * 100, 1) if item["total"] else 0.0


async def _execute_suite_cases(db, suite_run, suite, extra_vars: dict, *, execution_queue: str = "default"):
    from app.models.case import TestCase
    from app.models.suite import SuiteRunStatus

    case_items = sorted(suite.case_ids or [], key=lambda x: x.get("sort", 0))
    suite_config = _normalize_suite_config(suite.config)
    total_cases = len(case_items)
    case_run_results: list[dict] = []
    counts = {"total": 0, "passed": 0, "failed": 0, "error": 0, "skipped": 0}

    # Device-bound children run inline only when the parent is already on the
    # matching dedicated queue. This also covers a homogeneous device suite
    # inside a mixed plan, whose parent plan task must stay on the default
    # orchestration queue.
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

    async def run_one(item: dict) -> dict:
        case_id = item.get("case_id")
        if not case_id:
            return {"ignored": True}

        case = await db.get(TestCase, case_id)
        if not case:
            return {
                "case_id": case_id,
                "run_id": None,
                "status": "error",
                "error": "用例不存在",
            }

        if case.id in remote_case_ids:
            return await _execute_case_run(db, suite_run, case, extra_vars, route_to_worker=True)
        return await _execute_case_run(db, suite_run, case, extra_vars)

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
        return _suite_run_should_stop(
            counts,
            total_cases,
            suite_config["fail_strategy"],
            suite_config["min_pass_rate"],
        )

    if suite_config["execution_mode"] == "parallel":
        for start in range(0, total_cases, suite_config["max_workers"]):
            batch = case_items[start : start + suite_config["max_workers"]]
            for result in await asyncio.gather(*(run_one(item) for item in batch)):
                should_stop = await consume_result(result)
                if should_stop:
                    break
            if _suite_run_should_stop(
                counts,
                total_cases,
                suite_config["fail_strategy"],
                suite_config["min_pass_rate"],
            ):
                break
    else:
        for item in case_items:
            should_stop = await consume_result(await run_one(item))
            if should_stop:
                break

    skipped_items = case_items[counts["total"] :]
    for item in skipped_items:
        case_id = item.get("case_id")
        if not case_id:
            continue
        case_run_results.append(
            {
                "case_id": case_id,
                "run_id": None,
                "status": "skipped",
                "error": "已根据套件失败策略提前停止",
            }
        )
        counts["total"] += 1
        counts["skipped"] += 1

    all_passed = counts["failed"] == 0 and counts["error"] == 0
    suite_run.status = SuiteRunStatus.passed if all_passed else SuiteRunStatus.failed
    await _mark_flaky_case_results(db, case_run_results)
    suite_run.case_run_ids = case_run_results
    suite_run.result_summary = {
        **counts,
        **suite_config,
    }


async def _safe_invalidate_stats_cache() -> None:
    try:
        await delete_json_cache_pattern("atp:stats:*")
    except Exception:
        logger.exception("Failed to invalidate stats cache")


def _record_run_outcome(entity_type: str, status: object) -> None:
    """Best-effort Prometheus signal for run success-rate SLOs."""
    status_value = status.value if hasattr(status, "value") else str(status)
    if status_value not in {"passed", "failed", "error", "skipped"}:
        return
    try:
        from app.core.metrics import RUN_OUTCOMES

        RUN_OUTCOMES.labels(entity_type=entity_type, status=status_value).inc()
    except Exception:
        logger.exception("Failed to record run outcome metric")


@celery_app.task(bind=True, name="run_test_case")
def run_test_case(self, run_id: int, extra_vars: dict, trace_id: str | None = None):
    """统一执行入口，根据用例类型路由到对应执行器。

    P3.B MVP-B：若 case 绑定了 dataset 且当前 run 不是 child run（无 parent_run_id），
    则将当前 run 作为 parent 容器：按 dataset.rows 创建 N 个 child run，每个 child
    单独 dispatch_case；child 之间的失败互不影响。parent 状态根据 child 聚合。
    """
    from app.core.database import AsyncSessionLocal
    from app.models.case import TestRun, TestCase, RunStatus
    from sqlalchemy import select

    async def _execute():
        token = set_trace_id(trace_id or generate_trace_id())
        attach_app_trace_id_to_current_span()
        try:
            async with AsyncSessionLocal() as db:
                run = await db.get(TestRun, run_id)
                if not run:
                    logger.error(f"Run {run_id} not found")
                    return

                if not run.trace_id:
                    run.trace_id = trace_id or generate_trace_id()
                    await db.commit()

                case = await db.get(TestCase, run.case_id)

                # ── P3.B 参数化分支 ──────────────────────────
                if case is not None and case.dataset_id is not None and run.parent_run_id is None:
                    await _execute_parameterized(db, run, case, extra_vars)
                    return

                run.status = RunStatus.running
                await db.commit()

                try:
                    # 通知前端开始执行（发布失败不影响执行状态）
                    await _safe_publish_run_event(run_id, {"type": "run_status", "run_id": run_id, "status": "running"})

                    dispatched = await dispatch_case(db, run, case, extra_vars)
                    await db.refresh(run)
                    _record_run_outcome("case", run.status)
                    if not dispatched:
                        await _safe_publish_run_event(
                            run_id,
                            {
                                "type": "completed",
                                "run_id": run_id,
                                "status": "error",
                            },
                        )
                except Exception as e:
                    logger.exception(f"Run {run_id} failed with error: {e}")
                    run.status = RunStatus.error
                    run.error_message = str(e)
                    await db.commit()
                    _record_run_outcome("case", run.status)
                    await _safe_publish_run_event(
                        run_id,
                        {
                            "type": "completed",
                            "run_id": run_id,
                            "status": "error",
                        },
                    )
                finally:
                    await _safe_invalidate_stats_cache()
        finally:
            reset_trace_id(token)

    run_async(_execute())


async def _execute_parameterized(db, parent_run, case, extra_vars: dict) -> None:
    """按 case.dataset 的 rows 依次执行 N 次 child runs，聚合状态写回 parent。"""
    from app.models.case import RunStatus, TestRun
    from app.models.dataset import TestDataset, TestDatasetVersion
    from app.services.dataset_execution import DatasetExecutionError, build_dataset_iterations, redact_dataset_row
    from sqlalchemy import select
    from app.services.dataset_schema import DatasetSchemaField, validate_dataset_rows

    dataset = await db.get(TestDataset, case.dataset_id)
    dataset_source = dataset
    dataset_version = getattr(case, "dataset_version", None)
    if dataset_version is not None:
        version_result = await db.execute(
            select(TestDatasetVersion)
            .where(
                TestDatasetVersion.dataset_id == case.dataset_id,
                TestDatasetVersion.version == dataset_version,
            )
            .limit(1)
        )
        dataset_source = version_result.scalar_one_or_none()
        if dataset_source is None:
            parent_run.status = RunStatus.error
            parent_run.error_message = f"Dataset version {dataset_version} not found"
            parent_run.result_summary = {
                **(parent_run.result_summary or {}),
                "dataset_version": dataset_version,
                "dataset_version_missing": True,
            }
            await db.commit()
            _record_run_outcome("case", parent_run.status)
            await _safe_publish_run_event(
                parent_run.id,
                {"type": "completed", "run_id": parent_run.id, "status": "error"},
            )
            await _safe_invalidate_stats_cache()
            return

    rows = list(dataset_source.rows or []) if dataset_source else []
    case_config = getattr(case, "config", None) or {}
    try:
        rows = build_dataset_iterations(
            rows,
            strategy=case_config.get("dataset_strategy", "sequential"),
            fixed_count=case_config.get("dataset_fixed_count"),
            seed=case_config.get("dataset_seed"),
            max_iterations=case_config.get("dataset_max_iterations", 1000),
            combination_fields=case_config.get("dataset_combination_fields"),
        )
    except DatasetExecutionError as exc:
        parent_run.status = RunStatus.error
        parent_run.error_message = str(exc)
        parent_run.result_summary = {
            **(parent_run.result_summary or {}),
            "dataset_execution_strategy": case_config.get("dataset_strategy", "sequential"),
            "dataset_execution_error": str(exc),
        }
        await db.commit()
        _record_run_outcome("case", parent_run.status)
        await _safe_publish_run_event(
            parent_run.id,
            {"type": "completed", "run_id": parent_run.id, "status": "error"},
        )
        await _safe_invalidate_stats_cache()
        return
    if not rows:
        # 数据集空 → 直接降级为单次执行（保留旧行为，避免空入参）
        parent_run.status = RunStatus.running
        await db.commit()
        await dispatch_case(db, parent_run, case, extra_vars)
        await db.refresh(parent_run)
        _record_run_outcome("case", parent_run.status)
        await _safe_invalidate_stats_cache()
        return

    schema_fields = [
        DatasetSchemaField(
            name=str(field.get("name", "")),
            type=field.get("type", "string"),
            required=bool(field.get("required", False)),
            default=field.get("default"),
        )
        for field in (getattr(dataset_source, "schema_fields", None) or [])
        if isinstance(field, dict) and field.get("name")
    ]
    strict_schema = bool((getattr(case, "config", None) or {}).get("dataset_strict_schema")) or (
        getattr(dataset_source, "validation_policy", "soft") == "hard"
    )
    validation = validate_dataset_rows(rows=rows, schema=schema_fields, preview_limit=0)
    if strict_schema and not validation.valid:
        parent_run.status = RunStatus.error
        parent_run.error_message = f"Dataset schema validation failed: {len(validation.issues)} issue(s)"
        parent_run.result_summary = {
            **(parent_run.result_summary or {}),
            "iteration_total": len(rows),
            "iteration_passed": 0,
            "iteration_failed": 0,
            "iteration_error": 0,
            "dataset_schema_valid": False,
            "dataset_schema_issue_count": len(validation.issues),
            "dataset_strict_schema": True,
        }
        await db.commit()
        _record_run_outcome("case", parent_run.status)
        await _safe_publish_run_event(
            parent_run.id,
            {
                "type": "completed",
                "run_id": parent_run.id,
                "status": "error",
            },
        )
        await _safe_invalidate_stats_cache()
        return

    parent_run.status = RunStatus.running
    parent_run.result_summary = {
        **(parent_run.result_summary or {}),
        "iteration_total": len(rows),
        "iteration_passed": 0,
        "iteration_failed": 0,
        "iteration_error": 0,
        "dataset_execution_strategy": case_config.get("dataset_strategy", "sequential"),
        "dataset_schema_valid": validation.valid,
        "dataset_schema_issue_count": len(validation.issues),
        "dataset_strict_schema": strict_schema,
    }
    await db.commit()
    await _safe_publish_run_event(
        parent_run.id,
        {
            "type": "run_status",
            "run_id": parent_run.id,
            "status": "running",
        },
    )

    summary_counts = {"passed": 0, "failed": 0, "error": 0}
    redact_fields = case_config.get("dataset_redact_fields") or []

    for idx, row in enumerate(rows):
        raw_iteration_data = row if isinstance(row, dict) else {"value": row}
        persisted_iteration_data = redact_dataset_row(raw_iteration_data, redact_fields)
        child = TestRun(
            case_id=case.id,
            triggered_by=parent_run.triggered_by,
            trace_id=parent_run.trace_id,
            status=RunStatus.running,
            environment=parent_run.environment,
            iteration_index=idx,
            iteration_data=persisted_iteration_data,
            parent_run_id=parent_run.id,
        )
        db.add(child)
        await db.commit()
        await db.refresh(child)

        merged_vars = {**(extra_vars or {}), **raw_iteration_data}
        try:
            await dispatch_case(db, child, case, merged_vars)
            await db.refresh(child)
            status_str = child.status.value if hasattr(child.status, "value") else str(child.status)
        except Exception as exc:
            logger.exception(f"Parameterized child run {child.id} failed: {exc}")
            child.status = RunStatus.error
            child.error_message = str(exc)[:500]
            await db.commit()
            status_str = "error"
        _record_run_outcome("case", child.status)

        if status_str == "passed":
            summary_counts["passed"] += 1
        elif status_str == "failed":
            summary_counts["failed"] += 1
        else:
            summary_counts["error"] += 1

    # 聚合 parent 状态
    if summary_counts["error"] > 0:
        parent_run.status = RunStatus.error
    elif summary_counts["failed"] > 0:
        parent_run.status = RunStatus.failed
    else:
        parent_run.status = RunStatus.passed

    parent_run.result_summary = {
        **(parent_run.result_summary or {}),
        "iteration_total": len(rows),
        "iteration_passed": summary_counts["passed"],
        "iteration_failed": summary_counts["failed"],
        "iteration_error": summary_counts["error"],
    }
    await db.commit()
    _record_run_outcome("case", parent_run.status)
    await _safe_publish_run_event(
        parent_run.id,
        {
            "type": "completed",
            "run_id": parent_run.id,
            "status": parent_run.status.value,
        },
    )
    await _safe_invalidate_stats_cache()


@celery_app.task(bind=True, name="run_test_suite")
def run_test_suite(self, suite_run_id: int, extra_vars: dict, trace_id: str | None = None):
    """套件执行入口：按配置顺序或分批并发执行套件内用例"""
    from app.core.database import AsyncSessionLocal
    from app.models.suite import TestSuite, SuiteRun, SuiteRunStatus
    import time

    async def _execute():
        token = set_trace_id(trace_id or generate_trace_id())
        attach_app_trace_id_to_current_span()
        try:
            async with AsyncSessionLocal() as db:
                suite_run = await db.get(SuiteRun, suite_run_id)
                if not suite_run:
                    logger.error(f"SuiteRun {suite_run_id} not found")
                    return

                if not suite_run.trace_id:
                    suite_run.trace_id = trace_id or generate_trace_id()
                    await db.commit()

                suite = await db.get(TestSuite, suite_run.suite_id)
                if not suite:
                    suite_run.status = SuiteRunStatus.error
                    suite_run.error_message = "套件不存在"
                    await db.commit()
                    _record_run_outcome("suite", suite_run.status)
                    return

                suite_run.status = SuiteRunStatus.running
                await db.commit()

                total_start = time.monotonic()
                await _execute_suite_cases(
                    db,
                    suite_run,
                    suite,
                    extra_vars,
                    execution_queue=_celery_task_queue(self),
                )
                suite_run.duration_ms = int((time.monotonic() - total_start) * 1000)
                await db.commit()
                _record_run_outcome("suite", suite_run.status)

                counts = suite_run.result_summary or {}

                try:
                    from app.services.notifier import (
                        email_html_report_enabled,
                        send_notifications,
                    )

                    report_html = None
                    if await email_html_report_enabled(db, suite.project_id):
                        try:
                            from app.api.v1.exports import _build_suite_run_report_html

                            report_html = await _build_suite_run_report_html(db, suite_run)
                        except Exception as exc:
                            logger.warning(f"Suite report HTML build failed: {exc}")
                    await send_notifications(
                        db,
                        suite.project_id,
                        {
                            "title": f"测试套件「{suite.name}」执行完成",
                            "status": suite_run.status.value,
                            "total": counts.get("total", 0),
                            "passed": counts.get("passed", 0),
                            "failed": counts.get("failed", 0),
                            "error": counts.get("error", 0),
                            "duration_ms": suite_run.duration_ms,
                            "trigger_type": "manual",
                            "entity_type": "suite",
                            "suite_id": suite.id,
                        },
                        report_html=report_html,
                    )
                except Exception as e:
                    logger.warning(f"Suite notification failed: {e}")
                finally:
                    await _safe_invalidate_stats_cache()
        finally:
            reset_trace_id(token)

    run_async(_execute())


@celery_app.task(bind=True, name="run_test_plan")
def run_test_plan(self, plan_run_id: int, extra_vars: dict, trace_id: str | None = None):
    """测试计划执行入口：按配置顺序或分批并发执行计划内所有套件"""
    from app.core.database import AsyncSessionLocal
    from app.models.plan import TestPlan, PlanRun, PlanRunStatus
    from app.models.suite import TestSuite, SuiteRun, SuiteRunStatus
    import time
    from datetime import datetime, timezone

    async def _execute():
        token = set_trace_id(trace_id or generate_trace_id())
        attach_app_trace_id_to_current_span()
        try:
            async with AsyncSessionLocal() as db:
                plan_run = await db.get(PlanRun, plan_run_id)
                if not plan_run:
                    logger.error(f"PlanRun {plan_run_id} not found")
                    return

                if not plan_run.trace_id:
                    plan_run.trace_id = trace_id or generate_trace_id()
                    await db.commit()

                plan = await db.get(TestPlan, plan_run.plan_id)
                if not plan:
                    plan_run.status = PlanRunStatus.error
                    plan_run.error_message = "测试计划不存在"
                    await db.commit()
                    _record_run_outcome("plan", plan_run.status)
                    return

                plan_run.status = PlanRunStatus.running
                await db.commit()

                total_start = time.monotonic()
                plan_config = _normalize_plan_config(plan.config)
                suite_items = sorted(plan.suite_ids or [], key=lambda x: x.get("sort", 0))
                total_suites = len(suite_items)
                suite_run_results: list[dict] = []
                counts = {"total": 0, "passed": 0, "failed": 0, "error": 0}
                plan_meta = {
                    "triggered_by": plan_run.triggered_by,
                    "creator_id": plan.creator_id,
                    "trace_id": plan_run.trace_id,
                }
                execution_queue = _celery_task_queue(self)

                def _accumulate(result: dict) -> bool:
                    """累计单个 suite 执行结果，返回是否应当提前停止。"""
                    suite_run_results.append(result)
                    status_str = result.get("status", "error")
                    counts["total"] += 1
                    if status_str in counts:
                        counts[status_str] += 1
                    return _plan_run_should_stop(
                        counts,
                        total_suites,
                        plan_config["fail_strategy"],
                        plan_config["min_pass_rate"],
                    )

                valid_items = [item for item in suite_items if item.get("suite_id")]

                if plan_config["execution_mode"] == "parallel" and len(valid_items) > 1:
                    stopped = False
                    for start in range(0, len(valid_items), plan_config["max_workers"]):
                        batch = valid_items[start : start + plan_config["max_workers"]]
                        batch_results = await asyncio.gather(
                            *(
                                _execute_plan_suite(
                                    plan_meta=plan_meta,
                                    suite_id=item["suite_id"],
                                    extra_vars=extra_vars,
                                    execution_queue=execution_queue,
                                )
                                for item in batch
                            )
                        )
                        for result in batch_results:
                            if _accumulate(result):
                                stopped = True
                                break
                        if stopped:
                            break
                else:
                    for item in valid_items:
                        result = await _execute_plan_suite(
                            plan_meta=plan_meta,
                            suite_id=item["suite_id"],
                            extra_vars=extra_vars,
                            execution_queue=execution_queue,
                        )
                        if _accumulate(result):
                            break

                # 早停或并发批次结束后剩余未执行的 suite 标记为 skipped
                executed_suite_ids = {r.get("suite_id") for r in suite_run_results}
                for item in valid_items:
                    suite_id = item["suite_id"]
                    if suite_id in executed_suite_ids:
                        continue
                    suite_run_results.append(
                        {
                            "suite_id": suite_id,
                            "suite_run_id": None,
                            "status": "skipped",
                            "error": "已根据计划失败策略提前停止",
                        }
                    )

                total_ms = int((time.monotonic() - total_start) * 1000)
                all_passed = counts["failed"] == 0 and counts["error"] == 0
                plan_run.status = PlanRunStatus.passed if all_passed else PlanRunStatus.failed
                plan_run.duration_ms = total_ms
                plan_run.suite_run_ids = suite_run_results
                plan_run.result_summary = {**counts, **plan_config}

                if plan.auto_create_bugs and suite_run_results:
                    try:
                        from sqlalchemy import select
                        from app.models.case import TestCase, TestRun
                        from app.models.bug_tracker import BugTracker
                        from app.services.bug_reporter import (
                            create_bug,
                            find_duplicate_bug,
                            upload_attachment,
                            build_bug_description,
                        )
                        from app.core.minio_client import read_bytes
                        from app.core.encryption import decrypt_config
                        from app.api.v1.exports import _extract_minio_object

                        bug_trackers_result = await db.execute(
                            select(BugTracker).where(
                                BugTracker.project_id == plan.project_id, BugTracker.is_enabled == True
                            )
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
                                        bug_results.append(
                                            {"case_id": case.id, "bug_id": duplicate["bug_id"], "duplicate": True}
                                        )
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
                                        select(__import__("app.models.case", fromlist=["StepResult"]).StepResult).where(
                                            __import__("app.models.case", fromlist=["StepResult"]).StepResult.run_id
                                            == case_run.id,
                                            __import__(
                                                "app.models.case", fromlist=["StepResult"]
                                            ).StepResult.screenshot_url.isnot(None),
                                        )
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
                                    bug_results.append(
                                        {
                                            "case_id": case.id,
                                            "bug_id": created["bug_id"],
                                            "bug_url": created["bug_url"],
                                            "duplicate": False,
                                            "attachment_uploaded": attachment_uploaded,
                                        }
                                    )
                        plan_run.result_summary = {**counts, **plan_config, "auto_bugs": bug_results}
                    except Exception as e:
                        logger.warning(f"Auto create bugs for plan failed: {e}")
                        plan_run.result_summary = {**counts, **plan_config, "auto_bugs_error": str(e)[:500]}

                plan.last_run_at = datetime.now(timezone.utc)
                if plan.schedule_type.value == "cron" and plan.cron_expression:
                    try:
                        from croniter import croniter

                        cron = croniter(plan.cron_expression, datetime.now(timezone.utc))
                        plan.next_run_at = cron.get_next(datetime)
                    except Exception:
                        pass
                await db.commit()
                _record_run_outcome("plan", plan_run.status)

                # 发送通知
                try:
                    from app.services.notifier import (
                        email_html_report_enabled,
                        send_notifications,
                    )

                    report_html = None
                    if await email_html_report_enabled(db, plan.project_id):
                        try:
                            from app.api.v1.exports import _build_plan_run_report_html

                            report_html = await _build_plan_run_report_html(db, plan_run)
                        except Exception as exc:
                            logger.warning(f"Plan report HTML build failed: {exc}")
                    await send_notifications(
                        db,
                        plan.project_id,
                        {
                            "title": f"测试计划「{plan.name}」执行完成",
                            "status": plan_run.status.value,
                            **counts,
                            "duration_ms": total_ms,
                            "trigger_type": plan_run.trigger_type.value,
                            "entity_type": "plan",
                            "plan_id": plan.id,
                        },
                        report_html=report_html,
                    )
                except Exception as e:
                    logger.warning(f"Plan notification failed: {e}")
                finally:
                    await _safe_invalidate_stats_cache()
        finally:
            reset_trace_id(token)

    run_async(_execute())


async def _execute_suite_inline(db, suite_run, suite, extra_vars, *, execution_queue: str = "default"):
    """内联执行套件（在 plan 上下文中直接调用，避免嵌套 Celery 任务）"""
    from app.models.suite import SuiteRunStatus
    import time

    suite_run.status = SuiteRunStatus.running
    await db.commit()

    total_start = time.monotonic()
    await _execute_suite_cases(db, suite_run, suite, extra_vars, execution_queue=execution_queue)
    suite_run.duration_ms = int((time.monotonic() - total_start) * 1000)
    await db.commit()
    _record_run_outcome("suite", suite_run.status)


async def _execute_plan_suite(
    *,
    plan_meta: dict,
    suite_id: int,
    extra_vars: dict,
    execution_queue: str = "default",
) -> dict:
    """plan 内单个 suite 的独立执行入口。

    每次调用使用独立的 ``AsyncSessionLocal``，便于在 plan 并发模式下安全并行
    多个 suite。``plan_meta`` 必须包含 ``triggered_by`` / ``creator_id`` / ``trace_id``。
    """
    from app.core.database import AsyncSessionLocal
    from app.models.suite import TestSuite, SuiteRun, SuiteRunStatus

    async with AsyncSessionLocal() as db:
        suite = await db.get(TestSuite, suite_id)
        if not suite:
            return {
                "suite_id": suite_id,
                "suite_run_id": None,
                "status": "error",
                "error": "套件不存在",
            }

        triggered_by = plan_meta.get("triggered_by")
        if triggered_by is None:
            triggered_by = plan_meta.get("creator_id")

        suite_run = SuiteRun(
            suite_id=suite_id,
            triggered_by=triggered_by,
            trace_id=plan_meta.get("trace_id"),
            status=SuiteRunStatus.pending,
        )
        db.add(suite_run)
        await db.commit()
        await db.refresh(suite_run)

        try:
            await _execute_suite_inline(
                db,
                suite_run,
                suite,
                extra_vars,
                execution_queue=execution_queue,
            )
        except Exception as exc:
            logger.exception(f"Plan suite {suite_id} run failed: {exc}")
            suite_run.status = SuiteRunStatus.error
            suite_run.error_message = str(exc)[:500]
            await db.commit()
            _record_run_outcome("suite", suite_run.status)

        await db.refresh(suite_run)
        return {
            "suite_id": suite_id,
            "suite_name": suite.name,
            "suite_run_id": suite_run.id,
            "status": suite_run.status.value,
        }


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
                        ev_result = await db.execute(select(EnvVariable).where(EnvVariable.env_id == env.id))
                        merged_vars = decrypt_env_vars(ev_result.scalars().all())

                plan_run = PlanRun(
                    plan_id=plan.id,
                    triggered_by=None,
                    trace_id=generate_trace_id(),
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

                from app.services.execution_routing import enqueue_task, resolve_plan_execution_queue

                queue = await resolve_plan_execution_queue(db, plan)
                enqueue_task(run_test_plan, (plan_run.id, merged_vars, plan_run.trace_id), queue)
                logger.info(f"Cron triggered plan {plan.id} -> PlanRun {plan_run.id}")

    run_async(_check())


@celery_app.task(name="check_dashboard_alerts")
def check_dashboard_alerts():
    """每小时检查启用的看板告警规则，触发事件并发送通知。"""
    from app.core.database import AsyncSessionLocal
    from app.services.dashboard_alerts import evaluate_dashboard_alerts

    async def _check():
        async with AsyncSessionLocal() as db:
            return await evaluate_dashboard_alerts(db)

    try:
        return run_async(_check())
    except Exception:
        logger.exception("Dashboard alert check failed")
        return {"error": True}
