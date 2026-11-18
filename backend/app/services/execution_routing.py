"""Execution queue routing shared by API entry points.

Device cases must reach Workers with their local automation dependencies,
while Web and protocol cases may need deployment-specific queues when several
ATP releases share one broker. Keeping the mapping here prevents entry points
from silently bypassing those boundaries.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.models.case import CaseType, TestCase
from app.models.plan import TestPlan
from app.models.suite import TestSuite

DEFAULT_EXECUTION_QUEUE = "default"
ANDROID_EXECUTION_QUEUE = "android"
IOS_EXECUTION_QUEUE = "ios"
PROTOCOL_CASE_TYPES = {
    CaseType.api.value,
    CaseType.graphql.value,
    CaseType.websocket.value,
    CaseType.grpc.value,
}


def execution_queue_for_case_type(case_type: CaseType | str | None) -> str:
    """Return the Celery queue required by a case type."""

    value = case_type.value if isinstance(case_type, CaseType) else str(case_type or "")
    if value == CaseType.android.value:
        return ANDROID_EXECUTION_QUEUE
    if value == CaseType.ios.value:
        return IOS_EXECUTION_QUEUE
    if value == CaseType.web.value:
        return settings.WEB_EXECUTION_QUEUE.strip() or DEFAULT_EXECUTION_QUEUE
    if value in PROTOCOL_CASE_TYPES:
        return settings.PROTOCOL_EXECUTION_QUEUE.strip() or DEFAULT_EXECUTION_QUEUE
    return DEFAULT_EXECUTION_QUEUE


def enqueue_case_run(
    task: Any,
    run_id: int,
    extra_vars: dict,
    trace_id: str | None,
    case_type: Any,
    *,
    queue_override: str | None = None,
) -> str:
    """Enqueue a case run and return the selected queue.

    ``delay`` remains the default path when no dedicated queue is configured,
    so existing callers and test doubles keep their backwards-compatible
    contract. Explicitly routed cases cannot rely on Celery's static task route
    because it cannot inspect the case row after publication.
    """

    queue = (queue_override or "").strip() or execution_queue_for_case_type(case_type)
    enqueue_task(task, (run_id, extra_vars, trace_id), queue)
    return queue


def http_status_for_device_resolution(code: str) -> int:
    """Map DeviceResolutionError codes to HTTP status codes per frozen contract."""
    if code in {"worker_offline", "worker_registry_unavailable"}:
        return 503
    return 409


async def resolve_android_device_queue(
    db: Any,
    *,
    device_id: int | None = None,
    device_serial: str | None = None,
) -> str:
    """Resolve the target ``android.<worker_id>`` queue for a specific Android device."""
    queue, _meta = await resolve_android_device_dispatch(
        db,
        device_id=device_id,
        device_serial=device_serial,
    )
    return queue


async def resolve_android_device_dispatch(
    db: Any,
    *,
    device_id: int | None = None,
    device_serial: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Resolve ``(queue, worker_meta)`` for an Android device, converting Redis errors to 503 codes."""
    if not settings.ANDROID_MULTI_NODE_ENABLED or settings.ATP_LOCAL_MODE:
        return ANDROID_EXECUTION_QUEUE, {}

    from app.services.android_worker_registry import (
        AndroidWorkerRegistryError,
        get_android_worker,
        worker_android_queue,
    )
    from app.services.device_resolution import DeviceResolutionError, resolve_device_async

    device = await resolve_device_async(
        db,
        device_id=device_id,
        serial=device_serial,
        require_claimed=True,
    )
    worker_id = (device.worker_id or "").strip()
    try:
        worker_info = await get_android_worker(worker_id)
    except AndroidWorkerRegistryError as exc:
        raise DeviceResolutionError("worker_registry_unavailable", str(exc)) from exc
    if not worker_info:
        raise DeviceResolutionError(
            "worker_offline",
            f"设备 {device.serial} 所属节点 '{worker_id}' 当前离线，无法执行",
        )
    meta: dict[str, Any] = {
        "_expected_worker_id": worker_id,
        "device_id": int(device.id),
        "device_serial": str(device.serial),
    }
    if worker_info.get("instance_generation") is not None:
        meta["_expected_generation"] = int(worker_info["instance_generation"])
    return worker_android_queue(worker_id), meta


