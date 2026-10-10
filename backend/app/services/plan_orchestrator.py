import asyncio
import logging
import time
from app.core.config import settings
from app.services.local_group_control import is_group_cancelled
from app.services.suite_orchestrator import (
    execute_suite_inline,
    suite_run_should_stop,
)

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


def normalize_plan_config(config: dict | None) -> dict:
    """与 normalize_suite_config 一致的结构，但默认 max_workers=3
    （计划内套件数通常远少于套件内用例数）。"""
    raw = config if isinstance(config, dict) else {}
    execution_mode = raw.get("execution_mode")
    if execution_mode not in {"sequential", "parallel"}:
        execution_mode = "sequential"
    if settings.ATP_LOCAL_MODE:
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


def plan_run_should_stop(counts: dict, total: int, fail_strategy: str, min_pass_rate: float) -> bool:
    """plan 级停止策略，逻辑与 suite_run_should_stop 一致。"""
    return suite_run_should_stop(counts, total, fail_strategy, min_pass_rate)


async def execute_plan_suite(
    *,
    plan_meta: dict,
    suite_id: int,
    extra_vars: dict,
    execution_queue: str = "default",
    run_case_task=None,
    execute_suite_inline_fn=None,
    is_cancelled_fn=None,
) -> dict:
    if is_cancelled_fn is None:
        is_cancelled_fn = is_group_cancelled
    if execute_suite_inline_fn is None:
        execute_suite_inline_fn = execute_suite_inline
    """plan 内单个 suite 的独立执行入口。

    每次调用使用独立的 ``AsyncSessionLocal``，便于在 plan 并发模式下安全并行
    多个 suite。``plan_meta`` 必须包含 ``triggered_by`` / ``creator_id`` / ``trace_id``。
    """
    from app.core.database import AsyncSessionLocal
    from app.models.suite import SuiteRun, SuiteRunStatus, TestSuite

    async with AsyncSessionLocal() as db:
        from app.models.plan import PlanRun
        from app.services.group_execution import record_child

        parent = await db.get(PlanRun, plan_meta.get("plan_run_id")) if plan_meta.get("plan_run_id") else None
        if (
            parent is None
            or parent.identity_token != plan_meta.get("plan_identity")
            or parent.status.value != "running"
            or is_cancelled_fn("plan", parent.id, parent.identity_token)
        ):
            return {"suite_id": suite_id, "suite_run_id": None, "status": "skipped", "error": "计划身份变化或已取消"}
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
        await db.flush()
        await record_child(db, kind="plan", parent=parent, child=suite_run)
        await db.commit()
        await db.refresh(suite_run)

        if settings.ATP_LOCAL_MODE and plan_meta.get("plan_run_id"):
            parent = await db.get(PlanRun, plan_meta["plan_run_id"])
            if parent is not None:
                parent.suite_run_ids = [
                    *(parent.suite_run_ids or []),
                    {"suite_id": suite_id, "suite_run_id": suite_run.id, "status": "pending"},
                ]
                await db.commit()

        try:
            await execute_suite_inline_fn(
                db,
                suite_run,
                suite,
                extra_vars,
                execution_queue=execution_queue,
                run_case_task=run_case_task,
                is_cancelled_fn=is_cancelled_fn,
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


async def execute_plan_suites(
    db,
    plan_run,
    plan,
    extra_vars: dict,
    *,
    execution_queue: str = "default",
    run_case_task=None,
    execute_plan_suite_fn=None,
    is_cancelled_fn=None,
) -> dict:
    if is_cancelled_fn is None:
        is_cancelled_fn = is_group_cancelled
    if execute_plan_suite_fn is None:
        execute_plan_suite_fn = execute_plan_suite
    """编排执行测试计划内包含的所有套件，更新 plan_run 状态与汇总结果。"""
    from app.models.plan import PlanRunStatus

    total_start = time.monotonic()
    plan_config = normalize_plan_config(plan.config)
    suite_items = sorted(plan.suite_ids or [], key=lambda x: x.get("sort", 0))
    total_suites = len(suite_items)
    suite_run_results: list[dict] = []
    counts = {"total": 0, "passed": 0, "failed": 0, "error": 0}
    plan_meta = {
        "plan_run_id": plan_run.id,
        "plan_identity": plan_run.identity_token,
        "triggered_by": plan_run.triggered_by,
        "creator_id": plan.creator_id,
        "trace_id": plan_run.trace_id,
    }

    def _accumulate(result: dict) -> bool:
        """累计单个 suite 执行结果，返回是否应当提前停止。"""
        suite_run_results.append(result)
        status_str = result.get("status", "error")
        counts["total"] += 1
        if status_str in counts:
            counts[status_str] += 1
        return plan_run_should_stop(
            counts,
            total_suites,
            plan_config["fail_strategy"],
            plan_config["min_pass_rate"],
        )

    valid_items = [item for item in suite_items if item.get("suite_id")]

    if plan_config["execution_mode"] == "parallel" and len(valid_items) > 1:
        stopped = False
        for start in range(0, len(valid_items), plan_config["max_workers"]):
            if is_cancelled_fn("plan", plan_run.id, plan_run.identity_token):
                break
            batch = valid_items[start : start + plan_config["max_workers"]]
            batch_results = await asyncio.gather(
                *(
                    execute_plan_suite_fn(
                        plan_meta=plan_meta,
                        suite_id=item["suite_id"],
                        extra_vars=extra_vars,
                        execution_queue=execution_queue,
                        run_case_task=run_case_task,
                        is_cancelled_fn=is_cancelled_fn,
                    )
                    for item in batch
                )
            )
            for result in batch_results:
                if _accumulate(result):
                    stopped = True
            if stopped:
                break
    else:
        for item in valid_items:
            if is_cancelled_fn("plan", plan_run.id, plan_run.identity_token):
                break
            result = await execute_plan_suite_fn(
                plan_meta=plan_meta,
                suite_id=item["suite_id"],
                extra_vars=extra_vars,
                execution_queue=execution_queue,
                run_case_task=run_case_task,
                is_cancelled_fn=is_cancelled_fn,
            )
            should_stop = _accumulate(result)
            if settings.ATP_LOCAL_MODE:
                plan_run.suite_run_ids = list(suite_run_results)
                plan_run.result_summary = {**counts, **plan_config}
                await db.commit()
            if should_stop:
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
    if is_cancelled_fn("plan", plan_run.id, plan_run.identity_token):
        plan_run.status = PlanRunStatus.error
        plan_run.error_message = "计划已请求停止或执行归属无法确认；当前批次已结束，后续套件未继续执行"
    plan_run.duration_ms = total_ms
    plan_run.suite_run_ids = suite_run_results
    plan_run.result_summary = {**counts, **plan_config}

    return {
        "counts": counts,
        "plan_config": plan_config,
        "suite_run_results": suite_run_results,
    }


# Backward-compatibility aliases
_normalize_plan_config = normalize_plan_config
_plan_run_should_stop = plan_run_should_stop
_execute_plan_suite = execute_plan_suite
_execute_plan_suites = execute_plan_suites
