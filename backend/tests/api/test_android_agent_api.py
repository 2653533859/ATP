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
async def test_api_control_session_and_version_defense(tmp_path: Path):
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
            # 接口只登记 prepared，设备写入由控制权门禁放行后执行
            assert manual_resp["status"] == "prepared"

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