async def resolve_android_case_dispatch_target(
    db: Any,
    case: Any,
    extra_vars: dict[str, Any] | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """Determine ``(queue_override, dispatch_vars_patch)`` before creating an Android TestRun."""
    case_type = getattr(case, "case_type", None)
    case_type_val = str(getattr(case_type, "value", case_type or ""))
    if case_type_val != CaseType.android.value:
        return None, {}

    cfg = getattr(case, "config", None) or {}
    merged_extra = extra_vars or {}
    is_matrix_parent = bool(
        cfg.get("device_matrix")
        and not cfg.get("_device_matrix_variant")
        and not merged_extra.get("_device_matrix_variant")
        and not merged_extra.get("device_id")
        and not merged_extra.get("device_serial")
    )
    if is_matrix_parent:
        if settings.ANDROID_MULTI_NODE_ENABLED and not settings.ATP_LOCAL_MODE:
            return DEFAULT_EXECUTION_QUEUE, {}
        return None, {}

    if not settings.ANDROID_MULTI_NODE_ENABLED or settings.ATP_LOCAL_MODE:
        return None, {}

    from app.services.device_resolution import extract_target_device_spec

    target_id, target_serial = extract_target_device_spec(cfg, merged_extra)
    queue, meta = await resolve_android_device_dispatch(
        db,
        device_id=target_id,
        device_serial=target_serial,
    )
    return queue, meta


def enqueue_task(task: Any, args: tuple[Any, ...], queue: str) -> None:
    """Publish a task using the default compatibility path or an explicit queue."""
    if settings.ATP_LOCAL_MODE:
        from app.services.local_jobs import enqueue_local_job

        enqueue_local_job(task, args)
        return

    if queue == DEFAULT_EXECUTION_QUEUE:
        task.delay(*args)
    else:
        task.apply_async(args=args, queue=queue)


async def resolve_suite_execution_queue(db: Any, suite: TestSuite) -> str:
    """Route homogeneous device suites to their dedicated Worker queue.

    Mixed suites stay on the default queue; the suite executor will dispatch
    their device-bound children explicitly so web/API cases remain local to
    the orchestration Worker.
    """

    case_ids = _json_ids(getattr(suite, "case_ids", None), key="case_id")
    if not case_ids:
        return DEFAULT_EXECUTION_QUEUE
    if not callable(getattr(db, "execute", None)):
        return DEFAULT_EXECUTION_QUEUE

    result = await db.execute(select(TestCase.case_type).where(TestCase.id.in_(case_ids)))
    case_types = list(result.scalars().all())
    queues = {execution_queue_for_case_type(case_type) for case_type in case_types}
    if case_types and len(case_types) == len(case_ids) and len(queues) == 1:
        queue = queues.pop()
        if queue == ANDROID_EXECUTION_QUEUE and settings.ANDROID_MULTI_NODE_ENABLED:
            return DEFAULT_EXECUTION_QUEUE
        if queue != DEFAULT_EXECUTION_QUEUE:
            return queue
    return DEFAULT_EXECUTION_QUEUE


async def resolve_plan_execution_queue(db: Any, plan: TestPlan) -> str:
    """Use the Android queue when every suite in a plan is Android-only."""

    suite_ids = _json_ids(getattr(plan, "suite_ids", None), key="suite_id")
    if not suite_ids:
        return DEFAULT_EXECUTION_QUEUE
    if not callable(getattr(db, "execute", None)):
        return DEFAULT_EXECUTION_QUEUE

    result = await db.execute(select(TestSuite).where(TestSuite.id.in_(suite_ids)))
    suites = list(result.scalars().all())
    if len(suites) != len(suite_ids):
        return DEFAULT_EXECUTION_QUEUE

    queues = [await resolve_suite_execution_queue(db, suite) for suite in suites]
    if queues and len(set(queues)) == 1 and queues[0] != DEFAULT_EXECUTION_QUEUE:
        return queues[0]
    return DEFAULT_EXECUTION_QUEUE


def _json_ids(items: Any, *, key: str) -> list[int]:
    if not isinstance(items, Iterable) or isinstance(items, (str, bytes, dict)):
        return []

    ids: list[int] = []
    for item in items:
        raw_id = item.get(key) if isinstance(item, dict) else item
        if not isinstance(raw_id, (int, str)):
            continue
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if item_id > 0:
            ids.append(item_id)
    return ids
