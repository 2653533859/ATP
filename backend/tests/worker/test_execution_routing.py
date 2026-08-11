from __future__ import annotations

import asyncio
import types

from app.models.case import CaseType
from app.services.execution_routing import (
    ANDROID_EXECUTION_QUEUE,
    DEFAULT_EXECUTION_QUEUE,
    enqueue_case_run,
    execution_queue_for_case_type,
    resolve_suite_execution_queue,
)


class _ScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _DB:
    def __init__(self, values):
        self.values = values

    async def execute(self, _query):
        return types.SimpleNamespace(scalars=lambda: _ScalarResult(self.values))


def test_android_case_uses_dedicated_queue():
    assert execution_queue_for_case_type(CaseType.android) == ANDROID_EXECUTION_QUEUE
    assert execution_queue_for_case_type(CaseType.api) == DEFAULT_EXECUTION_QUEUE


def test_enqueue_case_run_uses_explicit_queue_for_android():
    calls = {}
    task = types.SimpleNamespace(
        delay=lambda *_args, **_kwargs: calls.update(kind="delay"),
        apply_async=lambda **kwargs: calls.update(kind="apply_async", **kwargs),
    )

    queue = enqueue_case_run(task, 11, {"x": "y"}, "trace-11", CaseType.android)

    assert queue == ANDROID_EXECUTION_QUEUE
    assert calls == {
        "kind": "apply_async",
        "args": (11, {"x": "y"}, "trace-11"),
        "queue": ANDROID_EXECUTION_QUEUE,
    }


def test_android_only_suite_uses_android_queue():
    suite = types.SimpleNamespace(case_ids=[{"case_id": 1}, {"case_id": 2}])
    queue = asyncio.run(resolve_suite_execution_queue(_DB([CaseType.android, CaseType.android]), suite))
    assert queue == ANDROID_EXECUTION_QUEUE


def test_mixed_suite_stays_on_default_queue():
    suite = types.SimpleNamespace(case_ids=[{"case_id": 1}, {"case_id": 2}])
    queue = asyncio.run(resolve_suite_execution_queue(_DB([CaseType.android, CaseType.api]), suite))
    assert queue == DEFAULT_EXECUTION_QUEUE


def test_ios_only_suite_uses_ios_queue():
    suite = types.SimpleNamespace(case_ids=[{"case_id": 1}, {"case_id": 2}])
    queue = asyncio.run(resolve_suite_execution_queue(_DB([CaseType.ios, CaseType.ios]), suite))
    assert queue == "ios"
