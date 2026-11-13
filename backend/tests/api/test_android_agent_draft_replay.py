"""M3 轨迹编译、草稿版本、独立回放与幂等保存正式用例的回归测试。

覆盖实施清单 A30–A33：草稿来源映射与阻断项、版本不可变与验证资格失效、
回放/发布的幂等与冲突，以及跨项目隔离。
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.api.v1.android_agent as android_agent_api
from app.api.v1.android_agent import (
    complete_agent_session,
    create_agent_draft,
    get_agent_draft,
    get_agent_replay,
    preview_agent_draft_replay,
    publish_agent_draft,
    start_agent_draft_replay,
    update_agent_draft,
)
from app.models.android_agent import (
    AndroidAgentDraft,
    AndroidAgentEvent,
    AndroidAgentReplay,
    AndroidAgentSession,
)
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceLease
from app.models.case import TestCase, TestRun
from app.models.project import Module, Project
from app.models.user import User
from app.schemas.android_agent import (
    AgentCompleteRequest,
    AgentDraftCreateRequest,
    AgentDraftPatchRequest,
    AgentReplayStartRequest,
)
from app.services.android_agent.compiler import DRAFT_SCHEMA_VERSION, compile_session_draft

load_all_models()


@pytest.fixture(autouse=True)
def _stub_replay_dispatch(monkeypatch):
    """回放派发依赖 Celery 队列；单测只验证记录与幂等，不实际投递任务。"""
    calls: list[int] = []
    monkeypatch.setattr(android_agent_api, "_enqueue_replay_run", lambda run, case, session: calls.append(run.id))
    from app.services.android_agent import coordinator

    async def no_publish(*args, **kwargs):
        pass

    monkeypatch.setattr(coordinator, "_safe_publish_agent_event", no_publish)
    return calls


PACKAGE = "com.example.shop"


def test_manual_input_and_fixed_wait_remain_blocked_until_draft_review():
    events = [
        SimpleNamespace(
            seq=1,
            event_type="step_executed",
            payload={
                "action": "input",
                "action_status": "succeeded",
                "controller": "manual",
                "node": {"resource_id": f"{PACKAGE}:id/search"},
                "params": {},
            },
        ),
        SimpleNamespace(
            seq=2,
            event_type="step_executed",
            payload={
                "action": "wait",
                "action_status": "succeeded",
                "controller": "manual",
                "params": {"duration_ms": 1000},
            },
        ),
        SimpleNamespace(seq=3, event_type="session_completed", payload={}),
    ]
    draft = compile_session_draft(
        session_id=1,
        package_name=PACKAGE,
        goal="Search",
        expected_outcome="Result",
        events=events,
        terminal_assertions=[{"type": "element_visible", "resource_id": f"{PACKAGE}:id/result"}],
    )
    codes = {issue["code"] for issue in draft.blocking_issues}
    assert {"step_unsafe_input", "step_needs_manual_review"} <= codes
    assert not draft.replayable


async def _setup_db(tmp_path: Path, *, tag: str = "base"):
    db_path = tmp_path / f"agent_m3_{tag}.sqlite"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}", connect_args={"timeout": 5})

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
        Base.metadata.tables["test_cases"],
        Base.metadata.tables["test_runs"],
        Base.metadata.tables["test_datasets"],
        Base.metadata.tables["case_steps"],
        Device.__table__,
        DeviceLease.__table__,
        AndroidAgentSession.__table__,
        AndroidAgentEvent.__table__,
        Base.metadata.tables["android_agent_commands"],
        AndroidAgentDraft.__table__,
        AndroidAgentReplay.__table__,
        Base.metadata.tables["audit_logs"],
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(username="agent_m3", email="agent_m3@example.com", hashed_password="pw", role="admin")
        db.add(user)
        await db.commit()
        db.add_all(
            [
                Project(name="Agent M3 Project", description="Test", owner_id=user.id),
                Project(name="Agent M3 Other", description="Test", owner_id=user.id),
            ]
        )
        db.add(Device(id=1, serial="agent-m3-001", status="online"))
        await db.flush()
        db.add(Module(id=1, project_id=1, name="Android Agent"))
        await db.commit()
    return engine, factory, user


def _trajectory_events() -> list[dict]:
    """一条成功轨迹：启动应用、中文关键字输入、点按结果、终态断言。"""
    return [
        {"seq": 1, "event_type": "session_created", "payload": {"goal": "搜索商品并打开详情", "package_name": PACKAGE}},
        {"seq": 2, "event_type": "session_running", "payload": {}},
        {
            "seq": 3,
            "event_type": "step_executed",
            "payload": {
                "observation_id": "obs-1",
                "action": "launch_app",
                "action_status": "succeeded",
                "params": {"package_name": PACKAGE},
                "node": {"resource_id": "", "text": "", "class_name": ""},
                "expected": {"type": "element_visible", "resource_id": f"{PACKAGE}:id/search_input"},
            },
        },
        {
            "seq": 4,
            "event_type": "step_executed",
            "payload": {
                "observation_id": "obs-2",
                "action": "input",
                "action_status": "succeeded",
                "params": {"value_ref": "keyword"},
                "node": {
                    "resource_id": f"{PACKAGE}:id/search_input",
                    "text": "",
                    "class_name": "android.widget.EditText",
                },
                "expected": {"type": "element_visible", "resource_id": f"{PACKAGE}:id/result_list"},
            },
        },
        {
            "seq": 5,
            "event_type": "step_executed",
            "payload": {
                "observation_id": "obs-3",
                "action": "tap",
                "action_status": "succeeded",
                "params": {},
                "node": {
                    "resource_id": f"{PACKAGE}:id/item_title",
                    "text": "测试商品",
                    "class_name": "android.widget.TextView",
                },
                "expected": {"type": "element_visible", "resource_id": f"{PACKAGE}:id/detail_title"},
            },
        },
        {
            "seq": 6,
            "event_type": "step_executed",
            "payload": {
                "observation_id": "obs-4",
                "action": "finish",
                "action_status": "succeeded",
                "params": {},
                "node": {"resource_id": "", "text": "", "class_name": ""},
                "expected": {"type": "element_visible", "resource_id": f"{PACKAGE}:id/product_stock"},
            },
        },
        {"seq": 7, "event_type": "session_completed", "payload": {"outcome": "success"}},
    ]


async def _seed_session(factory, *, project_id: int = 1, status_value: str = "completed") -> int:
    async with factory() as db:
        session = AndroidAgentSession(
            project_id=project_id,
            device_id=1,
            created_by=1,
            title="搜索商品",
            goal="搜索商品并打开详情",
            expected_outcome="详情页商品名称等于 测试商品",
            package_name=PACKAGE,
            status=status_value,
            controller="agent",
            # 用户确认的终态断言：草稿只能从这里取得回放依据
            terminal_assertions=[{"type": "element_visible", "resource_id": f"{PACKAGE}:id/product_stock"}],
        )
        db.add(session)
        await db.flush()
        events = _trajectory_events()
        if status_value != "completed":
            events[-1] = {"seq": 7, "event_type": f"session_{status_value}", "payload": {"reason": "seed"}}
        for item in events:
            db.add(AndroidAgentEvent(session_id=session.id, **item))
        await db.commit()
        session_id = session.id
    return session_id


# ---------------- A30 轨迹编译 ----------------


def test_compile_success_trajectory_to_replayable_draft():
    events = [SimpleNamespace(**item) for item in _trajectory_events()]
    result = compile_session_draft(
        session_id=1,
        package_name=PACKAGE,
        goal="搜索商品并打开详情",
        expected_outcome="详情页商品名称等于 测试商品",
        events=events,
        terminal_assertions=[{"type": "element_visible", "resource_id": f"{PACKAGE}:id/product_stock"}],
    )

    assert result.schema_version == DRAFT_SCHEMA_VERSION
    assert result.replayable is True
    assert result.blocking_issues == []
    assert [step["action"] for step in result.steps] == ["start_app", "input", "click"]
    # 启动应用由任务配置决定，固定为第一步
    assert result.steps[0]["params"]["package_name"] == PACKAGE
    # 输入参数使用运行变量引用，不写入明文
    assert result.steps[1]["params"]["value"] == "${keyword}"
    assert result.steps[1]["params"]["resource_id"] == f"{PACKAGE}:id/search_input"
    # 点按优先保存稳定选择器，不保存坐标
    assert result.steps[2]["params"]["resource_id"] == f"{PACKAGE}:id/item_title"
    assert "x" not in result.steps[2]["params"] and "y" not in result.steps[2]["params"]
    # 终态断言来自用户确认的成功条件，模型 finish 不生成操作步骤
    assert result.assertions == [{"type": "element_visible", "resource_id": f"{PACKAGE}:id/product_stock"}]
    # 每个步骤保留来源事件序号
    # 启动应用由任务配置注入，来源为空；其余步骤映射回原事件序号
    assert [step["source_seq"] for step in result.steps] == [None, 4, 5]
    assert result.variables == ["keyword"]


def test_compile_failed_trajectory_keeps_blocking_issues():
    events = [SimpleNamespace(**item) for item in _trajectory_events()]
    events[-1] = SimpleNamespace(seq=7, event_type="session_failed", payload={"error_code": "target_ambiguous"})
    events.insert(
        4,
        SimpleNamespace(
            seq=99,
            event_type="step_executed",
            payload={
                "observation_id": "obs-3",
                "action": "tap",
                "action_status": "failed",
                "params": {},
                "node": {"resource_id": "", "text": "", "class_name": ""},
            },
        ),
    )

    result = compile_session_draft(
        session_id=1,
        package_name=PACKAGE,
        goal="搜索商品",
        expected_outcome="详情页可见",
        events=events,
        terminal_assertions=[{"type": "element_visible", "resource_id": f"{PACKAGE}:id/detail"}],
    )

    assert result.replayable is False
    codes = {issue["code"] for issue in result.blocking_issues}
    assert "session_not_completed" in codes
    assert "step_failed" in codes
    manual = [step for step in result.steps if step.get("needs_manual_review")]
    assert manual, "无法证明可自动转换的步骤必须进入待人工整理"


def test_compile_is_deterministic_and_hashes_content():
    events = [SimpleNamespace(**item) for item in _trajectory_events()]
    first = compile_session_draft(session_id=1, package_name=PACKAGE, goal="g", expected_outcome="e", events=events)
    second = compile_session_draft(session_id=1, package_name=PACKAGE, goal="g", expected_outcome="e", events=events)
    assert first.content_hash == second.content_hash
    assert len(first.content_hash) == 64


def test_finish_event_is_not_a_failed_step():
    """finish 是终止建议，action_status=not_executed 是正常的，不能判成失败步骤。"""
    events = [SimpleNamespace(**item) for item in _trajectory_events()]
    events.insert(
        6,
        SimpleNamespace(
            seq=70,
            event_type="step_executed",
            payload={
                "observation_id": "obs-5",
                "action": "finish",
                "action_status": "not_executed",
                "expected": {"type": "element_visible", "resource_id": f"{PACKAGE}:id/product_stock"},
            },
        ),
    )
    result = compile_session_draft(session_id=1, package_name=PACKAGE, goal="g", expected_outcome="e", events=events)
    codes = {issue["code"] for issue in result.blocking_issues}
    assert "step_failed" not in codes


def test_user_confirmed_assertion_is_the_only_passing_basis():
    """终态断言只认用户确认值；模型 finish 的建议值不能直接让草稿可回放。"""
    events = [SimpleNamespace(**item) for item in _trajectory_events()]
    events.insert(
        6,
        SimpleNamespace(
            seq=70,
            event_type="step_executed",
            payload={
                "observation_id": "obs-5",
                "action": "finish",
                "action_status": "not_executed",
                "expected": {"type": "element_visible", "resource_id": f"{PACKAGE}:id/model_suggested"},
            },
        ),
    )
    confirmed = [{"type": "element_visible", "resource_id": f"{PACKAGE}:id/user_confirmed"}]
    result = compile_session_draft(
        session_id=1,
        package_name=PACKAGE,
        goal="g",
        expected_outcome="e",
        events=events,
        terminal_assertions=confirmed,
    )
    assert result.replayable is True
    assert result.assertions == confirmed


def test_trajectory_suggested_assertion_is_flagged_when_unconfirmed():
    """没有用户确认时退回轨迹建议值，但必须显式标注未经确认。"""
    events = [SimpleNamespace(**item) for item in _trajectory_events()]
    events.insert(
        6,
        SimpleNamespace(
            seq=70,
            event_type="step_executed",
            payload={
                "observation_id": "obs-5",
                "action": "finish",
                "action_status": "not_executed",
                "expected": {"type": "element_visible", "resource_id": f"{PACKAGE}:id/suggested"},
            },
        ),
    )
    result = compile_session_draft(session_id=1, package_name=PACKAGE, goal="g", expected_outcome="e", events=events)
    assert result.replayable is False
    assert "assertion_not_user_confirmed" in {issue["code"] for issue in result.blocking_issues}


def test_missing_assertion_blocks_replay():
    events = [SimpleNamespace(**item) for item in _trajectory_events()]
    result = compile_session_draft(session_id=1, package_name=PACKAGE, goal="g", expected_outcome="e", events=events)
    assert result.replayable is False
    # 轨迹里的 finish 建议值不算用户确认，必须显式标注
    assert "assertion_not_user_confirmed" in {issue["code"] for issue in result.blocking_issues}


# ---------------- A30/A31 API：创建与版本 ----------------


@pytest.mark.asyncio
async def test_api_create_draft_persists_immutable_version(tmp_path: Path):
    engine, factory, user = await _setup_db(tmp_path, tag="create")
    try:
        session_id = await _seed_session(factory)
        async with factory() as db:
            draft_out = await create_agent_draft(
                project_id=1,
                session_id=session_id,
                payload=AgentDraftCreateRequest(),
                db=db,
                current_user=user,
            )
            assert draft_out.version == 1
            assert draft_out.status == "replayable"
            assert len(draft_out.steps) == 3
            first_hash = draft_out.content_hash

            # 轨迹未变化时重复编译复用既有版本，不产生重复版本
            second = await create_agent_draft(
                project_id=1,
                session_id=session_id,
                payload=AgentDraftCreateRequest(),
                db=db,
                current_user=user,
            )
            assert second.id == draft_out.id
            assert second.version == 1
            assert second.content_hash == first_hash

            # 轨迹新增事件后编译才产生新版本，旧版本内容保持不变
            async with factory() as event_db:
                event_db.add(
                    AndroidAgentEvent(
                        session_id=session_id,
                        seq=80,
                        event_type="step_executed",
                        payload={
                            "observation_id": "obs-5",
                            "action": "back",
                            "action_status": "succeeded",
                            "params": {},
                            "node": {"resource_id": "", "text": "", "class_name": ""},
                            "expected": {"type": "element_visible", "resource_id": f"{PACKAGE}:id/result_list"},
                        },
                    )
                )
                await event_db.commit()
            third = await create_agent_draft(
                project_id=1,
                session_id=session_id,
                payload=AgentDraftCreateRequest(),
                db=db,
                current_user=user,
            )
            assert third.version == 2
            assert third.content_hash != first_hash

            old = await get_agent_draft(project_id=1, draft_id=draft_out.id, db=db, current_user=user)
            assert old.version == 1
            assert old.steps == draft_out.steps
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_patch_draft_creates_new_version_and_invalidates_verification(tmp_path: Path):
    engine, factory, user = await _setup_db(tmp_path, tag="patch")
    try:
        session_id = await _seed_session(factory)
        async with factory() as db:
            draft = await create_agent_draft(
                project_id=1,
                session_id=session_id,
                payload=AgentDraftCreateRequest(),
                db=db,
                current_user=user,
            )
            edited = await update_agent_draft(
                project_id=1,
                draft_id=draft.id,
                payload=AgentDraftPatchRequest(
                    expected_version=draft.version,
                    steps=[
                        {"action": "click", "params": {"resource_id": f"{PACKAGE}:id/search_button"}, "source_seq": 3}
                    ],
                    assertions=[{"type": "element_visible", "resource_id": f"{PACKAGE}:id/result_list"}],
                ),
                db=db,
                current_user=user,
            )
            assert edited.id != draft.id
            assert edited.version == draft.version + 1
            assert edited.status == "pending_replay"
            assert edited.content_hash != draft.content_hash
            assert len(edited.steps) == 1

            # 旧版本号重复提交（版本冲突）返回 409
            with pytest.raises(HTTPException) as exc_info:
                await update_agent_draft(
                    project_id=1,
                    draft_id=draft.id,
                    payload=AgentDraftPatchRequest(
                        expected_version=draft.version,
                        steps=[{"action": "click", "params": {"resource_id": "x"}, "source_seq": 3}],
                    ),
                    db=db,
                    current_user=user,
                )
            assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    finally:
        await engine.dispose()


# ---------------- A32 独立回放 ----------------


@pytest.mark.asyncio
async def test_api_replay_preview_requires_confirmed_initial_state(tmp_path: Path):
    engine, factory, user = await _setup_db(tmp_path, tag="preview")
    try:
        session_id = await _seed_session(factory)
        async with factory() as db:
            draft = await create_agent_draft(
                project_id=1,
                session_id=session_id,
                payload=AgentDraftCreateRequest(),
                db=db,
                current_user=user,
            )
            preview = await preview_agent_draft_replay(project_id=1, draft_id=draft.id, db=db, current_user=user)
            assert preview.draft_id == draft.id
            assert preview.content_hash == draft.content_hash
            assert preview.frozen_snapshot["package_name"] == PACKAGE
            codes = {item.code for item in preview.items}
            assert "CASE_MODULE_BINDING" in codes
            assert "DEVICE_BOUND" in codes
            assert all(item.status != "fail" for item in preview.items)
            assert preview.ready is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_replay_is_idempotent_per_version(tmp_path: Path):
    engine, factory, user = await _setup_db(tmp_path, tag="replay")
    try:
        session_id = await _seed_session(factory)
        async with factory() as db:
            draft = await create_agent_draft(
                project_id=1,
                session_id=session_id,
                payload=AgentDraftCreateRequest(),
                db=db,
                current_user=user,
            )
            handoff = await start_agent_draft_replay(
                project_id=1,
                draft_id=draft.id,
                payload=AgentReplayStartRequest(initial_state_confirmed=True, module_id=1, idempotency_key="replay-1"),
                db=db,
                current_user=user,
            )
            assert handoff.replay.status == "queued"
            assert handoff.case_id > 0

            # 同幂等键重复请求返回同一回放，不重复发起
            again = await start_agent_draft_replay(
                project_id=1,
                draft_id=draft.id,
                payload=AgentReplayStartRequest(initial_state_confirmed=True, module_id=1, idempotency_key="replay-1"),
                db=db,
                current_user=user,
            )
            assert again.replay.id == handoff.replay.id

            # 未确认初始状态必须拒绝
            with pytest.raises(HTTPException) as exc_info:
                await start_agent_draft_replay(
                    project_id=1,
                    draft_id=draft.id,
                    payload=AgentReplayStartRequest(
                        initial_state_confirmed=False, module_id=1, idempotency_key="replay-2"
                    ),
                    db=db,
                    current_user=user,
                )
            assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

            fetched = await get_agent_replay(project_id=1, replay_id=handoff.replay.id, db=db, current_user=user)
            assert fetched.case_id == handoff.case_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_replay_rejects_non_replayable_draft(tmp_path: Path):
    engine, factory, user = await _setup_db(tmp_path, tag="blocked")
    try:
        session_id = await _seed_session(factory, status_value="failed")
        async with factory() as db:
            draft = await create_agent_draft(
                project_id=1,
                session_id=session_id,
                payload=AgentDraftCreateRequest(),
                db=db,
                current_user=user,
            )
            assert draft.status == "blocked"
            with pytest.raises(HTTPException) as exc_info:
                await start_agent_draft_replay(
                    project_id=1,
                    draft_id=draft.id,
                    payload=AgentReplayStartRequest(initial_state_confirmed=True, module_id=1, idempotency_key="b-1"),
                    db=db,
                    current_user=user,
                )
            assert exc_info.value.status_code == status.HTTP_409_CONFLICT
            assert "draft_not_replayable" in str(exc_info.value.detail)
    finally:
        await engine.dispose()


# ---------------- A33 幂等保存正式用例 ----------------


@pytest.mark.asyncio
async def test_api_publish_requires_verified_current_version(tmp_path: Path):
    engine, factory, user = await _setup_db(tmp_path, tag="publish")
    try:
        session_id = await _seed_session(factory)
        async with factory() as db:
            draft = await create_agent_draft(
                project_id=1,
                session_id=session_id,
                payload=AgentDraftCreateRequest(),
                db=db,
                current_user=user,
            )
            with pytest.raises(HTTPException) as exc_info:
                await publish_agent_draft(
                    project_id=1, draft_id=draft.id, idempotency_key="publish-1", db=db, current_user=user
                )
            assert exc_info.value.status_code == status.HTTP_409_CONFLICT

            # 先发起一次独立回放，拿到可用的用例与运行记录
            handoff = await start_agent_draft_replay(
                project_id=1,
                draft_id=draft.id,
                payload=AgentReplayStartRequest(initial_state_confirmed=True, module_id=1, idempotency_key="pub-1"),
                db=db,
                current_user=user,
            )

            draft_case_id = handoff.case_id
            draft_run_id = handoff.run_id

        async with factory() as verify_db:
            assert await verify_db.get(TestCase, draft_case_id) is not None
            assert await verify_db.get(TestRun, draft_run_id) is not None
            replay = AndroidAgentReplay(
                project_id=1,
                session_id=session_id,
                idempotency_key="seed-verify-1",
                draft_id=draft.id,
                draft_version=draft.version,
                content_hash=draft.content_hash,
                status="passed",
                module_id=1,
                case_id=draft_case_id,
                run_id=draft_run_id,
            )
            verify_db.add(replay)
            await verify_db.commit()

        async with factory() as db:
            published = await publish_agent_draft(
                project_id=1, draft_id=draft.id, idempotency_key="publish-1", db=db, current_user=user
            )
            assert published.published is True
            assert published.case_id == draft_case_id

            again = await publish_agent_draft(
                project_id=1, draft_id=draft.id, idempotency_key="publish-1", db=db, current_user=user
            )
            assert again.case_id == published.case_id
            assert again.idempotent_replay is True

            # 修改草稿后旧验证资格失效
            edited = await update_agent_draft(
                project_id=1,
                draft_id=draft.id,
                payload=AgentDraftPatchRequest(
                    expected_version=draft.version,
                    steps=[{"action": "click", "params": {"resource_id": f"{PACKAGE}:id/x"}, "source_seq": 3}],
                ),
                db=db,
                current_user=user,
            )
            with pytest.raises(HTTPException) as exc_info2:
                await publish_agent_draft(
                    project_id=1, draft_id=edited.id, idempotency_key="publish-2", db=db, current_user=user
                )
            assert exc_info2.value.status_code == status.HTTP_409_CONFLICT
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_draft_project_isolation(tmp_path: Path):
    engine, factory, user = await _setup_db(tmp_path, tag="isolation")
    try:
        session_id = await _seed_session(factory)
        async with factory() as db:
            draft = await create_agent_draft(
                project_id=1,
                session_id=session_id,
                payload=AgentDraftCreateRequest(),
                db=db,
                current_user=user,
            )
            with pytest.raises(HTTPException) as exc_info:
                await get_agent_draft(project_id=2, draft_id=draft.id, db=db, current_user=user)
            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_complete_endpoint_requires_structured_assertions(tmp_path: Path):
    """finish 只是建议：没有结构化终态断言时必须拒绝收敛。"""
    engine, factory, user = await _setup_db(tmp_path, tag="complete-guard")
    try:
        session_id = await _seed_session(factory, status_value="paused")
        async with factory() as db:
            with pytest.raises(HTTPException) as exc_info:
                await complete_agent_session(
                    payload=AgentCompleteRequest(terminal_assertion_confirmed=True, terminal_assertions=[]),
                    project_id=1,
                    session_id=session_id,
                    db=db,
                    current_user=user,
                )
            assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
            assert "terminal_assertions_required" in str(exc_info.value.detail)

            with pytest.raises(HTTPException) as exc_info2:
                await complete_agent_session(
                    payload=AgentCompleteRequest(
                        terminal_assertion_confirmed=False,
                        terminal_assertions=[{"type": "element_visible", "resource_id": "a:id/b"}],
                    ),
                    project_id=1,
                    session_id=session_id,
                    db=db,
                    current_user=user,
                )
            assert exc_info2.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_complete_endpoint_converges_paused_session(tmp_path: Path):
    """paused（needs_review）经用户确认后可收敛为 completed，并释放租约。"""
    engine, factory, user = await _setup_db(tmp_path, tag="complete-ok")
    try:
        session_id = await _seed_session(factory, status_value="paused")
        async with factory() as db:
            session = await db.get(AndroidAgentSession, session_id)
            session.lease_token = "lease-token-1"
            await db.commit()

            result = await complete_agent_session(
                payload=AgentCompleteRequest(
                    terminal_assertion_confirmed=True,
                    terminal_assertions=[{"type": "element_visible", "resource_id": "a:id/result"}],
                    summary="用户确认",
                ),
                project_id=1,
                session_id=session_id,
                db=db,
                current_user=user,
            )
            assert result.status == "completed"
            assert result.terminal_assertions == [{"type": "element_visible", "resource_id": "a:id/result"}]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_complete_endpoint_rejects_terminal_state(tmp_path: Path):
    engine, factory, user = await _setup_db(tmp_path, tag="complete-terminal")
    try:
        session_id = await _seed_session(factory, status_value="completed")
        async with factory() as db:
            with pytest.raises(HTTPException) as exc_info:
                await complete_agent_session(
                    payload=AgentCompleteRequest(
                        terminal_assertion_confirmed=True,
                        terminal_assertions=[{"type": "element_visible", "resource_id": "a:id/b"}],
                    ),
                    project_id=1,
                    session_id=session_id,
                    db=db,
                    current_user=user,
                )
            assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_api_publish_records_audit_log_once_across_idempotent_replay(tmp_path: Path):
    from sqlalchemy import select

    from app.models.audit import AuditLog
    from app.models.base import Base

    engine, factory, user = await _setup_db(tmp_path, tag="publish-audit")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[AuditLog.__table__]))

        session_id = await _seed_session(factory)
        async with factory() as db:
            draft = await create_agent_draft(
                project_id=1,
                session_id=session_id,
                payload=AgentDraftCreateRequest(),
                db=db,
                current_user=user,
            )
            handoff = await start_agent_draft_replay(
                project_id=1,
                draft_id=draft.id,
                payload=AgentReplayStartRequest(initial_state_confirmed=True, module_id=1, idempotency_key="pub-aud-1"),
                db=db,
                current_user=user,
            )

        async with factory() as verify_db:
            verify_db.add(
                AndroidAgentReplay(
                    project_id=1,
                    session_id=session_id,
                    idempotency_key="seed-verify-aud",
                    draft_id=draft.id,
                    draft_version=draft.version,
                    content_hash=draft.content_hash,
                    status="passed",
                    module_id=1,
                    case_id=handoff.case_id,
                    run_id=handoff.run_id,
                )
            )
            await verify_db.commit()

        async with factory() as db:
            published = await publish_agent_draft(
                project_id=1,
                draft_id=draft.id,
                idempotency_key="publish-aud-1",
                db=db,
                current_user=user,
            )
            assert published.published is True
            again = await publish_agent_draft(
                project_id=1,
                draft_id=draft.id,
                idempotency_key="publish-aud-1",
                db=db,
                current_user=user,
            )
            assert again.idempotent_replay is True

            logs = list(
                (await db.execute(select(AuditLog).where(AuditLog.action == "android_agent_draft_publish"))).scalars()
            )
            assert len(logs) == 1
            assert logs[0].resource_type == "android_agent_draft"
            assert logs[0].resource_id == draft.id
            assert logs[0].project_id == 1
            assert f"case_id={published.case_id}" in (logs[0].detail or "")
    finally:
        await engine.dispose()
