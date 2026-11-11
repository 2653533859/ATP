"""Tests for Android Agent persistent coordinator, lifecycle state machine, lease watchdog and crash recovery."""

from pathlib import Path
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.android_agent import AndroidAgentCommand, AndroidAgentEvent, AndroidAgentSession
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceLease, DeviceStatus
from app.models.project import Project
from app.models.user import User
from app.schemas.android_agent import (
    AgentBudgetConfig,
    AgentControlAction,
    AgentManualActionRequest,
    AgentSessionCreate,
    AgentSessionStatus,
)
from app.services.android_agent.coordinator import (
    AgentCoordinator,
    DeviceLeaseUnavailableError,
    InvalidStateTransitionError,
    SessionNotFoundError,
    UnauthorizedControllerError,
)
from app.services.device_leases import acquire_device_lease

load_all_models()


async def _setup_test_db(tmp_path: Path):
    db_path = tmp_path / "coordinator_test.sqlite"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}", connect_args={"timeout": 5})

    @event.listens_for(engine.sync_engine, "connect")
    def _configure(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    tables = [
        Base.metadata.tables["users"],
        Base.metadata.tables["ai_llm_configs"],
        Base.metadata.tables["projects"],
        Device.__table__,
        DeviceLease.__table__,
        AndroidAgentSession.__table__,
        AndroidAgentEvent.__table__,
        AndroidAgentCommand.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(username="test_admin", email="admin@example.com", hashed_password="pw", role="admin")
        db.add(user)
        await db.commit()
        project = Project(name="Test Project", description="Desc", owner_id=user.id)
        db.add(project)
        device = Device(id=1, serial="test-serial-001", status=DeviceStatus.online)
        device_busy = Device(id=2, serial="test-serial-002", status=DeviceStatus.busy)
        db.add(device)
        db.add(device_busy)
        await db.commit()

    return engine, factory


@pytest.mark.asyncio
async def test_create_session(tmp_path: Path):
    engine, factory = await _setup_test_db(tmp_path)
    try:
        coord = AgentCoordinator()
        payload = AgentSessionCreate(
            device_id=1,
            package_name="com.shop",
            goal="Search and buy",
            expected_outcome="Order confirmed",
            context_values={"item": "hat"},
            budget=AgentBudgetConfig(max_steps=20, max_calls=25),
        )
        async with factory() as db:
            session = await coord.create_session(db, project_id=1, payload=payload)
            await db.commit()

            assert session.id is not None
            assert session.status == AgentSessionStatus.created.value
            assert session.controller == "agent"
            assert session.version == 1
            assert session.budget_max_steps == 20
            assert session.budget_max_calls == 25

            events = await coord.list_events(db, session.id)
            assert len(events) == 1
            assert events[0].seq == 1
            assert events[0].event_type == "session_created"
            assert events[0].payload["goal"] == "Search and buy"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_start_session_lifecycle_and_lease(tmp_path: Path):
    engine, factory = await _setup_test_db(tmp_path)
    try:
        coord = AgentCoordinator()
        payload = AgentSessionCreate(
            device_id=1,
            package_name="com.shop",
            goal="Search and buy",
            expected_outcome="Order confirmed",
        )
        async with factory() as db:
            session = await coord.create_session(db, project_id=1, payload=payload)
            await db.commit()

            started = await coord.start_session(db, session.id)
            await db.commit()

            assert started.status == AgentSessionStatus.running.value
            assert started.lease_token is not None
            assert started.started_at is not None

            events = await coord.list_events(db, session.id)
            types = [e.event_type for e in events]
            assert types == ["session_created", "session_prechecking", "session_running"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_start_session_device_conflict(tmp_path: Path):
    engine, factory = await _setup_test_db(tmp_path)
    try:
        coord = AgentCoordinator()
        async with factory() as db:
            # 占用设备 1
            await acquire_device_lease(db, 1, owner_id=None, owner_label="other-task")
            await db.commit()

            payload = AgentSessionCreate(
                device_id=1,
                package_name="com.shop",
                goal="Search and buy",
                expected_outcome="Order confirmed",
            )
            session = await coord.create_session(db, project_id=1, payload=payload)
            await db.commit()

            with pytest.raises(DeviceLeaseUnavailableError):
                await coord.start_session(db, session.id)

            reloaded = await coord.get_session(db, session.id)
            assert reloaded.status == AgentSessionStatus.failed.value
            assert reloaded.error_code == "device_busy"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_control_pause_and_resume(tmp_path: Path):
    engine, factory = await _setup_test_db(tmp_path)
    try:
        coord = AgentCoordinator()
        payload = AgentSessionCreate(
            device_id=1,
            package_name="com.shop",
            goal="Search and buy",
            expected_outcome="Order confirmed",
        )
        async with factory() as db:
            session = await coord.create_session(db, project_id=1, payload=payload)
            await coord.start_session(db, session.id)
            await db.commit()

            paused = await coord.control_session(db, session.id, AgentControlAction.pause, reason="Inspect screen")
            await db.commit()
            assert paused.status == AgentSessionStatus.paused.value
            assert paused.control_epoch == 1

            resumed = await coord.control_session(db, session.id, AgentControlAction.resume, reason="Back to work")
            await db.commit()
            assert resumed.status == AgentSessionStatus.running.value
            assert resumed.controller == "agent"
            assert resumed.control_epoch == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_control_takeover_and_manual_action(tmp_path: Path):
    engine, factory = await _setup_test_db(tmp_path)
    try:
        coord = AgentCoordinator()
        payload = AgentSessionCreate(
            device_id=1,
            package_name="com.shop",
            goal="Search and buy",
            expected_outcome="Order confirmed",
        )
        async with factory() as db:
            session = await coord.create_session(db, project_id=1, payload=payload)
            await coord.start_session(db, session.id)
            await db.commit()

            # 人工接管
            takeover = await coord.control_session(db, session.id, AgentControlAction.takeover, reason="Manual login")
            await db.commit()
            assert takeover.status == AgentSessionStatus.paused.value
            assert takeover.controller == "manual"

            # 执行人工指令
            manual_req = AgentManualActionRequest(
                action="tap",
                params={"x": 500, "y": 800},
                idempotency_key="key-001",
            )
            cmd = await coord.manual_action(db, session.id, manual_req)
            await db.commit()
            assert cmd.action == "tap"
            # 人工动作只登记为 prepared，真正落设备要过 dispatch_prepared_command 的控制器门禁
            assert cmd.status == "prepared"

            executed = await coord.dispatch_prepared_command(
                db, session.id, cmd.id, execute=lambda _db, _session, _cmd: None
            )
            await db.commit()
            assert executed.status == "succeeded"

            # 幂等性测试
            cmd2 = await coord.manual_action(db, session.id, manual_req)
            assert cmd2.id == cmd.id

            # 恢复给 Agent
            resumed = await coord.control_session(db, session.id, AgentControlAction.resume)
            await db.commit()
            assert resumed.controller == "agent"
            assert resumed.status == AgentSessionStatus.running.value

            # 非人工接管状态下拒绝 manual_action
            with pytest.raises(UnauthorizedControllerError):
                await coord.manual_action(db, session.id, manual_req)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_control_cancel(tmp_path: Path):
    engine, factory = await _setup_test_db(tmp_path)
    try:
        coord = AgentCoordinator()
        payload = AgentSessionCreate(
            device_id=1,
            package_name="com.shop",
            goal="Search and buy",
            expected_outcome="Order confirmed",
        )
        async with factory() as db:
            session = await coord.create_session(db, project_id=1, payload=payload)
            await coord.start_session(db, session.id)
            await db.commit()

            assert session.lease_token is not None

            cancelled = await coord.control_session(db, session.id, AgentControlAction.cancel, reason="User cancelled")
            await db.commit()
            assert cancelled.status == AgentSessionStatus.cancelled.value
            assert cancelled.lease_token is None
            assert cancelled.finished_at is not None

            cancelled2 = await coord.control_session(db, session.id, AgentControlAction.cancel)
            assert cancelled2.status == AgentSessionStatus.cancelled.value
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_record_step_progress_and_budget_exhaustion(tmp_path: Path):
    engine, factory = await _setup_test_db(tmp_path)
    try:
        coord = AgentCoordinator()
        payload = AgentSessionCreate(
            device_id=1,
            package_name="com.shop",
            goal="Search and buy",
            expected_outcome="Order confirmed",
            budget=AgentBudgetConfig(max_steps=2, max_calls=3),
        )
        async with factory() as db:
            session = await coord.create_session(db, project_id=1, payload=payload)
            await coord.start_session(db, session.id)
            await db.commit()

            # Step 1
            await coord.record_step_progress(db, session.id, model_calls=1, tokens=500, actions=1)
            reloaded = await coord.get_session(db, session.id)
            assert reloaded.steps_count == 1
            assert reloaded.model_calls_count == 1
            assert reloaded.total_tokens == 500
            assert reloaded.status == AgentSessionStatus.running.value

            # Step 2: 达到预算上限
            await coord.record_step_progress(db, session.id, model_calls=1, tokens=600, actions=1)
            reloaded = await coord.get_session(db, session.id)
            assert reloaded.steps_count == 2
            assert reloaded.status == AgentSessionStatus.failed.value
            assert reloaded.error_code == "budget_exceeded"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recover_orphaned_sessions(tmp_path: Path):
    engine, factory = await _setup_test_db(tmp_path)
    try:
        coord = AgentCoordinator()
        async with factory() as db:
            # 1. 正常的 running 会话
            payload1 = AgentSessionCreate(device_id=1, package_name="com.shop", goal="g1", expected_outcome="o1")
            s1 = await coord.create_session(db, project_id=1, payload=payload1)
            await coord.start_session(db, s1.id)

            # 2. 租约丢失的孤儿会话
            s2 = AndroidAgentSession(
                project_id=1,
                device_id=1,
                title="Orphaned",
                goal="g2",
                expected_outcome="o2",
                package_name="com.shop",
                status=AgentSessionStatus.running.value,
                lease_token="invalid_or_expired_token",
            )
            db.add(s2)
            await db.flush()

            # 执行孤儿扫描
            recovered = await coord.recover_orphaned_sessions(db, inactive_threshold_seconds=180)
            await db.commit()

            assert s2.id in recovered
            reloaded_s2 = await coord.get_session(db, s2.id)
            assert reloaded_s2.status == AgentSessionStatus.failed.value
            # 错误码对齐实施清单的 system_restarted_needs_review
            assert reloaded_s2.error_code == "system_restarted_needs_review"

            reloaded_s1 = await coord.get_session(db, s1.id)
            assert reloaded_s1.status == AgentSessionStatus.running.value
            assert s1.id not in recovered
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_session_not_found_and_invalid_transition(tmp_path: Path):
    engine, factory = await _setup_test_db(tmp_path)
    try:
        coord = AgentCoordinator()
        async with factory() as db:
            with pytest.raises(SessionNotFoundError):
                await coord.get_session(db, 999999)

            with pytest.raises(InvalidStateTransitionError):
                coord.validate_transition(AgentSessionStatus.completed.value, AgentSessionStatus.running.value)
    finally:
        await engine.dispose()
