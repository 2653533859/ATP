"""M2 模型循环接入持久协调器的回归测试。

覆盖实施清单 A21/A22 的执行门槛：
- 每轮只在租约、控制代次和预算都有效时执行一次观察与一个候选动作；
- 暂停/接管/取消在动作前生效，未知结果不重复发送；
- 后端重启后非终态会话收敛为待人工核查，不自动继续设备操作；
- 人工接管后的手动动作在动作前复核控制权。
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.android_agent import AndroidAgentCommand, AndroidAgentEvent, AndroidAgentSession
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceLease
from app.models.project import Module, Project
from app.models.user import User
from app.schemas.android_agent import AgentManualActionRequest
from app.services.android_agent import loop as loop_module
from app.services.android_agent.coordinator import AgentCoordinator, UnauthorizedControllerError
from app.services.android_agent.contracts import parse_decision
from app.services.android_agent.device_adapter import DeviceAdapterError
from app.services.android_agent.loop import AgentLoopError, run_agent_session

load_all_models()
PACKAGE = "com.example.shop"
# 模型请求只作为"已配置"的占位，真正的模型调用由 probe_model 替身接管
LLM_REQUEST = SimpleNamespace(provider="openai", api_key="test", model_name="stub", prompt="")
NODE_XML = (
    '<hierarchy><node class="android.widget.FrameLayout" enabled="true" clickable="false" bounds="[0,0][1080,1920]">'
    f'<node class="android.widget.EditText" resource-id="{PACKAGE}:id/search" '
    'text="晴天" enabled="true" clickable="true" bounds="[40,120][1040,220]"/></node></hierarchy>'
)


class FakeTransport:
    """最小替身：只实现适配层用到的两个原语。"""

    def __init__(self, *, package: str = PACKAGE, nodes_xml: str = NODE_XML):
        self.package = package
        self.nodes_xml = nodes_xml
        self.calls: list[tuple[str, list]] = []

    def current_package(self) -> str:
        return self.package

    def rpc_once(self, method: str, params: list) -> object:
        self.calls.append((method, params))
        if method == "dumpWindowHierarchy":
            return self.nodes_xml
        if method == "count":
            return 1
        return True


class FakeAdapter:
    """记录动作调用，便于断言"未知结果不重复发送"与"动作前复核"。"""

    package = PACKAGE

    def __init__(self, *, fail_with: str | None = None):
        self.actions: list[str] = []
        self.observations = 0
        self.fail_with = fail_with

    def observe(self, *, attempts: int = 3):
        from app.services.android_agent.observation import parse_hierarchy

        self.observations += 1
        return parse_hierarchy(NODE_XML.encode("utf-8"), width=1080, height=1920)

    def tap(self, target, *, assert_write_allowed):
        assert_write_allowed()
        if self.fail_with:
            raise DeviceAdapterError(self.fail_with)
        self.actions.append("tap")

    def replace_text(self, resource_id, value, *, assert_write_allowed):
        assert_write_allowed()
        if self.fail_with:
            raise DeviceAdapterError(self.fail_with)
        self.actions.append("input:" + value)

    def press_back(self, *, assert_write_allowed):
        assert_write_allowed()
        if self.fail_with:
            raise DeviceAdapterError(self.fail_with)
        self.actions.append("back")

    def swipe(self, direction, distance_fraction, *, assert_write_allowed):
        assert_write_allowed()
        if self.fail_with:
            raise DeviceAdapterError(self.fail_with)
        self.actions.append("swipe:" + direction)

    def wait_for(self, target, *, timeout_ms, absent=False):
        return self.observe()


async def _setup_db(tmp_path: Path, *, tag: str = "loop"):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{(tmp_path / f'{tag}.sqlite').as_posix()}", connect_args={"timeout": 5}
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
        Base.metadata.tables["modules"],
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
        db.add(User(username="loop_user", email="loop@example.com", hashed_password="pw", role="admin"))
        await db.commit()
        db.add(Project(name="Loop Project", description="Test", owner_id=1))
        await db.flush()
        db.add(Module(id=1, project_id=1, name="默认模块"))
        db.add(Device(id=5, serial="loop-5554", status="online"))
        await db.commit()
    return engine, factory


async def _running_session(factory) -> int:
    """用协调器真实建立一条 running 会话（含租约），保证状态机路径不绕过。"""
    async with factory() as db:
        coordinator = AgentCoordinator()
        session = AndroidAgentSession(
            project_id=1,
            device_id=5,
            created_by=1,
            title="搜索商品",
            goal="搜索商品并打开详情",
            expected_outcome="详情页商品名称等于 测试商品",
            package_name=PACKAGE,
            status="created",
            controller="agent",
            budget_max_steps=5,
            budget_max_calls=5,
        )
        db.add(session)
        await db.commit()
        session = await coordinator.start_session(db, session.id)
        await db.commit()
        return session.id


def _decisions(script: list[dict]):
    """把预置决策脚本包装成 probe_model 替身。"""
    calls = {"n": 0}

    async def fake_probe(request, *, goal, observation):
        index = min(calls["n"], len(script) - 1)
        calls["n"] += 1
        return SimpleNamespace(
            decision=script[index],
            elapsed_ms=1,
            usage={"total_tokens": 12},
        )

    return fake_probe, calls


def _decision(action: str, **extra):
    """构造真实契约对象，避免用裸 dict 绕过联合类型校验。"""
    base = {"action": action, "observation_id": "obs", "schema_version": 1, "reason": "test"}
    base.update(extra)
    return parse_decision(json.dumps(base))


@pytest.fixture(autouse=True)
def _patch_probe(monkeypatch):
    """默认让所有决策落到 request_help，避免任何真实模型调用。"""

    async def fake_probe(request, *, goal, observation):
        raise AssertionError("测试必须显式 patch probe")

    monkeypatch.setattr(loop_module, "probe_model", fake_probe)
    from app.services.android_agent import coordinator

    async def no_publish(*args, **kwargs):
        pass

    monkeypatch.setattr(coordinator, "_safe_publish_agent_event", no_publish)
    return monkeypatch


@pytest.mark.asyncio
async def test_loop_stops_on_request_help_and_never_retries_write(tmp_path: Path):
    engine, factory = await _setup_db(tmp_path, tag="help")
    try:
        session_id = await _running_session(factory)
        probe, _ = _decisions([_decision("request_help", code="cannot_progress")])
        loop_module.probe_model = probe
        adapter = FakeAdapter()

        result = await run_agent_session(
            factory,
            session_id,
            adapter=adapter,
            llm_request=LLM_REQUEST,
            values={},
        )

        assert result.status == "needs_review"
        assert result.reason == "cannot_progress"
        assert adapter.actions == []
        assert result.model_calls == 1
        async with factory() as db:
            session = await db.get(AndroidAgentSession, session_id)
            assert session.status == "paused"
            events = (
                (await db.execute(select(AndroidAgentEvent).where(AndroidAgentEvent.session_id == session_id)))
                .scalars()
                .all()
            )
            assert any(event.event_type == "session_paused" for event in events)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_loop_executes_one_action_and_records_progress(tmp_path: Path):
    engine, factory = await _setup_db(tmp_path, tag="act")
    try:
        session_id = await _running_session(factory)
        probe, calls = _decisions(
            [
                _decision(
                    "tap",
                    target={"node_id": "n2"},
                    expected_observation={"type": "element_visible", "resource_id": f"{PACKAGE}:id/search"},
                ),
                _decision("request_help", code="cannot_progress"),
            ]
        )
        loop_module.probe_model = probe
        adapter = FakeAdapter()

        result = await run_agent_session(factory, session_id, adapter=adapter, llm_request=LLM_REQUEST, values={})

        assert result.status == "needs_review"
        assert adapter.actions == ["tap"]
        assert calls["n"] == 2
        # request_help 是终止轮：会话计数已含两次模型调用，返回结果只带本轮用量
        assert result.model_calls == 1
        assert result.tokens == 12
        async with factory() as db:
            session = await db.get(AndroidAgentSession, session_id)
            assert session.steps_count == 1
            # 每轮都记账一次模型调用（含未执行动作的 request_help 轮）
            assert session.model_calls_count == 2
            assert session.total_tokens == 24
            steps = (
                (
                    await db.execute(
                        select(AndroidAgentEvent).where(
                            AndroidAgentEvent.session_id == session_id, AndroidAgentEvent.event_type == "step_executed"
                        )
                    )
                )
                .scalars()
                .all()
            )
            # 一条执行成功的动作 + 一条终止轮记账，两者都写进轨迹
            assert len(steps) == 2
            acted = [item for item in steps if item.payload.get("action") == "tap"]
            assert len(acted) == 1
            assert acted[0].payload["action_status"] == "succeeded"
            assert any(item.payload.get("action_status") == "not_executed" for item in steps)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_loop_unknown_outcome_halts_without_retry(tmp_path: Path):
    engine, factory = await _setup_db(tmp_path, tag="unknown")
    try:
        session_id = await _running_session(factory)
        probe, calls = _decisions(
            [
                _decision(
                    "tap",
                    target={"node_id": "n2"},
                    expected_observation={"type": "element_visible", "resource_id": f"{PACKAGE}:id/search"},
                )
            ]
        )
        loop_module.probe_model = probe
        adapter = FakeAdapter(fail_with="write_outcome_unknown")

        result = await run_agent_session(factory, session_id, adapter=adapter, llm_request=LLM_REQUEST, values={})

        assert result.status == "needs_review"
        # 适配层返回的稳定码原样上报，便于定位是哪一步进入了未知状态
        assert result.reason == "write_outcome_unknown"
        # 未知结果绝不重发：只调用一次模型、一次动作
        assert calls["n"] == 1
        assert adapter.actions == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_loop_aborts_before_action_when_epoch_changes(tmp_path: Path):
    engine, factory = await _setup_db(tmp_path, tag="epoch")
    try:
        session_id = await _running_session(factory)
        probe, calls = _decisions(
            [
                _decision(
                    "tap",
                    target={"node_id": "n2"},
                    expected_observation={"type": "element_visible", "resource_id": f"{PACKAGE}:id/search"},
                )
            ]
        )
        loop_module.probe_model = probe
        adapter = FakeAdapter()

        async def pause_during_model_wait(request, **kwargs):
            # 模拟模型请求期间用户点下暂停：代次递增，旧决策必须失效
            result = await probe(request, **kwargs)
            async with factory() as db:
                await AgentCoordinator().control_session(db, session_id, "pause")
                await db.commit()
            return result

        loop_module.probe_model = pause_during_model_wait

        result = await run_agent_session(factory, session_id, adapter=adapter, llm_request=LLM_REQUEST, values={})

        assert result.status == "halted"
        # 暂停先落库，门禁在动作前发现会话已非 running，返回 write_cancelled
        assert result.reason in {"control_epoch_changed", "write_cancelled"}
        assert adapter.actions == []
        assert calls["n"] == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_disabling_during_model_call_pauses_before_device_write(tmp_path: Path, monkeypatch):
    engine, factory = await _setup_db(tmp_path, tag="disabled")
    try:
        session_id = await _running_session(factory)
        tap = _decision(
            "tap",
            target={"node_id": "n2"},
            expected_observation={"type": "element_visible", "resource_id": f"{PACKAGE}:id/search"},
        )
        probe, _ = _decisions([tap])

        async def disable_during_probe(request, **kwargs):
            result = await probe(request, **kwargs)
            monkeypatch.setattr(loop_module.settings, "ANDROID_AGENT_ENABLED", False)
            return result

        monkeypatch.setattr(loop_module, "probe_model", disable_during_probe)
        adapter = FakeAdapter()
        result = await run_agent_session(factory, session_id, adapter=adapter, llm_request=LLM_REQUEST)
        assert result.reason == "android_agent_disabled"
        assert adapter.actions == []
        async with factory() as db:
            session = await db.get(AndroidAgentSession, session_id)
            assert session.status == "paused"
            assert session.lease_token
            events = (await db.execute(select(AndroidAgentEvent))).scalars().all()
            assert any(
                e.event_type == "session_paused" and e.payload["reason"] == "android_agent_disabled" for e in events
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_disabled_startup_sweep_invalidates_running_session_and_retains_lease(tmp_path: Path):
    engine, factory = await _setup_db(tmp_path, tag="disabled-sweep")
    try:
        session_id = await _running_session(factory)
        async with factory() as db:
            session = await db.get(AndroidAgentSession, session_id)
            old_epoch, old_token = session.control_epoch, session.lease_token
            assert await AgentCoordinator().pause_disabled_sessions(db) == [session_id]
            await db.commit()
        async with factory() as db:
            session = await db.get(AndroidAgentSession, session_id)
            assert session.status == "paused"
            assert session.control_epoch == old_epoch + 1
            assert session.lease_token == old_token
            assert await AgentCoordinator().pause_disabled_sessions(db) == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_loop_honours_step_budget(tmp_path: Path):
    engine, factory = await _setup_db(tmp_path, tag="budget")
    try:
        session_id = await _running_session(factory)
        tap = _decision(
            "tap",
            target={"node_id": "n2"},
            expected_observation={"type": "element_visible", "resource_id": f"{PACKAGE}:id/search"},
        )
        probe, calls = _decisions([tap])
        loop_module.probe_model = probe
        adapter = FakeAdapter()

        async with factory() as db:
            session = await db.get(AndroidAgentSession, session_id)
            session.budget_max_steps = 4
            session.budget_max_calls = 20
            await db.commit()

        result = await run_agent_session(factory, session_id, adapter=adapter, llm_request=LLM_REQUEST, values={})

        assert result.status == "halted"
        assert result.reason == "budget_exceeded"
        # 预算按已落库动作计：4 步预算恰好执行 4 次，不多不少
        assert len(adapter.actions) == 4
        assert calls["n"] == 4
        async with factory() as db:
            session = await db.get(AndroidAgentSession, session_id)
            assert session.status == "failed"
            assert session.error_code == "budget_exceeded"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_loop_translates_adapter_readiness_error_to_stable_code(tmp_path: Path):
    engine, factory = await _setup_db(tmp_path, tag="ready")
    try:
        session_id = await _running_session(factory)
        probe, _ = _decisions([_decision("back", expected_observation={"type": "element_visible", "resource_id": "x"})])
        loop_module.probe_model = probe
        adapter = FakeAdapter()

        def broken_observe(*, attempts=3):
            raise DeviceAdapterError("observation_unavailable")

        adapter.observe = broken_observe  # type: ignore[method-assign]

        result = await run_agent_session(factory, session_id, adapter=adapter, llm_request=LLM_REQUEST, values={})

        assert result.status == "needs_review"
        assert result.reason == "observation_unavailable"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_loop_requires_running_session(tmp_path: Path):
    engine, factory = await _setup_db(tmp_path, tag="state")
    try:
        async with factory() as db:
            session = AndroidAgentSession(
                project_id=1,
                device_id=5,
                created_by=1,
                title="t",
                goal="g",
                expected_outcome="e",
                package_name=PACKAGE,
                status="created",
            )
            db.add(session)
            await db.commit()
            session_id = session.id

        with pytest.raises(AgentLoopError) as exc_info:
            await run_agent_session(factory, session_id, adapter=FakeAdapter(), llm_request=LLM_REQUEST, values={})
        assert "session_not_running" in str(exc_info.value)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recovery_converges_to_review_and_does_not_continue(tmp_path: Path):
    engine, factory = await _setup_db(tmp_path, tag="recover")
    try:
        session_id = await _running_session(factory)
        async with factory() as db:
            recovered = await AgentCoordinator().recover_orphaned_sessions(db, inactive_threshold_seconds=0)
            await db.commit()
            assert session_id in recovered
            session = await db.get(AndroidAgentSession, session_id)
            # 不自动继续：状态收敛为 failed，错误码标记需人工核查
            assert session.status == "failed"
            assert session.error_code == "system_restarted_needs_review"
            events = (
                (
                    await db.execute(
                        select(AndroidAgentEvent).where(
                            AndroidAgentEvent.session_id == session_id, AndroidAgentEvent.event_type == "session_failed"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert events
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_manual_action_requires_manual_control_and_dispatch_is_gated(tmp_path: Path):
    engine, factory = await _setup_db(tmp_path, tag="manual")
    try:
        session_id = await _running_session(factory)
        coordinator = AgentCoordinator()
        async with factory() as db:
            # 未接管时禁止人工动作
            with pytest.raises(UnauthorizedControllerError):
                await coordinator.manual_action(db, session_id, AgentManualActionRequest(action="back"))

            await coordinator.control_session(db, session_id, "takeover")
            await db.commit()

        executed: list[int] = []

        def fake_executor(db, session, command):
            executed.append(command.id)

        async with factory() as db:
            command = await coordinator.manual_action(db, session_id, AgentManualActionRequest(action="back"))
            await db.commit()
            assert command.status == "prepared"
            await coordinator.dispatch_prepared_command(db, session_id, command.id, execute=fake_executor)
            await db.commit()
            stored = await db.get(AndroidAgentCommand, command.id)
            assert stored.status == "succeeded"
            assert executed == [command.id]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_manual_action_deferred_while_agent_holds_control(tmp_path: Path):
    engine, factory = await _setup_db(tmp_path, tag="defer")
    try:
        session_id = await _running_session(factory)
        coordinator = AgentCoordinator()
        async with factory() as db:
            await coordinator.control_session(db, session_id, "takeover")
            await db.commit()

            command = await coordinator.manual_action(db, session_id, AgentManualActionRequest(action="back"))
            await db.commit()
            assert command.status == "prepared"

            # 执行前控制权被交还 agent：门禁必须拒绝，且不产生设备写入
            session = await db.get(AndroidAgentSession, session_id)
            session.controller = "agent"
            await db.commit()

            def explode(db, session, cmd):
                raise AssertionError("控制权在 agent 手上时不得执行人工动作")

            with pytest.raises(HTTPException) as exc_info:
                await coordinator.dispatch_prepared_command(db, session_id, command.id, execute=explode)
            assert exc_info.value.status_code == 409
    finally:
        await engine.dispose()
