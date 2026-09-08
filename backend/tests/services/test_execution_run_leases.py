"""Regression tests for execution worker leases and lost-worker recovery."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.case import RunStatus as CaseRunStatus
from app.models.case import TestRun
from app.models.bootstrap import load_all_models
from app.models.execution_run_lease import ExecutionRunLease
from app.models.mobile_special import MobileSpecialRun, RunStatus as MobileRunStatus, TaskType
from app.models.performance import PerformanceRun, PerformanceRunStatus
from app.models.plan import PlanRun, PlanRunStatus
from app.models.suite import SuiteRun, SuiteRunStatus
from app.services.execution_run_leases import (
    ExecutionLeaseConflict,
    ExecutionRunLeaseGuard,
    acquire_execution_run_lease,
    heartbeat_execution_run_lease,
    reconcile_expired_execution_run_leases,
    release_execution_run_lease,
)

load_all_models()


class _LeaseSession:
    def __init__(self, lease=None, runs=None):
        self.lease = lease
        self.runs = runs or {}
        self.commits = 0
        self.rollbacks = 0

    def scalar(self, _statement):
        return self.lease

    def add(self, value):
        self.lease = value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def get(self, model, run_id):
        return self.runs.get((model, run_id))


def test_existing_lease_rejects_duplicate_delivery_and_expired_lease_requires_new_run():
    now = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    session = _LeaseSession()
    lease = acquire_execution_run_lease(
        session,
        task_type="case",
        run_id=7,
        lease_token="first",
        worker_id="worker-a",
        celery_task_id="task-a",
        ttl_seconds=90,
        now=now,
    )

    with pytest.raises(ExecutionLeaseConflict, match="worker-a"):
        acquire_execution_run_lease(
            session,
            task_type="case",
            run_id=7,
            lease_token="duplicate",
            worker_id="worker-b",
            celery_task_id="task-b",
            ttl_seconds=90,
            now=now + timedelta(seconds=30),
        )

    lease.expires_at = now - timedelta(seconds=1)
    lease.status = "released"
    with pytest.raises(ExecutionLeaseConflict, match="released lease"):
        acquire_execution_run_lease(
            session,
            task_type="case",
            run_id=7,
            lease_token="replacement",
            worker_id="worker-b",
            celery_task_id="task-b",
            ttl_seconds=90,
            now=now + timedelta(seconds=91),
        )


def test_expired_active_lease_is_recovered_instead_of_replaying_the_same_run():
    now = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    run = TestRun(id=7, case_id=1, triggered_by=1, status=CaseRunStatus.running, result_summary={})
    lease = ExecutionRunLease(
        task_type="case",
        run_id=7,
        lease_token="expired",
        worker_id="dead-worker",
        status="active",
        acquired_at=now - timedelta(minutes=3),
        heartbeat_at=now - timedelta(minutes=2),
        expires_at=now - timedelta(minutes=1),
    )
    session = _LeaseSession(lease, {(TestRun, 7): run})

    with pytest.raises(ExecutionLeaseConflict, match="create a new run"):
        acquire_execution_run_lease(
            session,
            task_type="case",
            run_id=7,
            lease_token="late-delivery",
            worker_id="worker-b",
            celery_task_id="task-b",
            ttl_seconds=90,
            now=now,
        )

    assert lease.status == "expired"
    assert run.status == CaseRunStatus.error


class _InsertRaceSession(_LeaseSession):
    def __init__(self, winner):
        super().__init__()
        self.winner = winner
        self.scalar_calls = 0

    def scalar(self, _statement):
        self.scalar_calls += 1
        return None if self.scalar_calls == 1 else self.winner

    def commit(self):
        raise IntegrityError("insert", {}, RuntimeError("duplicate"))


def test_concurrent_insert_race_is_reported_as_a_lease_conflict():
    now = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    winner = ExecutionRunLease(
        task_type="suite",
        run_id=9,
        lease_token="winner",
        worker_id="worker-a",
        status="active",
        acquired_at=now,
        heartbeat_at=now,
        expires_at=now + timedelta(seconds=90),
    )
    session = _InsertRaceSession(winner)

    with pytest.raises(ExecutionLeaseConflict, match="worker-a"):
        acquire_execution_run_lease(
            session,
            task_type="suite",
            run_id=9,
            lease_token="loser",
            worker_id="worker-b",
            celery_task_id="task-b",
            ttl_seconds=90,
            now=now,
        )

    assert session.rollbacks == 1


class _UpdateSession:
    def __init__(self, rowcount):
        self.rowcount = rowcount
        self.commits = 0

    def execute(self, _statement):
        return SimpleNamespace(rowcount=self.rowcount)

    def commit(self):
        self.commits += 1


def test_heartbeat_and_release_require_the_current_fencing_token():
    heartbeat_session = _UpdateSession(1)
    assert heartbeat_execution_run_lease(
        heartbeat_session,
        task_type="plan",
        run_id=11,
        lease_token="current",
        ttl_seconds=90,
    )
    stale_session = _UpdateSession(0)
    assert not release_execution_run_lease(
        stale_session,
        task_type="plan",
        run_id=11,
        lease_token="stale",
    )


class _RecoverySession:
    def __init__(self, leases, runs):
        self.leases = leases
        self.runs = runs

    def scalars(self, _statement):
        return self.leases

    def get(self, model, run_id):
        return self.runs[(model, run_id)]


def test_reconcile_expired_leases_recovers_all_five_execution_domains():
    now = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    task_types = ["case", "suite", "plan", "android", "performance"]
    leases = [
        ExecutionRunLease(
            task_type=task_type,
            run_id=index,
            lease_token=f"token-{index}",
            worker_id="dead-worker",
            status="active",
            acquired_at=now - timedelta(minutes=5),
            heartbeat_at=now - timedelta(minutes=3),
            expires_at=now - timedelta(minutes=2),
        )
        for index, task_type in enumerate(task_types, start=1)
    ]
    case_run = TestRun(id=1, case_id=1, triggered_by=1, status=CaseRunStatus.running, result_summary={})
    suite_run = SuiteRun(id=2, suite_id=1, triggered_by=1, status=SuiteRunStatus.running, result_summary={})
    plan_run = PlanRun(id=3, plan_id=1, status=PlanRunStatus.running, result_summary={})
    mobile_run = MobileSpecialRun(
        id=4,
        task_id=1,
        task_type=TaskType.performance,
        status=MobileRunStatus.running,
        summary_json={},
        config_snapshot={},
    )
    performance_run = PerformanceRun(
        id=5,
        performance_test_id=1,
        project_id=1,
        status=PerformanceRunStatus.running.value,
        options_snapshot={},
        summary={},
    )
    session = _RecoverySession(
        leases,
        {
            (TestRun, 1): case_run,
            (SuiteRun, 2): suite_run,
            (PlanRun, 3): plan_run,
            (MobileSpecialRun, 4): mobile_run,
            (PerformanceRun, 5): performance_run,
        },
    )

    counts = reconcile_expired_execution_run_leases(session, now=now)

    assert counts == {
        "android": 1,
        "case": 1,
        "performance": 1,
        "plan": 1,
        "suite": 1,
        "leases": 5,
        "runs": 5,
    }
    assert case_run.status == CaseRunStatus.error
    assert suite_run.status == SuiteRunStatus.error
    assert plan_run.status == PlanRunStatus.error
    assert mobile_run.status == MobileRunStatus.failed
    assert performance_run.status == PerformanceRunStatus.failed.value
    assert all(lease.status == "expired" for lease in leases)


def test_guard_caps_heartbeat_interval_below_the_expiry_window(monkeypatch):
    monkeypatch.setattr("app.services.execution_run_leases.settings.EXECUTION_RUN_LEASE_TTL_SECONDS", 30)
    monkeypatch.setattr("app.services.execution_run_leases.settings.EXECUTION_RUN_LEASE_HEARTBEAT_SECONDS", 1200)

    assert ExecutionRunLeaseGuard("case", 1).heartbeat_interval == 10


def test_guard_fences_a_late_worker_when_its_lease_was_already_recovered(monkeypatch):
    import app.core.database as database
    import app.services.execution_run_leases as lease_service

    class _GuardSession:
        def __init__(self):
            self.commits = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def commit(self):
            self.commits += 1

    session = _GuardSession()
    recovered = []
    monkeypatch.setattr(database, "sync_session_factory", lambda: session, raising=False)
    monkeypatch.setattr(lease_service, "release_execution_run_lease", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        lease_service,
        "_recover_run",
        lambda current, task_type, run_id, force=False: recovered.append((current, task_type, run_id, force)),
    )
    guard = ExecutionRunLeaseGuard("performance", 41)

    guard.__exit__(None, None, None)

    assert recovered == [(session, "performance", 41, True)]
    assert session.commits == 1
