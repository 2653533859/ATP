"""Integration and route tests for Android Agent REST API."""

from pathlib import Path
import pytest
from fastapi import HTTPException, status
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.android_agent import (
    control_agent_session,
    create_agent_session,
    get_agent_session,
    get_agent_session_events,
    list_agent_sessions,
    manual_action_agent_session,
    start_agent_session,
)
from app.models.android_agent import AndroidAgentCommand, AndroidAgentEvent, AndroidAgentSession
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceLease, DeviceStatus
from app.models.project import Project
from app.models.user import User
from app.schemas.android_agent import (
    AgentBudgetConfig,
    AgentControlAction,
    AgentControlRequest,
    AgentManualActionRequest,
    AgentSessionCreate,
    AgentSessionStatus,
)
from app.services.device_leases import acquire_device_lease

load_all_models()


@pytest.fixture(autouse=True)
def _disable_external_event_publish(monkeypatch):
    from app.services.android_agent import coordinator

    async def no_publish(*args, **kwargs):
        pass

    monkeypatch.setattr(coordinator, "_safe_publish_agent_event", no_publish)


async def _setup_api_test_db(tmp_path: Path):
    db_path = tmp_path / "api_test.sqlite"
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
        Base.metadata.tables["audit_logs"],
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(username="admin_user", email="admin@example.com", hashed_password="pw", role="admin")
        db.add(user)
        await db.commit()
        project = Project(name="ATP Agent Project", description="Test", owner_id=user.id)
        other_project = Project(name="Other Project", description="Test", owner_id=user.id)
        db.add(project)
        db.add(other_project)
        device1 = Device(id=1, serial="api-serial-001", status=DeviceStatus.online)
        db.add(device1)
        await db.commit()

    return engine, factory, user


