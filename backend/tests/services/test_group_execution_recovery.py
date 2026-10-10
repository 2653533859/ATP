"""N1 transaction regressions. SQLite is real; broker transport is simulated.

These tests establish persistence/identity invariants, not live dual-mode acceptance.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.local_schema import _create_job_queue
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.execution_dispatch import ExecutionDispatch
from app.models.execution_run_lease import ExecutionRunLease
from app.models.group_run_child import GroupRunChild
from app.models.plan import PlanRun, TestPlan
from app.models.suite import SuiteRun, SuiteRunStatus, TestSuite
from app.services import execution_dispatch as dispatch
from app.services import group_execution as groups
from app.services import local_jobs
from app.services.execution_run_leases import reconcile_expired_execution_run_leases
from app.services.suite_delivery import SuiteDeliveryRejected, accept_suite_delivery


@pytest.fixture
def store(tmp_path, monkeypatch):
    load_all_models()
    path = tmp_path / "acceptance.sqlite3"
    engine = create_engine(f"sqlite:///{path}")
    tables = [TestSuite, SuiteRun, TestPlan, PlanRun, ExecutionDispatch, ExecutionRunLease, GroupRunChild]
    Base.metadata.create_all(engine, tables=[model.__table__ for model in tables])
    with engine.begin() as connection:
        _create_job_queue(connection)
        connection.exec_driver_sql("ALTER TABLE local_jobs ADD COLUMN dispatch_id TEXT")
        connection.exec_driver_sql("ALTER TABLE local_jobs ADD COLUMN run_identity TEXT")
    sessions = sessionmaker(engine, expire_on_commit=False)
    import app.core.database as database

    monkeypatch.setattr(database, "sync_session_factory", sessions, raising=False)
    monkeypatch.setattr(dispatch, "_session", sessions)
    monkeypatch.setattr(local_jobs, "_engine", lambda: engine)
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", True)
    with sessions.begin() as db:
        suite = TestSuite(name="Isolated", project_id=1, creator_id=1)
        plan = TestPlan(name="Isolated", project_id=1, creator_id=1)
        db.add_all([suite, plan])
        db.flush()
        run = SuiteRun(suite_id=suite.id, triggered_by=1, trace_id="n16-fixture")
        plan_run = PlanRun(plan_id=plan.id, triggered_by=1)
        db.add_all([run, plan_run])
        db.flush()
        dispatch.record_suite_dispatch(db, run=run, project_id=1, extra_vars={}, queue="default")
    yield SimpleNamespace(engine=engine, sessions=sessions, path=path, run=run, plan_run=plan_run)
    engine.dispose()


def intent(store):
    with store.sessions() as db:
        return db.scalar(select(ExecutionDispatch))


def delivery(store):
    row = intent(store)
    return SimpleNamespace(
        request=SimpleNamespace(
            id=row.id,
            headers={
                "atp_dispatch_id": row.id,
                "atp_run_identity": row.run_identity,
            },
        )
    )


def test_commit_before_wakeup_survives_restart_and_enqueues_once(store):
    # No wakeup occurred after committing the intent; polling must discover it.
    assert dispatch.process_next_dispatch()
    assert not dispatch.process_next_dispatch()
    with store.engine.connect() as db:
        assert db.execute(text("SELECT COUNT(*) FROM local_jobs")).scalar_one() == 1
    assert intent(store).status == "submitted"
    assert intent(store).attempt_count == 1


def test_simultaneous_duplicates_accept_one_and_only_one(store):
    dispatch.process_next_dispatch()

    def accept(_):
        try:
            accept_suite_delivery(delivery(store), store.run.id, {}, "n16-fixture")
            return True
        except SuiteDeliveryRejected:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(accept, range(8))) == 1


def test_local_queue_failure_rolls_back_the_claim_and_allows_safe_scan(store, monkeypatch):
    original = dispatch._insert_local_job

    def crash(db, row):
        original(db, row)
        raise RuntimeError("injected exit before commit")

    with monkeypatch.context() as scope:
        scope.setattr(dispatch, "_insert_local_job", crash)
        with pytest.raises(RuntimeError):
            dispatch.process_next_dispatch()
    assert intent(store).status == "pending"
    with store.engine.connect() as db:
        assert db.execute(text("SELECT COUNT(*) FROM local_jobs")).scalar_one() == 0
    assert dispatch.process_next_dispatch()
    assert intent(store).attempt_count == 1


def test_expired_publication_remains_uncertain_without_retry(store):
    with store.sessions.begin() as db:
        db.execute(
            update(ExecutionDispatch).values(
                status="publishing", claimed_at=datetime.now(timezone.utc) - timedelta(minutes=6)
            )
        )
    dispatch.reconcile_expired_publications()
    assert intent(store).status == "uncertain"
    assert not dispatch.process_next_dispatch()


@pytest.mark.parametrize("matching", [False, True])
def test_child_suite_lease_is_bound_to_its_resource_identity(store, matching):
    now = datetime.now(timezone.utc)
    with store.sessions.begin() as db:
        db.execute(update(PlanRun).values(status="passed"))
        db.execute(update(SuiteRun).values(status="passed"))
        db.add(
            GroupRunChild(
                parent_kind="plan",
                parent_run_id=store.plan_run.id,
                parent_identity=store.plan_run.identity_token,
                child_kind="suite",
                child_id=store.run.id,
                child_identity=store.run.identity_token,
            )
        )
        db.add(
            ExecutionRunLease(
                task_type="suite",
                run_id=store.run.id,
                run_identity=store.run.identity_token if matching else "old-resource",
                lease_token="a" * 32,
                worker_id="old-worker",
                status="expired",
                acquired_at=now,
                heartbeat_at=now,
                expires_at=now,
            )
        )

    async def read():
        engine = create_async_engine(f"sqlite+aiosqlite:///{store.path}")
        try:
            async with async_sessionmaker(engine)() as db:
                run = await db.get(PlanRun, store.plan_run.id)
                state = await groups.execution_state(db, "plan", run)
                assert state.reason == ("child_execution_uncertain" if matching else "terminal")
                assert state.requires_reconciliation is matching
                assert state.children[0].verified
                assert state.children[0].execution_uncertain is matching
        finally:
            await engine.dispose()

    asyncio.run(read())


def test_terminal_plan_with_hidden_child_requires_reconciliation(store):
    with store.sessions.begin() as db:
        db.execute(update(PlanRun).values(status="passed"))
        db.execute(update(SuiteRun).values(status="passed"))
        children = [store.run]
        for index in range(200):
            child = SuiteRun(
                suite_id=store.run.suite_id,
                triggered_by=1,
                status=SuiteRunStatus.running if index == 199 else SuiteRunStatus.passed,
            )
            db.add(child)
            children.append(child)
        db.flush()
        db.add_all(
            GroupRunChild(
                parent_kind="plan",
                parent_run_id=store.plan_run.id,
                parent_identity=store.plan_run.identity_token,
                child_kind="suite",
                child_id=child.id,
                child_identity=child.identity_token,
            )
            for child in children
        )

    async def read():
        engine = create_async_engine(f"sqlite+aiosqlite:///{store.path}")
        try:
            async with async_sessionmaker(engine)() as db:
                run = await db.get(PlanRun, store.plan_run.id)
                state = await groups.execution_state(db, "plan", run)
                assert state.child_count == 201
                assert len(state.children) == 200
                assert state.children_truncated
                assert state.reason == "children_truncated"
                assert state.requires_reconciliation
                assert state.has_more
                assert state.next_cursor is not None
                assert state.active_children_count == 0

                next_page = await groups.execution_state(db, "plan", run, limit=50, cursor=state.next_cursor)
                assert len(next_page.children) == 1
                assert next_page.children[0].status == "running"
                assert next_page.active_children_count == 1
                assert not next_page.has_more
        finally:
            await engine.dispose()

    asyncio.run(read())


def test_rollbacks_leave_neither_new_run_nor_intent(store):
    with store.sessions() as db:
        run = SuiteRun(suite_id=store.run.suite_id, triggered_by=1)
        db.add(run)
        db.flush()
        dispatch.record_suite_dispatch(db, run=run, project_id=1, extra_vars={}, queue="default")
        db.flush()
        db.rollback()
    with store.sessions() as db:
        assert len(db.scalars(select(SuiteRun)).all()) == 1
        assert len(db.scalars(select(ExecutionDispatch)).all()) == 1


@pytest.mark.parametrize("local", [True, False])
def test_acceptance_is_permanent_even_if_worker_dies_before_start(store, monkeypatch, local):
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", local)
    with store.sessions.begin() as db:
        db.execute(update(ExecutionDispatch).values(status="uncertain", mode="local" if local else "server"))
    task = delivery(store)
    assert accept_suite_delivery(task, store.run.id, {}, "n16-fixture") == store.run.identity_token
    with pytest.raises(SuiteDeliveryRejected, match="INTENT_NOT_ACCEPTABLE"):
        accept_suite_delivery(task, store.run.id, {}, "n16-fixture")
    assert not dispatch.process_next_dispatch()
    assert intent(store).execution_token
    with store.sessions() as db:
        assert db.get(SuiteRun, store.run.id).status == SuiteRunStatus.pending


@pytest.mark.parametrize("fault", ["identity", "payload", "task_id", "headers"])
def test_invalid_message_does_not_consume_valid_delivery(store, fault):
    dispatch.process_next_dispatch()
    task = delivery(store)
    variables = {}
    if fault == "identity":
        task.request.headers["atp_run_identity"] = "replacement"
    elif fault == "payload":
        variables = {"unexpected": True}
    elif fault == "task_id":
        task.request.id = "another-message"
    else:
        task.request.headers = {}
    with pytest.raises(SuiteDeliveryRejected):
        accept_suite_delivery(task, store.run.id, variables, "n16-fixture")
    assert intent(store).execution_token is None
    accept_suite_delivery(delivery(store), store.run.id, {}, "n16-fixture")


def test_broker_timeout_is_uncertain_and_never_republished(store, monkeypatch):
    from app.worker.celery_app import celery_app

    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", False)
    with store.sessions.begin() as db:
        db.execute(update(ExecutionDispatch).values(mode="server"))
    calls = []

    def send(*args, **kwargs):
        calls.append(kwargs)
        raise TimeoutError("transport outcome unknown")

    monkeypatch.setattr(celery_app, "send_task", send, raising=False)
    assert dispatch.process_next_dispatch()
    assert intent(store).status == "uncertain"
    assert not dispatch.process_next_dispatch()
    assert len(calls) == 1
    assert calls[0]["retry"] is False


@pytest.mark.parametrize("kind", ["suite", "plan"])
@pytest.mark.parametrize("running", [False, True])
def test_cancel_is_persistent_and_does_not_claim_running_work_stopped(store, kind, running):
    model = SuiteRun if kind == "suite" else PlanRun
    source = store.run if kind == "suite" else store.plan_run
    with store.sessions.begin() as db:
        db.execute(update(model).values(status="running" if running else "pending"))

    async def cancel_twice():
        engine = create_async_engine(f"sqlite+aiosqlite:///{store.path}")
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as db:
                run = await db.get(model, source.id)
                assert await groups.request_cancel(db, kind, run) is (not running)
                await db.commit()
                first = run.cancel_requested_at
                assert await groups.request_cancel(db, kind, run) is False
                await db.commit()
                assert run.cancel_requested_at == first
        finally:
            await engine.dispose()

    asyncio.run(cancel_twice())
    with store.sessions() as db:
        run = db.get(model, source.id)
        assert run.cancel_requested_at is not None
        assert run.status.value == ("running" if running else "error")
    if kind == "suite" and not running:
        dispatch.process_next_dispatch()
        assert intent(store).status == "skipped"


@pytest.mark.parametrize("kind", ["suite", "plan"])
@pytest.mark.parametrize("replacement,terminal", [(False, False), (True, False), (False, True)])
def test_expired_worker_preserves_replacements_and_terminal_results(store, kind, replacement, terminal):
    model = SuiteRun if kind == "suite" else PlanRun
    source = store.run if kind == "suite" else store.plan_run
    now = datetime.now(timezone.utc)
    with store.sessions.begin() as db:
        run = db.get(model, source.id)
        run.status = "passed" if terminal else "running"
        if replacement:
            run.identity_token = "b" * 32
        db.add(
            ExecutionRunLease(
                task_type=kind,
                run_id=source.id,
                run_identity=source.identity_token,
                lease_token="a" * 32,
                worker_id="lost",
                status="active",
                acquired_at=now,
                heartbeat_at=now,
                expires_at=now - timedelta(seconds=1),
            )
        )
    with store.sessions.begin() as db:
        counts = reconcile_expired_execution_run_leases(db, now=now)
    with store.sessions() as db:
        status = db.get(model, source.id).status.value
    assert status == ("passed" if terminal else "running" if replacement else "error")
    assert counts[kind] == (0 if replacement or terminal else 1)
