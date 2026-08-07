"""Celery tasks for HTTP performance testing."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.encryption import decrypt
from app.models.bootstrap import load_all_models
from app.models.performance_node import PerformanceNode
from app.services.performance_control import clear_cancel_request, create_control_client, is_cancel_requested
from app.services.performance_options import ENVIRONMENT_SNAPSHOT_KEY
from app.services.performance_node import (
    PerformanceNodeConstraintError,
    effective_node_status,
    enqueue_performance_run,
    node_has_capacity,
    parse_egress_allowlist,
    validate_node_options,
    worker_node_id,
    worker_node_name,
    worker_node_queue,
)
from app.services.performance_executor import (
    configured_performance_executors,
    node_supports_executor,
    run_performance_executor,
)
from app.services.performance_dataset import (
    PerformanceDatasetBindingError,
    load_dataset_rows,
    resolve_dataset_binding,
    serialize_dataset_rows,
)
from app.worker.async_runner import run_async
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

load_all_models()


async def _heartbeat_worker_node(db):
    """Register explicitly configured performance workers without touching generic workers."""
    if not settings.PERFORMANCE_NODE_ENABLED or not settings.PERFORMANCE_NODE_ID.strip():
        return None
    now = datetime.now(timezone.utc)
    executors = configured_performance_executors()
    result = await db.execute(select(PerformanceNode).where(PerformanceNode.node_id == worker_node_id()))
    node = result.scalar_one_or_none()
    if node is None:
        node = PerformanceNode(
            node_id=worker_node_id(),
            name=worker_node_name(),
            queue_name=worker_node_queue(),
            status="online",
            enabled=True,
            capabilities={"executors": executors},
            max_vus=settings.PERFORMANCE_NODE_MAX_VUS or None,
            max_concurrency=settings.PERFORMANCE_NODE_MAX_CONCURRENCY or None,
            egress_allowlist=parse_egress_allowlist(settings.PERFORMANCE_NODE_EGRESS_ALLOWLIST),
            last_heartbeat_at=now,
        )
        db.add(node)
    elif node.enabled:
        if node.status != "draining":
            node.status = "online"
        node.name = worker_node_name()
        node.queue_name = worker_node_queue()
        node.capabilities = {"executors": executors}
        node.max_vus = settings.PERFORMANCE_NODE_MAX_VUS or None
        node.max_concurrency = settings.PERFORMANCE_NODE_MAX_CONCURRENCY or None
        node.egress_allowlist = parse_egress_allowlist(settings.PERFORMANCE_NODE_EGRESS_ALLOWLIST)
        node.last_heartbeat_at = now
        node.last_error = None
    else:
        node.status = "disabled"
    await db.flush()
    return node


@celery_app.task(bind=True, name="run_performance_test")
def run_performance_test(self, run_id: int):
    from app.core.database import AsyncSessionLocal
    from app.models.performance import PerformanceMetricSample, PerformanceRun, PerformanceRunStatus, PerformanceTest
    from app.services.performance_metrics import PerformanceResourceSampler
    from app.services.performance import PerformanceRunCancelled

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

            worker_node = await _heartbeat_worker_node(db)
            assigned_node_id = getattr(run, "performance_node_id", None)
            executor = getattr(test, "executor", "k6")
            if executor not in configured_performance_executors():
                run.status = PerformanceRunStatus.failed.value
                run.error_message = f"当前 worker 未启用 {executor} 性能执行器"
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
                return
            if assigned_node_id is not None:
                if worker_node is None or worker_node.id != assigned_node_id:
                    run.status = PerformanceRunStatus.failed.value
                    run.error_message = "指定的性能压测节点与当前 worker 不匹配"
                    run.finished_at = datetime.now(timezone.utc)
                    await db.commit()
                    return
                if effective_node_status(worker_node) != "online":
                    run.status = PerformanceRunStatus.failed.value
                    run.error_message = "指定的性能压测节点当前不可用"
                    run.finished_at = datetime.now(timezone.utc)
                    await db.commit()
                    return
                if not node_supports_executor(worker_node, executor):
                    run.status = PerformanceRunStatus.failed.value
                    run.error_message = f"指定的性能压测节点不支持 {executor} 执行器"
                    run.finished_at = datetime.now(timezone.utc)
                    await db.commit()
                    return
                if not await node_has_capacity(db, worker_node, exclude_run_id=run.id):
                    run.status = PerformanceRunStatus.failed.value
                    run.error_message = "性能压测节点并发容量已满"
                    run.finished_at = datetime.now(timezone.utc)
                    await db.commit()
                    return

            control_client = create_control_client()
            try:
                if run.status in {
                    PerformanceRunStatus.cancelled.value,
                    PerformanceRunStatus.cancelling.value,
                } or is_cancel_requested(run_id, client=control_client):
                    run.status = PerformanceRunStatus.cancelled.value
                    run.error_message = "用户已停止压测"
                    run.finished_at = datetime.now(timezone.utc)
                    await db.commit()
                    return

                run.status = PerformanceRunStatus.running.value
                run.started_at = datetime.now(timezone.utc)
                await db.commit()

                metric_samples: list[dict] = []
                resource_sampler = PerformanceResourceSampler() if settings.PERFORMANCE_METRICS_ENABLED else None

                def collect_metric_sample() -> None:
                    if resource_sampler is not None:
                        metric_samples.append(resource_sampler.sample())

                try:
                    runtime_options = dict(run.options_snapshot or {})
                    encrypted_environment = runtime_options.pop(ENVIRONMENT_SNAPSHOT_KEY, None)
                    if encrypted_environment is not None:
                        if not isinstance(encrypted_environment, dict):
                            raise RuntimeError("压测环境快照格式无效")
                        environment_values = {
                            str(key): decrypt(str(value)) for key, value in encrypted_environment.items()
                        }
                        merged_env = dict(environment_values)
                        merged_env.update(runtime_options.get("env") or {})
                        if merged_env:
                            runtime_options["env"] = merged_env
                    elif getattr(run, "environment_id", None):
                        # Backward compatibility for runs created before environment values
                        # were captured at trigger time. New runs always use the encrypted snapshot.
                        from app.core.encryption import decrypt_env_vars
                        from app.models.environment import EnvVariable

                        env_result = await db.execute(
                            select(EnvVariable).where(EnvVariable.env_id == run.environment_id)
                        )
                        environment_values = decrypt_env_vars(env_result.scalars().all())
                        merged_env = dict(environment_values)
                        merged_env.update(runtime_options.get("env") or {})
                        if merged_env:
                            runtime_options["env"] = merged_env

                    if getattr(run, "dataset_id", None) is not None:
                        dataset_rows = await load_dataset_rows(
                            db,
                            run.dataset_id,
                            getattr(run, "dataset_version", None),
                        )
                        dataset_env = dict(runtime_options.get("env") or {})
                        dataset_env["ATP_DATASET_JSON"] = serialize_dataset_rows(dataset_rows)
                        runtime_options["env"] = dataset_env

                    if worker_node is not None:
                        try:
                            validate_node_options(runtime_options, worker_node, executor=executor)
                        except PerformanceNodeConstraintError as exc:
                            raise RuntimeError(str(exc)) from exc

                    summary, raw_object_name, duration_ms = run_performance_executor(
                        executor=executor,
                        run_id=run.id,
                        script_object_name=test.script_object_name,
                        options=runtime_options,
                        cancel_check=lambda: is_cancel_requested(run_id, client=control_client),
                        metric_callback=collect_metric_sample if resource_sampler is not None else None,
                        metric_interval_seconds=settings.PERFORMANCE_METRICS_INTERVAL_SECONDS,
                        max_metric_samples=settings.PERFORMANCE_METRICS_MAX_SAMPLES,
                    )
                    run.summary = summary
                    run.raw_result_object_name = raw_object_name
                    run.duration_ms = duration_ms
                    run.status = (
                        PerformanceRunStatus.success.value
                        if summary.get("exit_code") == 0
                        else PerformanceRunStatus.failed.value
                    )
                    run.error_message = (
                        summary.get("k6_error") or summary.get("locust_error") or summary.get("grpc_error")
                    )
                except PerformanceRunCancelled:
                    run.status = PerformanceRunStatus.cancelled.value
                    run.error_message = "用户已停止压测"
                except Exception as exc:
                    logger.exception("Performance run %s failed", run_id)
                    run.status = PerformanceRunStatus.failed.value
                    run.error_message = str(exc)[:1000]
                finally:
                    for sample in metric_samples:
                        db.add(
                            PerformanceMetricSample(
                                run_id=run.id,
                                captured_at=sample["captured_at"],
                                node_id=sample["node_id"],
                                source=sample["source"],
                                metrics=sample["metrics"],
                                errors=sample["errors"],
                            )
                        )
                    run.finished_at = datetime.now(timezone.utc)
                    await db.commit()
            finally:
                clear_cancel_request(run_id, client=control_client)
                control_client.close()

    run_async(_execute())


@celery_app.task(bind=True, name="heartbeat_performance_node")
def heartbeat_performance_node(self):
    """Refresh this worker's node heartbeat and schedule the next refresh locally."""
    from app.core.database import AsyncSessionLocal

    async def _heartbeat():
        async with AsyncSessionLocal() as db:
            await _heartbeat_worker_node(db)
            await db.commit()

    try:
        run_async(_heartbeat())
    except Exception:
        # A transient database outage must not permanently stop this worker's heartbeat chain.
        logger.exception("Performance node heartbeat failed")
    finally:
        if settings.PERFORMANCE_NODE_ENABLED and settings.PERFORMANCE_NODE_ID.strip():
            interval = max(5, settings.PERFORMANCE_NODE_HEARTBEAT_TIMEOUT_SECONDS // 3)
            self.apply_async(countdown=interval, queue=worker_node_queue())


@celery_app.task(name="check_performance_schedules")
def check_performance_schedules():
    """每分钟触发到期的压测计划，并防止同一压测重复并发执行。"""
    from app.core.database import AsyncSessionLocal
    from app.core.encryption import decrypt_env_vars
    from app.models.environment import EnvVariable
    from app.models.performance import PerformanceRun, PerformanceRunStatus, PerformanceTest
    from app.api.v1.performance import _validate_performance_options
    from app.services.performance_runtime import build_options_snapshot
    from app.services.performance_schedule import next_schedule_time

    async def _check():
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(PerformanceTest)
                .where(
                    PerformanceTest.schedule_enabled.is_(True),
                    PerformanceTest.cron_expression.isnot(None),
                    PerformanceTest.next_run_at.isnot(None),
                    PerformanceTest.next_run_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
            tests = result.scalars().all()

            for test in tests:
                if not test.cron_expression:
                    continue
                active_result = await db.execute(
                    select(PerformanceRun.id)
                    .where(
                        PerformanceRun.performance_test_id == test.id,
                        PerformanceRun.status.in_(
                            [
                                PerformanceRunStatus.pending.value,
                                PerformanceRunStatus.running.value,
                                PerformanceRunStatus.cancelling.value,
                            ]
                        ),
                    )
                    .limit(1)
                )
                if active_result.scalar_one_or_none() is not None:
                    test.next_run_at = next_schedule_time(test.cron_expression, test.schedule_timezone, now)
                    await db.commit()
                    continue

                environment_values: dict = {}
                secret_keys: set[str] = set()
                if test.schedule_environment_id is not None:
                    environment_result = await db.execute(
                        select(EnvVariable).where(EnvVariable.env_id == test.schedule_environment_id)
                    )
                    variables = environment_result.scalars().all()
                    environment_values = decrypt_env_vars(variables)
                    secret_keys = {variable.key for variable in variables if variable.is_secret}

                options_snapshot, runtime_options = build_options_snapshot(
                    test.default_options,
                    test.schedule_options,
                    environment_values,
                    secret_keys,
                )
                dataset_binding = None
                validation_options = runtime_options
                if getattr(test, "dataset_id", None) is not None:
                    try:
                        dataset_binding = await resolve_dataset_binding(db, test.dataset_id, test.project_id)
                        dataset_rows = await load_dataset_rows(db, dataset_binding[0], dataset_binding[1])
                        validation_options = dict(runtime_options)
                        validation_env = dict(runtime_options.get("env") or {})
                        validation_env["ATP_DATASET_JSON"] = serialize_dataset_rows(dataset_rows)
                        validation_options["env"] = validation_env
                    except PerformanceDatasetBindingError as exc:
                        logger.error("Scheduled performance test %s has invalid dataset: %s", test.id, exc)
                        test.next_run_at = next_schedule_time(test.cron_expression, test.schedule_timezone, now)
                        await db.commit()
                        continue
                executor = getattr(test, "executor", "k6")
                try:
                    _validate_performance_options(validation_options, executor)
                except Exception as exc:
                    logger.error("Scheduled performance test %s has invalid runtime options: %s", test.id, exc)
                    test.next_run_at = next_schedule_time(test.cron_expression, test.schedule_timezone, now)
                    await db.commit()
                    continue
                node = None
                if test.schedule_node_id is not None:
                    node = await db.get(PerformanceNode, test.schedule_node_id)
                    if node is None or effective_node_status(node) != "online":
                        logger.warning("Scheduled performance test %s has no available node", test.id)
                        test.next_run_at = next_schedule_time(test.cron_expression, test.schedule_timezone, now)
                        await db.commit()
                        continue
                    if not node_supports_executor(node, executor):
                        logger.warning("Scheduled performance test %s node does not support %s", test.id, executor)
                        test.next_run_at = next_schedule_time(test.cron_expression, test.schedule_timezone, now)
                        await db.commit()
                        continue
                    try:
                        validate_node_options(validation_options, node, executor=test.executor)
                    except PerformanceNodeConstraintError as exc:
                        logger.error("Scheduled performance test %s violates node constraints: %s", test.id, exc)
                        test.next_run_at = next_schedule_time(test.cron_expression, test.schedule_timezone, now)
                        await db.commit()
                        continue
                    if not await node_has_capacity(db, node):
                        logger.warning("Scheduled performance test %s has a full node", test.id)
                        test.next_run_at = next_schedule_time(test.cron_expression, test.schedule_timezone, now)
                        await db.commit()
                        continue
                run = PerformanceRun(
                    performance_test_id=test.id,
                    project_id=test.project_id,
                    environment_id=test.schedule_environment_id,
                    performance_node_id=node.id if node else None,
                    dataset_id=dataset_binding[0] if dataset_binding else None,
                    dataset_version=dataset_binding[1] if dataset_binding else None,
                    status=PerformanceRunStatus.pending.value,
                    triggered_by=None,
                    options_snapshot=options_snapshot,
                    summary={},
                )
                db.add(run)
                test.last_scheduled_run_at = now
                test.next_run_at = next_schedule_time(test.cron_expression, test.schedule_timezone, now)
                await db.commit()
                await db.refresh(run)
                enqueue_performance_run(run_performance_test, run.id, node.queue_name if node else None)
                logger.info("Scheduled performance test %s -> run %s", test.id, run.id)

    run_async(_check())
