"""Execution queue routing shared by API entry points.

Android execution must happen in the Worker that has access to the local
Windows ADB daemon. Keeping the mapping here prevents one entry point from
silently falling back to the default Linux worker queue.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select

from app.models.case import CaseType, TestCase
from app.models.plan import TestPlan
from app.models.suite import TestSuite

DEFAULT_EXECUTION_QUEUE = "default"
ANDROID_EXECUTION_QUEUE = "android"
IOS_EXECUTION_QUEUE = "ios"


def execution_queue_for_case_type(case_type: CaseType | str | None) -> str:
    """Return the Celery queue required by a case type."""

    value = case_type.value if isinstance(case_type, CaseType) else str(case_type or "")
    if value == CaseType.android.value:
        return ANDROID_EXECUTION_QUEUE
    if value == CaseType.ios.value:
        return IOS_EXECUTION_QUEUE
    return DEFAULT_EXECUTION_QUEUE


def enqueue_case_run(task: Any, run_id: int, extra_vars: dict, trace_id: str | None, case_type: Any) -> str:
    """Enqueue a case run and return the selected queue.

    ``delay`` remains the default path for web/API cases so existing callers
    and test doubles keep their backwards-compatible contract. Device-bound
    cases use an explicit queue because Celery's task route cannot inspect the
    case row after the task has already been published.
    """

    queue = execution_queue_for_case_type(case_type)
    enqueue_task(task, (run_id, extra_vars, trace_id), queue)
    return queue


def enqueue_task(task: Any, args: tuple[Any, ...], queue: str) -> None:
    """Publish a task using the default compatibility path or an explicit queue."""

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