@pytest.mark.asyncio
async def test_api_create_and_start_session(tmp_path: Path):
    engine, factory, user = await _setup_api_test_db(tmp_path)
    try:
        async with factory() as db:
            # 1. 创建会话
            payload = AgentSessionCreate(
                device_id=1,
                package_name="com.example.app",
                goal="Search and checkout",
                expected_outcome="Payment screen",
                budget=AgentBudgetConfig(max_steps=15, max_calls=20),
            )
            created = await create_agent_session(
                payload=payload,
                project_id=1,
                db=db,
                current_user=user,
            )
            assert created.id is not None
            assert created.status == AgentSessionStatus.created.value
            assert created.budget_max_steps == 15

            # 2. 启动会话
            started = await start_agent_session(
                project_id=1,
                session_id=created.id,
                db=db,
                current_user=user,
            )
            assert started.status == AgentSessionStatus.running.value
            assert started.lease_token is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_start_session_device_conflict(tmp_path: Path):
    engine, factory, user = await _setup_api_test_db(tmp_path)
    try:
        async with factory() as db:
            payload = AgentSessionCreate(
                device_id=1,
                package_name="com.example.app",
                goal="Search and checkout",
                expected_outcome="Payment screen",
            )
            created = await create_agent_session(
                payload=payload,
                project_id=1,
                db=db,
                current_user=user,
            )

            # 提前占用设备 1
            await acquire_device_lease(db, 1, owner_id=None, owner_label="busy-lock")
            await db.commit()

            # 启动时应捕获冲突并返回 409
            with pytest.raises(HTTPException) as exc_info:
                await start_agent_session(
                    project_id=1,
                    session_id=created.id,
                    db=db,
                    current_user=user,
                )
            assert exc_info.value.status_code == status.HTTP_409_CONFLICT
            assert "Device lease unavailable" in exc_info.value.detail
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_get_session_and_project_isolation(tmp_path: Path):
    engine, factory, user = await _setup_api_test_db(tmp_path)
    try:
        async with factory() as db:
            payload = AgentSessionCreate(
                device_id=1,
                package_name="com.example.app",
                goal="Search and checkout",
                expected_outcome="Payment screen",
            )
            created = await create_agent_session(
                payload=payload,
                project_id=1,
                db=db,
                current_user=user,
            )

            # 正常查询项目 1 下的会话
            fetched = await get_agent_session(
                project_id=1,
                session_id=created.id,
                db=db,
                current_user=user,
            )
            assert fetched.id == created.id

            # 跨项目查询（项目 2 查询项目 1 的会话）必须返回 404
            with pytest.raises(HTTPException) as exc_info:
                await get_agent_session(
                    project_id=2,
                    session_id=created.id,
                    db=db,
                    current_user=user,
                )
            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_control_session_and_version_defense(tmp_path: Path, monkeypatch):
    from app.api.v1 import android_agent

    async def fake_execute(*args):
        return "succeeded", None

    monkeypatch.setattr(android_agent, "_execute_manual_action", fake_execute)
    engine, factory, user = await _setup_api_test_db(tmp_path)
    try:
        async with factory() as db:
            payload = AgentSessionCreate(
                device_id=1,
                package_name="com.example.app",
                goal="Search and checkout",
                expected_outcome="Payment screen",
            )
            created = await create_agent_session(
                payload=payload,
                project_id=1,
                db=db,
                current_user=user,
            )
            await start_agent_session(
                project_id=1,
                session_id=created.id,
                db=db,
                current_user=user,
            )

            # 乐观锁防御：传入过期的 expected_version 必须返回 409
            conflict_req = AgentControlRequest(
                action=AgentControlAction.pause,
                expected_version=999,
            )
            with pytest.raises(HTTPException) as exc_info:
                await control_agent_session(
                    payload=conflict_req,
                    project_id=1,
                    session_id=created.id,
                    db=db,
                    current_user=user,
                )
            assert exc_info.value.status_code == status.HTTP_409_CONFLICT

            # 正确暂停
            pause_req = AgentControlRequest(action=AgentControlAction.pause, reason="Inspect screen")
            resp = await control_agent_session(
                payload=pause_req,
                project_id=1,
                session_id=created.id,
                db=db,
                current_user=user,
            )
            assert resp.status == AgentSessionStatus.paused.value

            # 正确接管
            takeover_req = AgentControlRequest(action=AgentControlAction.takeover, reason="User typing password")
            resp_takeover = await control_agent_session(
                payload=takeover_req,
                project_id=1,
                session_id=created.id,
                db=db,
                current_user=user,
            )
            # 接管后控制器统一记为 manual（与 AgentController.manual 一致）
            assert resp_takeover.controller == "manual"
            assert resp_takeover.status == AgentSessionStatus.paused.value

            # 人工接管下执行单步动作
            action_req = AgentManualActionRequest(action="tap", params={"x": 300, "y": 400})
            manual_resp = await manual_action_agent_session(
                payload=action_req,
                project_id=1,
                session_id=created.id,
                db=db,
                current_user=user,
            )
            assert manual_resp["action"] == "tap"
            assert manual_resp["status"] == "succeeded"

            # 恢复会话
            resume_req = AgentControlRequest(action=AgentControlAction.resume)
            resp_resume = await control_agent_session(
                payload=resume_req,
                project_id=1,
                session_id=created.id,
                db=db,
                current_user=user,
            )
            assert resp_resume.status == AgentSessionStatus.running.value
            assert resp_resume.controller == "agent"

            # 在 running 状态下尝试 manual_action 必须返回 400
            with pytest.raises(HTTPException) as exc_manual:
                await manual_action_agent_session(
                    payload=action_req,
                    project_id=1,
                    session_id=created.id,
                    db=db,
                    current_user=user,
                )
            assert exc_manual.value.status_code == status.HTTP_400_BAD_REQUEST

            # 取消会话
            cancel_req = AgentControlRequest(action=AgentControlAction.cancel, reason="Done")
            resp_cancel = await control_agent_session(
                payload=cancel_req,
                project_id=1,
                session_id=created.id,
                db=db,
                current_user=user,
            )
            assert resp_cancel.status == AgentSessionStatus.cancelled.value
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_get_events_pagination(tmp_path: Path):
    engine, factory, user = await _setup_api_test_db(tmp_path)
    try:
        async with factory() as db:
            payload = AgentSessionCreate(
                device_id=1,
                package_name="com.example.app",
                goal="Search and checkout",
                expected_outcome="Payment screen",
            )
            created = await create_agent_session(
                payload=payload,
                project_id=1,
                db=db,
                current_user=user,
            )
            await start_agent_session(
                project_id=1,
                session_id=created.id,
                db=db,
                current_user=user,
            )

            # 获取事件流
            events_page1 = await get_agent_session_events(
                project_id=1,
                session_id=created.id,
                after_seq=0,
                limit=2,
                db=db,
                current_user=user,
            )
            assert len(events_page1.items) == 2
            assert events_page1.has_more is True

            # 拉取下一页
            events_page2 = await get_agent_session_events(
                project_id=1,
                session_id=created.id,
                after_seq=events_page1.next_seq,
                limit=2,
                db=db,
                current_user=user,
            )
            assert len(events_page2.items) == 1
            assert events_page2.has_more is False

            # 获取项目下的会话列表（按 id 降序，且跨项目隔离）
            sessions_p1 = await list_agent_sessions(project_id=1, limit=20, db=db, current_user=user)
            assert len(sessions_p1) == 1
            assert sessions_p1[0].id == created.id

            sessions_p2 = await list_agent_sessions(project_id=2, limit=20, db=db, current_user=user)
            assert sessions_p2 == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_list_agent_models_excludes_secrets_and_disabled(tmp_path: Path):
    from app.api.v1.android_agent import list_agent_models
    from app.models.ai_llm_config import AILLMConfig
    from app.models.base import Base
    from app.schemas.android_agent import AgentVisionModelOut

    engine, factory, user = await _setup_api_test_db(tmp_path)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[AILLMConfig.__table__]))

        async with factory() as db:
            db.add_all(
                [
                    AILLMConfig(
                        name="text-on",
                        provider="openai",
                        api_key_encrypted="enc-secret-1",
                        endpoint="https://private-1.invalid",
                        model_name="gpt-4o-mini",
                        enabled=True,
                        supports_vision=False,
                    ),
                    AILLMConfig(
                        name="vision-on",
                        provider="anthropic",
                        api_key_encrypted="enc-secret-2",
                        endpoint="https://private-2.invalid",
                        model_name="claude-sonnet",
                        enabled=True,
                        supports_vision=True,
                    ),
                    AILLMConfig(
                        name="vision-off",
                        provider="openai",
                        api_key_encrypted="enc-secret-3",
                        endpoint="https://private-3.invalid",
                        model_name="gpt-4o",
                        enabled=False,
                        supports_vision=True,
                    ),
                ]
            )
            await db.commit()

            rows = await list_agent_models(project_id=1, db=db, current_user=user)
            assert [row.name for row in rows] == ["vision-on", "text-on"]
            serialized = [AgentVisionModelOut.model_validate(row).model_dump() for row in rows]
            assert serialized[0]["supports_vision"] is True
            for item in serialized:
                assert "api_key_encrypted" not in item
                assert "endpoint" not in item
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_feature_flag_disabled_blocks_new_or_resume_but_allows_read_and_cancel(
    tmp_path: Path,
    monkeypatch,
):
    from fastapi import status

    from app.api.v1 import android_agent as agent_api_module
    from app.models.audit import AuditLog
    from app.models.base import Base

    engine, factory, user = await _setup_api_test_db(tmp_path)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[AuditLog.__table__]))

        async with factory() as db:
            payload = AgentSessionCreate(
                device_id=1,
                package_name="com.example.app",
                goal="Login",
                expected_outcome="Home",
            )
            running_session = await create_agent_session(
                payload=payload,
                project_id=1,
                db=db,
                current_user=user,
            )
            await start_agent_session(
                project_id=1,
                session_id=running_session.id,
                db=db,
                current_user=user,
            )
            await control_agent_session(
                payload=AgentControlRequest(action=AgentControlAction.pause, reason="wait"),
                project_id=1,
                session_id=running_session.id,
                db=db,
                current_user=user,
            )

            created_only = await create_agent_session(
                payload=payload,
                project_id=1,
                db=db,
                current_user=user,
            )

            monkeypatch.setattr(agent_api_module.settings, "ANDROID_AGENT_ENABLED", False)

            with pytest.raises(HTTPException) as exc_create:
                await create_agent_session(payload=payload, project_id=1, db=db, current_user=user)
            assert exc_create.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "android_agent_disabled" in str(exc_create.value.detail)

            with pytest.raises(HTTPException) as exc_start:
                await start_agent_session(project_id=1, session_id=created_only.id, db=db, current_user=user)
            assert exc_start.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

            with pytest.raises(HTTPException) as exc_run:
                await agent_api_module.run_agent_session_endpoint(
                    project_id=1,
                    session_id=running_session.id,
                    db=db,
                    current_user=user,
                )
            assert exc_run.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

            with pytest.raises(HTTPException) as exc_resume:
                await control_agent_session(
                    payload=AgentControlRequest(action=AgentControlAction.resume),
                    project_id=1,
                    session_id=running_session.id,
                    db=db,
                    current_user=user,
                )
            assert exc_resume.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

            # 读取与取消现有会话仍允许，确保可安全回滚收尾
            fetched = await get_agent_session(
                project_id=1,
                session_id=running_session.id,
                db=db,
                current_user=user,
            )
            assert fetched.id == running_session.id
            cancelled = await control_agent_session(
                payload=AgentControlRequest(action=AgentControlAction.cancel, reason="rollback"),
                project_id=1,
                session_id=running_session.id,
                db=db,
                current_user=user,
            )
            assert cancelled.status == AgentSessionStatus.cancelled.value
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_audit_logs_recorded_for_takeover_manual_action_and_complete(tmp_path: Path, monkeypatch):
    from sqlalchemy import select

    from app.api.v1 import android_agent

    async def fake_execute(*args):
        return "succeeded", None

    monkeypatch.setattr(android_agent, "_execute_manual_action", fake_execute)

    from app.api.v1.android_agent import complete_agent_session
    from app.models.audit import AuditLog
    from app.models.base import Base
    from app.schemas.android_agent import AgentCompleteRequest

    engine, factory, user = await _setup_api_test_db(tmp_path)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[AuditLog.__table__]))

        async with factory() as db:
            created = await create_agent_session(
                payload=AgentSessionCreate(
                    device_id=1,
                    package_name="com.example.app",
                    goal="Audit flow",
                    expected_outcome="Done",
                ),
                project_id=1,
                db=db,
                current_user=user,
            )
            await start_agent_session(project_id=1, session_id=created.id, db=db, current_user=user)
            await control_agent_session(
                payload=AgentControlRequest(action=AgentControlAction.takeover, reason="manual check"),
                project_id=1,
                session_id=created.id,
                db=db,
                current_user=user,
            )
            await manual_action_agent_session(
                payload=AgentManualActionRequest(action="tap", params={"x": 120, "y": 240}),
                project_id=1,
                session_id=created.id,
                db=db,
                current_user=user,
            )
            await complete_agent_session(
                payload=AgentCompleteRequest(
                    terminal_assertion_confirmed=True,
                    terminal_assertions=[{"type": "element_visible", "resource_id": "com.example:id/done"}],
                    summary="verified manually",
                ),
                project_id=1,
                session_id=created.id,
                db=db,
                current_user=user,
            )

            logs = list((await db.execute(select(AuditLog).order_by(AuditLog.id))).scalars().all())
            assert [row.action for row in logs] == [
                "android_agent_session_takeover",
                "android_agent_manual_action",
                "android_agent_session_complete",
            ]
            assert all(row.project_id == 1 for row in logs)
            assert all(row.resource_type == "android_agent_session" for row in logs)
            assert all(row.resource_id == created.id for row in logs)
            assert all(row.username == getattr(user, "username", "") for row in logs)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_manual_action_dispatches_once_and_does_not_persist_input(tmp_path: Path, monkeypatch):
    from sqlalchemy import select
    from app.api.v1 import android_agent

    engine, factory, user = await _setup_api_test_db(tmp_path)
    calls = []

    class FakeAdapter:
        def replace_text(self, resource_id, value, *, assert_write_allowed):
            assert_write_allowed()
            calls.append((resource_id, value))

    monkeypatch.setattr(android_agent, "AsyncSessionLocal", factory)
    monkeypatch.setattr(android_agent, "_build_device_adapter", lambda device, package: FakeAdapter())
    try:
        async with factory() as db:
            session = await create_agent_session(
                AgentSessionCreate(device_id=1, package_name="com.example.app", goal="Search", expected_outcome="Done"),
                project_id=1,
                db=db,
                current_user=user,
            )
            await start_agent_session(project_id=1, session_id=session.id, db=db, current_user=user)
            await control_agent_session(
                AgentControlRequest(action=AgentControlAction.takeover),
                project_id=1,
                session_id=session.id,
                db=db,
                current_user=user,
            )
            request = AgentManualActionRequest(
                action="input",
                params={"resource_id": "com.example.app:id/search", "text": "private-value"},
                idempotency_key="manual-once",
            )
            result = await manual_action_agent_session(
                request, project_id=1, session_id=session.id, db=db, current_user=user
            )
            repeat = await manual_action_agent_session(
                request, project_id=1, session_id=session.id, db=db, current_user=user
            )
            assert result["status"] == repeat["status"] == "succeeded"
            assert result["command_id"] == repeat["command_id"]
            assert calls == [("com.example.app:id/search", "private-value")]
            commands = (await db.execute(select(AndroidAgentCommand))).scalars().all()
            events = (await db.execute(select(AndroidAgentEvent))).scalars().all()
            assert "private-value" not in repr([c.params for c in commands])
            assert "private-value" not in repr([e.payload for e in events])
            assert any(e.event_type == "step_executed" and e.payload["controller"] == "manual" for e in events)

            from app.services.android_agent.device_adapter import DeviceAdapterError

            class UnknownAdapter:
                def tap(self, target, *, assert_write_allowed):
                    assert_write_allowed()
                    calls.append("uncertain")
                    raise DeviceAdapterError("write_outcome_unknown")

            monkeypatch.setattr(android_agent, "_build_device_adapter", lambda device, package: UnknownAdapter())
            unknown = AgentManualActionRequest(
                action="tap", params={"resource_id": "com.example.app:id/button"}, idempotency_key="unknown-once"
            )
            first = await manual_action_agent_session(
                unknown, project_id=1, session_id=session.id, db=db, current_user=user
            )
            second = await manual_action_agent_session(
                unknown, project_id=1, session_id=session.id, db=db, current_user=user
            )
            assert first["status"] == second["status"] == "outcome_unknown"
            assert calls.count("uncertain") == 1

            command = await db.get(AndroidAgentCommand, first["command_id"])
            command.status = "dispatching"
            await db.commit()
            session_id = session.id
            with pytest.raises(HTTPException) as exc:
                await control_agent_session(
                    AgentControlRequest(action=AgentControlAction.resume),
                    project_id=1,
                    session_id=session_id,
                    db=db,
                    current_user=user,
                )
            assert exc.value.status_code == 409
            await db.rollback()
            cancelled = await control_agent_session(
                AgentControlRequest(action=AgentControlAction.cancel),
                project_id=1,
                session_id=session_id,
                db=db,
                current_user=user,
            )
            assert cancelled.status == "cancelled"
            retained = await db.get(AndroidAgentSession, session_id)
            assert retained.lease_token is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_control_transition(tmp_path: Path):
    from app.models.audit import AuditLog

    engine, factory, user = await _setup_api_test_db(tmp_path)
    try:
        async with factory() as db:
            session = await create_agent_session(
                AgentSessionCreate(device_id=1, package_name="com.example.app", goal="Search", expected_outcome="Done"),
                project_id=1,
                db=db,
                current_user=user,
            )
            await start_agent_session(project_id=1, session_id=session.id, db=db, current_user=user)
            session_id = session.id

            def fail_audit(*args):
                raise RuntimeError("audit unavailable")

            event.listen(AuditLog, "before_insert", fail_audit)
            try:
                with pytest.raises(RuntimeError, match="audit unavailable"):
                    await control_agent_session(
                        AgentControlRequest(action=AgentControlAction.takeover),
                        project_id=1,
                        session_id=session_id,
                        db=db,
                        current_user=user,
                    )
            finally:
                event.remove(AuditLog, "before_insert", fail_audit)
            await db.rollback()
        async with factory() as db:
            session = await db.get(AndroidAgentSession, session_id)
            assert session.status == "running"
            assert session.controller == "agent"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancel_during_manual_write_retains_lease_until_call_finishes(tmp_path: Path, monkeypatch):
    import asyncio
    from threading import Event

    from app.api.v1 import android_agent
    from app.services.device_leases import get_active_device_lease

    engine, factory, user = await _setup_api_test_db(tmp_path)
    started, finish = Event(), Event()

    class SlowAdapter:
        def tap(self, target, *, assert_write_allowed):
            assert_write_allowed()
            started.set()
            assert finish.wait(90)

    monkeypatch.setattr(android_agent, "AsyncSessionLocal", factory)
    monkeypatch.setattr(android_agent, "_build_device_adapter", lambda device, package: SlowAdapter())
    try:
        async with factory() as db:
            session = await create_agent_session(
                AgentSessionCreate(device_id=1, package_name="com.example.app", goal="Tap", expected_outcome="Done"),
                project_id=1,
                db=db,
                current_user=user,
            )
            await start_agent_session(project_id=1, session_id=session.id, db=db, current_user=user)
            await control_agent_session(
                AgentControlRequest(action=AgentControlAction.takeover),
                project_id=1,
                session_id=session.id,
                db=db,
                current_user=user,
            )
            session_id, token = session.id, session.lease_token

        async with factory() as manual_db:
            task = asyncio.create_task(
                manual_action_agent_session(
                    AgentManualActionRequest(
                        action="tap", params={"resource_id": "com.example.app:id/button"}, idempotency_key="slow-action"
                    ),
                    project_id=1,
                    session_id=session_id,
                    db=manual_db,
                    current_user=user,
                )
            )
            try:
                assert await asyncio.to_thread(started.wait, 30)
                async with factory() as cancel_db:
                    result = await control_agent_session(
                        AgentControlRequest(action=AgentControlAction.cancel),
                        project_id=1,
                        session_id=session_id,
                        db=cancel_db,
                        current_user=user,
                    )
                    assert result.status == "cancelled"
                    assert await get_active_device_lease(cancel_db, 1, token) is not None
                finish.set()
                assert (await task)["status"] == "succeeded"
            finally:
                finish.set()
                if not task.done():
                    await task

        async with factory() as db:
            session = await db.get(AndroidAgentSession, session_id)
            assert session.status == "cancelled"
            assert session.lease_token is None
            assert await get_active_device_lease(db, 1, token) is None
    finally:
        finish.set()
        await engine.dispose()
