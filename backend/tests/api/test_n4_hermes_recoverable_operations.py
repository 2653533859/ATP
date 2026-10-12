"""N4 Hermes 可恢复测试操作与命令闭环回归测试。

覆盖：
1. N4.1 多类操作面板（defect, knowledge, record, test_plan 等）持久草稿保存与读取；
2. N4.2 确认时版本冲突检查（expected_updated_at）与同一草稿重复确认幂等复用；
3. N4.3 扩展共用命令服务（update_case, create_defect, create_knowledge, run_case）与资源身份校验。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.bootstrap import load_all_models
from app.models.case import CaseStatus, CaseType, TestCase
from app.models.defect import Defect
from app.models.hermes import HermesSession
from app.models.hermes_action import HermesAction
from app.models.project import Module
from app.models.user import User
from app.schemas.hermes import HermesDraftConfirmIn, HermesDraftIn
from app.services.hermes_commands import command_resource

load_all_models()


# ==================== 1. N4.1 多类持久草稿创建与回读 ====================


@pytest.mark.asyncio
async def test_hermes_draft_creation_for_multiple_types(monkeypatch):
    """验证 Hermes 会话支持保存并回读不同类型的操作草稿（defect, knowledge, record 等）。"""
    from app.api.v1 import hermes

    now = datetime.now(timezone.utc)
    session = HermesSession(
        id=1,
        project_id=1,
        user_id=1,
        title="测试会话",
        messages=[],
        drafts=[],
        created_at=now,
        updated_at=now,
    )

    class FakeHermesDB:
        async def get(self, model, obj_id):
            return session if model is HermesSession and obj_id == 1 else None

        async def commit(self):
            pass

    user = User(id=1, username="tester", email="tester@example.com")
    monkeypatch.setattr(hermes, "assert_project_access", AsyncMock())

    # 1. 创建 defect 草稿
    defect_draft_in = HermesDraftIn(
        project_id=1,
        draft_type="defect",
        payload={"title": "登录偶现 500", "description": "超时排查", "run_id": 99},
    )
    draft_1 = await hermes.create_hermes_draft(1, defect_draft_in, FakeHermesDB(), user)
    assert draft_1["draft_type"] == "defect"
    assert draft_1["status"] == "pending_confirmation"

    # 2. 创建 knowledge 草稿
    knowledge_draft_in = HermesDraftIn(
        project_id=1,
        draft_type="knowledge",
        payload={"title": "连接池优化规范", "content": "参数建议", "source_type": "solution"},
    )
    draft_2 = await hermes.create_hermes_draft(1, knowledge_draft_in, FakeHermesDB(), user)
    assert draft_2["draft_type"] == "knowledge"

    # 验证会话中持久化了 2 个不同类型的草稿
    assert len(session.drafts) == 2


# ==================== 2. N4.2 确认时版本检查与重复确认幂等性 ====================


@pytest.mark.asyncio
async def test_hermes_draft_confirmation_idempotency_and_version_guard(monkeypatch):
    """验证同一草稿重复确认能幂等返回已有结果；验证用例并发编辑被 409 拦截。"""
    from app.api.v1 import hermes

    now = datetime.now(timezone.utc)
    case = TestCase(
        id=201,
        module_id=10,
        name="待更新用例",
        case_type=CaseType.web,
        status=CaseStatus.active,
        config={"steps": []},
    )
    case.updated_at = now

    draft_record = {
        "id": "draft-rec-1",
        "draft_type": "record",
        "status": "pending_confirmation",
        "payload": {
            "case_id": 201,
            "expected_updated_at": now.isoformat(),
            "config": {"steps": [{"action": "goto", "params": {"url": "https://example.com"}}]},
        },
    }

    session = HermesSession(
        id=2,
        project_id=1,
        user_id=1,
        title="录制修复会话",
        messages=[],
        drafts=[draft_record],
        created_at=now,
        updated_at=now,
    )

    class FakeConfirmDB:
        async def get(self, model, obj_id):
            if model is HermesSession and obj_id == 2:
                return session
            if model is TestCase and obj_id == 201:
                return case
            if model is Module and obj_id == 10:
                return Module(id=10, project_id=1)
            return None

        async def commit(self):
            pass

    user = User(id=1, username="tester", email="tester@example.com")
    monkeypatch.setattr(hermes, "assert_project_access", AsyncMock())

    confirm_in = HermesDraftConfirmIn(project_id=1, draft_id="draft-rec-1", confirmation="CONFIRM")

    # 1. 首次确认：成功更新用例并确认草稿
    res1 = await hermes.confirm_hermes_draft(2, confirm_in, FakeConfirmDB(), user)
    assert res1["status"] == "confirmed"
    assert res1["resource_id"] == 201
    assert case.config["steps"][0]["action"] == "goto"

    # 2. 重复确认（N4.2 幂等复用）：直接返回已有确认结果，不报错
    res2 = await hermes.confirm_hermes_draft(2, confirm_in, FakeConfirmDB(), user)
    assert res2["status"] == "confirmed"
    assert res2["resource_id"] == 201

    # 3. 并发版本检查拦截：如果期待时间与实际时间不符，抛出 409
    draft_conflict = {
        "id": "draft-conflict-1",
        "draft_type": "record",
        "status": "pending_confirmation",
        "payload": {
            "case_id": 201,
            "expected_updated_at": "2020-01-01T00:00:00",  # 旧版本时间戳
            "config": {},
        },
    }
    session.drafts.append(draft_conflict)
    confirm_conflict_in = HermesDraftConfirmIn(project_id=1, draft_id="draft-conflict-1", confirmation="CONFIRM")
    with pytest.raises(HTTPException) as exc_info:
        await hermes.confirm_hermes_draft(2, confirm_conflict_in, FakeConfirmDB(), user)
    assert exc_info.value.status_code == 409
    assert "其他操作修改" in exc_info.value.detail


# ==================== 3. N4.3 扩展共用命令服务与资源身份 ====================


@pytest.mark.asyncio
async def test_expanded_hermes_commands_lifecycle():
    """验证 command_resource 与 record_command 支持 update_case, create_defect 等动作。"""
    now = datetime.now(timezone.utc)
    defect = Defect(
        id=55,
        project_id=1,
        title="严重缺陷",
        status="open",
        created_at=now,
    )

    action = HermesAction(
        id=1,
        user_id=1,
        project_id=1,
        command_id="cmd-defect-1",
        action="create_defect",
        request_hash="hash-123",
        resource_id=55,
        resource_identity="create_defect-55",
    )

    class FakeCmdDB:
        async def get(self, model, obj_id):
            if model is Defect and obj_id == 55:
                return defect
            return None

    # 1. 验证命令资源能被正确解析为 available
    res, state = await command_resource(FakeCmdDB(), action)
    assert state == "available"
    assert res is defect

    # 2. 验证跨项目时标记为 replaced
    action_cross = HermesAction(
        id=2,
        user_id=1,
        project_id=2,  # 项目不匹配
        command_id="cmd-defect-2",
        action="create_defect",
        request_hash="hash-123",
        resource_id=55,
        resource_identity="create_defect-55",
    )
    res_cross, state_cross = await command_resource(FakeCmdDB(), action_cross)
    assert state_cross == "replaced"
    assert res_cross is None


@pytest.mark.asyncio
async def test_hermes_action_records_resolves_all_actions_and_paths(monkeypatch):
    """验证 list_hermes_action_records 为各类动作解析准确的路径与运行状态。"""
    from app.api.v1 import suites
    from app.models.case import TestRun, RunStatus

    now = datetime.now(timezone.utc)
    user = User(id=1, username="tester", email="tester@example.com")
    monkeypatch.setattr(suites, "assert_project_access", AsyncMock())

    test_run = TestRun(id=30, case_id=1, triggered_by=1, status=RunStatus.passed, created_at=now)

    action_defect = HermesAction(
        id=1,
        user_id=1,
        project_id=1,
        command_id="c1",
        action="create_defect",
        request_hash="h1",
        resource_id=10,
        resource_identity="create_defect-10",
    )
    action_knowledge = HermesAction(
        id=2,
        user_id=1,
        project_id=1,
        command_id="c2",
        action="create_knowledge",
        request_hash="h2",
        resource_id=20,
        resource_identity="create_knowledge-20",
    )
    action_run = HermesAction(
        id=3,
        user_id=1,
        project_id=1,
        command_id="c3",
        action="run_case",
        request_hash="h3",
        resource_id=30,
        resource_identity="run_case-30",
    )
    action_case = HermesAction(
        id=4,
        user_id=1,
        project_id=1,
        command_id="c4",
        action="update_case",
        request_hash="h4",
        resource_id=40,
        resource_identity="update_case-40",
    )

    records = [action_defect, action_knowledge, action_run, action_case]

    class FakeListDB:
        async def scalars(self, _stmt):
            res = MagicMock()
            res.all.return_value = records
            return res

        async def get(self, model, obj_id):
            if model is TestRun and obj_id == 30:
                return test_run
            return MagicMock(id=obj_id, project_id=1)

    res = await suites.list_hermes_action_records(project_id=1, db=FakeListDB(), user=user)
    assert len(res) == 4

    item_defect = next(r for r in res if r["action"] == "create_defect")
    assert item_defect["path"] == "/bugs?project_id=1"

    item_knowledge = next(r for r in res if r["action"] == "create_knowledge")
    assert item_knowledge["path"] == "/knowledge?project_id=1"

    item_run = next(r for r in res if r["action"] == "run_case")
    assert item_run["path"] == "/runs/30"
    assert item_run["run_status"] == RunStatus.passed

    item_case = next(r for r in res if r["action"] == "update_case")
    assert item_case["path"] == "/cases/40"
