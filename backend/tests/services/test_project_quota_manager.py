"""Unit tests for Q4.1 Project-Level Concurrency Quota and Execution Duration Hard Limit.

Tests:
1. get_or_default_project_quota returns sensible defaults
2. upsert_project_quota validates parameters and updates fields
3. evaluate_project_dispatch_quota permits runs within quota
4. evaluate_project_dispatch_quota rejects or queues on concurrency saturation
5. evaluate_project_dispatch_quota blocks when daily duration limit is reached
6. is_run_timed_out and scan_and_reap_timed_out_runs identify and terminate zombie runs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from app.models.bootstrap import load_all_models
from app.models.project_quota import ProjectQuota
from app.models.suite import SuiteRun, SuiteRunStatus, TestSuite
from app.services.project_quota_manager import (
    evaluate_project_dispatch_quota,
    get_or_default_project_quota,
    is_run_timed_out,
    scan_and_reap_timed_out_runs,
    upsert_project_quota,
)

load_all_models()


@pytest.mark.asyncio
async def test_get_or_default_project_quota():
    class _MockResult:
        def scalar_one_or_none(self):
            return None

    class _MockDB:
        async def execute(self, stmt):
            return _MockResult()

    db: Any = _MockDB()
    quota = await get_or_default_project_quota(db, project_id=99)
    assert quota.project_id == 99
    assert quota.max_concurrent_runs == 5
    assert quota.daily_duration_limit_seconds == 28800
    assert quota.max_single_run_timeout_seconds == 3600
    assert quota.over_quota_policy == "reject"
    assert quota.is_enabled is True


@pytest.mark.asyncio
async def test_upsert_project_quota_validation():
    class _MockDB:
        def __init__(self):
            self.added = []

        def add(self, obj):
            self.added.append(obj)

        async def execute(self, stmt):
            return SimpleNamespace(scalar_one_or_none=lambda: None)

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

    db: Any = _MockDB()
    with pytest.raises(ValueError, match="最大并发任务数"):
        await upsert_project_quota(db, project_id=1, max_concurrent_runs=0)

    # Invalid policy
    with pytest.raises(ValueError, match="超额策略必须为"):
        await upsert_project_quota(db, project_id=1, over_quota_policy="ignore")

    # Valid update
    quota = await upsert_project_quota(
        db,
        project_id=1,
        max_concurrent_runs=8,
        over_quota_policy="queue",
        daily_duration_limit_seconds=14400,
        max_single_run_timeout_seconds=1800,
    )
    assert quota.max_concurrent_runs == 8
    assert quota.over_quota_policy == "queue"
    assert quota.daily_duration_limit_seconds == 14400
    assert quota.max_single_run_timeout_seconds == 1800


@pytest.mark.asyncio
async def test_evaluate_project_dispatch_quota_within_limits():
    existing_quota = ProjectQuota(
        project_id=10,
        max_concurrent_runs=5,
        daily_duration_limit_seconds=3600,
        over_quota_policy="reject",
        is_enabled=True,
    )

    class _MockDB:
        async def execute(self, stmt):
            sql = str(stmt).lower()
            if "from project_quotas" in sql:
                return SimpleNamespace(scalar_one_or_none=lambda: existing_quota)
            # active runs count = 1 each (suite=1, plan=1, perf=1 -> total 3 < 5)
            if "count(" in sql:
                return SimpleNamespace(scalar=lambda: 1)
            # duration = 500 seconds (500000 ms)
            if "sum(" in sql:
                return SimpleNamespace(scalar=lambda: 500000)
            return SimpleNamespace(scalar=lambda: 0, all=lambda: [])

    db: Any = _MockDB()
    eval_res = await evaluate_project_dispatch_quota(db, project_id=10)
    assert eval_res.allowed is True
    assert eval_res.should_queue is False
    assert eval_res.current_active_runs == 3  # 1 suite + 1 plan + 1 perf
    assert eval_res.max_concurrent_runs == 5


@pytest.mark.asyncio
async def test_evaluate_project_dispatch_quota_concurrency_saturation_reject_and_queue():
    # 1. Reject policy
    quota_reject = ProjectQuota(
        project_id=10,
        max_concurrent_runs=3,
        over_quota_policy="reject",
        is_enabled=True,
    )

    class _MockDBReject:
        async def execute(self, stmt):
            sql = str(stmt).lower()
            if "from project_quotas" in sql:
                return SimpleNamespace(scalar_one_or_none=lambda: quota_reject)
            if "count(" in sql:
                return SimpleNamespace(scalar=lambda: 3)
            return SimpleNamespace(scalar=lambda: 0, all=lambda: [])

    db_reject: Any = _MockDBReject()
    eval_reject = await evaluate_project_dispatch_quota(db_reject, project_id=10)
    assert eval_reject.allowed is False
    assert eval_reject.should_queue is False
    assert eval_reject.reason == "concurrency_quota_exceeded"

    # 2. Queue policy
    quota_queue = ProjectQuota(
        project_id=10,
        max_concurrent_runs=3,
        over_quota_policy="queue",
        is_enabled=True,
    )

    class _MockDBQueue:
        async def execute(self, stmt):
            sql = str(stmt).lower()
            if "from project_quotas" in sql:
                return SimpleNamespace(scalar_one_or_none=lambda: quota_queue)
            if "count(" in sql:
                return SimpleNamespace(scalar=lambda: 3)
            return SimpleNamespace(scalar=lambda: 0, all=lambda: [])

    db_queue: Any = _MockDBQueue()
    eval_queue = await evaluate_project_dispatch_quota(db_queue, project_id=10)
    assert eval_queue.allowed is True
    assert eval_queue.should_queue is True
    assert eval_queue.reason == "concurrency_quota_queued"


@pytest.mark.asyncio
async def test_evaluate_project_dispatch_quota_daily_duration_exceeded():
    quota = ProjectQuota(
        project_id=10,
        max_concurrent_runs=10,
        daily_duration_limit_seconds=1800,  # 30 minutes
        is_enabled=True,
    )

    class _MockDB:
        async def execute(self, stmt):
            sql = str(stmt).lower()
            if "from project_quotas" in sql:
                return SimpleNamespace(scalar_one_or_none=lambda: quota)
            if "count(" in sql:
                return SimpleNamespace(scalar=lambda: 1)
            # Duration ms = 2,000,000 ms = 2000s > 1800s
            if "sum(" in sql:
                return SimpleNamespace(scalar=lambda: 2000000)
            return SimpleNamespace(scalar=lambda: 0, all=lambda: [])

    db_dur: Any = _MockDB()
    eval_res = await evaluate_project_dispatch_quota(db_dur, project_id=10)
    assert eval_res.allowed is False
    assert eval_res.should_queue is False
    assert eval_res.reason == "daily_duration_limit_exceeded"
    assert "今日执行时长已达上限" in eval_res.details.get("message", "")


def test_is_run_timed_out():
    now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Started 30 mins ago, timeout is 60 mins -> False
    started_recent = now - timedelta(minutes=30)
    assert is_run_timed_out(started_recent, max_timeout_seconds=3600, now=now) is False

    # 2. Started 90 mins ago, timeout is 60 mins -> True
    started_old = now - timedelta(minutes=90)
    assert is_run_timed_out(started_old, max_timeout_seconds=3600, now=now) is True

    # 3. None start time -> False
    assert is_run_timed_out(None, max_timeout_seconds=3600, now=now) is False


@pytest.mark.asyncio
async def test_scan_and_reap_timed_out_runs():
    now = datetime(2026, 10, 16, 15, 0, 0, tzinfo=timezone.utc)
    quota = ProjectQuota(project_id=42, max_single_run_timeout_seconds=1800, is_enabled=True)

    _ = TestSuite(id=1, project_id=42, name="Suite A")
    # Zombie run started 2 hours ago
    zombie_run = SuiteRun(
        id=101,
        suite_id=1,
        status=SuiteRunStatus.running,
        created_at=now - timedelta(hours=2),
    )

    class _MockDB:
        def __init__(self):
            self.committed = False

        async def execute(self, stmt):
            sql = str(stmt).lower()
            if "from suite_runs" in sql:
                return SimpleNamespace(all=lambda: [(zombie_run, 42)])
            if "from project_quotas" in sql:
                return SimpleNamespace(scalar_one_or_none=lambda: quota)
            return SimpleNamespace(all=lambda: [])

        async def commit(self):
            self.committed = True

    db: Any = _MockDB()
    reaped = await scan_and_reap_timed_out_runs(db, project_id=42, now=now)
    assert len(reaped) == 1
    assert reaped[0]["run_id"] == 101
    assert reaped[0]["reason"] == "execution_hard_timeout_exceeded"
    assert zombie_run.status == SuiteRunStatus.error
    assert "执行硬超时" in str(zombie_run.error_message)
    assert db.committed is True
