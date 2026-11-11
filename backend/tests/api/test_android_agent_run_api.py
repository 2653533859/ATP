"""Android Agent 模型循环接入 API 的回归测试（A22 控制面）。

只验证装配与门禁，不连接真实设备与模型：适配器、模型请求都由替身接管。
"""

from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.api.v1.android_agent as agent_api
from app.models.android_agent import AndroidAgentEvent, AndroidAgentSession
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceLease
from app.models.project import Project
from app.models.user import User
from app.services.android_agent.loop import AgentLoopError

load_all_models()


async def _setup(tmp_path: Path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{(tmp_path / 'run_api.sqlite').as_posix()}", connect_args={"timeout": 5}
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _configure(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    tables = [
        Base.metadata.tables["users"],
        Base.metadata.tables["ai_llm_configs"],
        Base.metadata.tables["projects"],
        Device.__table__,
        DeviceLease.__table__,
        AndroidAgentSession.__table__,
        AndroidAgentEvent.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add(User(username="runner", email="runner@example.com", hashed_password="pw", role="admin"))
        await db.commit()
        db.add(Project(name="Run Project", description="Test", owner_id=1))
        await db.commit()
        db.add(Device(id=5, serial="run-5554", status="online"))
        await db.commit()
    return engine, factory


async def _session(factory, *, status_value: str = "running") -> int:
    async with factory() as db:
        session = AndroidAgentSession(
            project_id=1,
            device_id=5,
            created_by=1,
            title="搜索商品",
            goal="搜索商品并打开详情",
            expected_outcome="详情页可见",
            package_name="com.example.shop",
            status=status_value,
            controller="agent",
        )
        db.add(session)
        await db.commit()
        return session.id


@pytest.mark.asyncio
async def test_run_endpoint_rejects_non_running_session(tmp_path: Path):
    engine, factory = await _setup(tmp_path)
    try:
        session_id = await _session(factory, status_value="created")
        async with factory() as db:
            user = await db.get(User, 1)
            with pytest.raises(HTTPException) as exc_info:
                await agent_api.run_agent_session_endpoint(
                    project_id=1, session_id=session_id, max_rounds=5, db=db, current_user=user
                )
            assert exc_info.value.status_code == 409
            assert "agent_loop_rejected" in exc_info.value.detail
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_run_endpoint_requires_vision_model(tmp_path: Path):
    engine, factory = await _setup(tmp_path)
    try:
        session_id = await _session(factory)
        async with factory() as db:
            user = await db.get(User, 1)
            with pytest.raises(HTTPException) as exc_info:
                await agent_api.run_agent_session_endpoint(
                    project_id=1, session_id=session_id, max_rounds=5, db=db, current_user=user
                )
            # 会话未绑定模型配置
            assert exc_info.value.status_code == 409
            assert "model_capability_missing" in exc_info.value.detail
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_run_endpoint_returns_loop_result(tmp_path: Path, monkeypatch):
    engine, factory = await _setup(tmp_path)
    try:
        session_id = await _session(factory)
        async with factory() as db:
            user = await db.get(User, 1)
            db.add(
                agent_api.AILLMConfig(
                    id=1,
                    name="vision-model",
                    provider="openai",
                    api_key_encrypted="cipher",
                    model_name="gpt-4o",
                    supports_vision=True,
                    enabled=True,
                )
            )
            await db.commit()
            session = await db.get(AndroidAgentSession, session_id)
            session.llm_config_id = 1
            await db.commit()

        monkeypatch.setattr(agent_api, "decrypt", lambda _value: "plain-key")
        monkeypatch.setattr(agent_api, "_build_device_adapter", lambda device, package: object())

        captured: dict[str, object] = {}

        async def fake_loop(session_factory, sid, *, adapter, llm_request, values, max_rounds):
            captured.update({"session_id": sid, "values": values, "max_rounds": max_rounds})
            from app.services.android_agent.loop import LoopResult

            return LoopResult(status="needs_review", reason="cannot_progress", steps=1, model_calls=2, tokens=30)

        monkeypatch.setattr(agent_api, "run_agent_session", fake_loop)

        async with factory() as db:
            user = await db.get(User, 1)
            result = await agent_api.run_agent_session_endpoint(
                project_id=1, session_id=session_id, max_rounds=7, db=db, current_user=user
            )
        assert result.status == "needs_review"
        assert result.reason == "cannot_progress"
        assert result.model_calls == 2
        assert captured["session_id"] == session_id
        assert captured["max_rounds"] == 7
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_run_endpoint_maps_loop_rejection_to_409(tmp_path: Path, monkeypatch):
    engine, factory = await _setup(tmp_path)
    try:
        session_id = await _session(factory)
        async with factory() as db:
            user = await db.get(User, 1)
            db.add(
                agent_api.AILLMConfig(
                    id=1,
                    name="vision-model",
                    provider="openai",
                    api_key_encrypted="cipher",
                    model_name="gpt-4o",
                    supports_vision=True,
                    enabled=True,
                )
            )
            await db.commit()
            session = await db.get(AndroidAgentSession, session_id)
            session.llm_config_id = 1
            await db.commit()

        monkeypatch.setattr(agent_api, "decrypt", lambda _value: "plain-key")
        monkeypatch.setattr(agent_api, "_build_device_adapter", lambda device, package: object())

        async def reject_loop(*args, **kwargs):
            raise AgentLoopError("lease_missing")

        monkeypatch.setattr(agent_api, "run_agent_session", reject_loop)

        async with factory() as db:
            user = await db.get(User, 1)
            with pytest.raises(HTTPException) as exc_info:
                await agent_api.run_agent_session_endpoint(
                    project_id=1, session_id=session_id, max_rounds=5, db=db, current_user=user
                )
            assert exc_info.value.status_code == 409
            assert "lease_missing" in exc_info.value.detail
    finally:
        await engine.dispose()
