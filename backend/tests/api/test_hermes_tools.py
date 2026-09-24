"""Hermes read-tool API permissions, timeout, and audit contract tests."""

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import MissingGreenlet
from starlette.requests import Request

from app.api.v1 import hermes
from app.schemas.hermes_orchestration import HermesOrchestrationIn
from app.schemas.hermes_tools import HermesToolCallIn, HermesToolEvidence
from app.services.hermes_tools import HermesToolExecution


class _DB:
    def __init__(self):
        self.rollback_count = 0
        self.commit_count = 0

    async def rollback(self):
        self.rollback_count += 1

    async def commit(self):
        self.commit_count += 1

    async def refresh(self, _item):
        return None


def _user():
    return SimpleNamespace(id=7, username="engineer", role="engineer")


def _request():
    return Request({"type": "http", "client": ("127.0.0.1", 4173)})


def test_list_hermes_tools_exposes_only_read_only_catalog():
    result = asyncio.run(hermes.list_hermes_tools(_user()))

    assert len(result.tools) == 5
    assert all(tool.read_only and tool.required_role == "viewer" for tool in result.tools)
    assert {tool.name for tool in result.tools} == {
        "failed_tasks",
        "run_detail",
        "quality_trend",
        "requirement_case_links",
        "knowledge_detail",
    }


def test_legacy_session_tool_endpoint_is_not_registered():
    paths = {route.path for route in hermes.router.routes}

    assert "/hermes/tools/execute" in paths
    assert "/hermes/sessions/{session_id}/tools/{tool_name}" not in paths


def test_execute_hermes_tool_checks_project_access_and_commits_safe_audit(monkeypatch):
    access_calls = []
    audit_calls = []

    async def allow_access(*args):
        access_calls.append(args)

    async def fake_execute(*_args):
        return HermesToolExecution(
            status="ok",
            data={"items": [{"name": "登录任务"}]},
            evidence=[
                HermesToolEvidence(
                    evidence_id="failed-task:case:9",
                    source_ref="HERMES-TASK-CASE-9",
                    title="登录任务",
                    excerpt="认证服务异常",
                    path="/runs/9?project_id=1",
                )
            ],
        )

    async def record_audit(_db, **kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)
    monkeypatch.setattr(hermes, "execute_read_tool", fake_execute)
    monkeypatch.setattr(hermes, "write_audit_log", record_audit)
    db = _DB()
    result = asyncio.run(
        hermes.execute_hermes_tool(
            HermesToolCallIn(
                project_id=1,
                conversation_id="hermes-session-1",
                tool="failed_tasks",
                arguments={"limit": 5},
            ),
            _request(),
            db,
            _user(),
        )
    )

    assert result.status == "ok"
    assert result.evidence[0].source_ref == "HERMES-TASK-CASE-9"
    assert access_calls and access_calls[0][3].value == "viewer"
    assert db.rollback_count == 1
    assert db.commit_count == 1
    assert audit_calls and audit_calls[0]["action"] == "hermes_read_tool"
    assert "limit" not in audit_calls[0]["detail"]


def test_execute_hermes_tool_returns_bounded_timeout_and_audits_it(monkeypatch):
    audit_calls = []

    async def allow_access(*_args):
        return None

    async def slow_execute(*_args):
        await asyncio.sleep(0.2)

    async def record_audit(_db, **kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)
    monkeypatch.setattr(hermes, "execute_read_tool", slow_execute)
    monkeypatch.setattr(hermes, "write_audit_log", record_audit)
    result = asyncio.run(
        hermes.execute_hermes_tool(
            HermesToolCallIn(
                project_id=1,
                conversation_id="hermes-session-1",
                tool="quality_trend",
                timeout_ms=100,
            ),
            _request(),
            _DB(),
            _user(),
        )
    )

    assert result.status == "timeout"
    assert result.message == "工具执行超时，请缩小查询范围后重试"
    assert audit_calls and "status=timeout" in audit_calls[0]["detail"]


class _ExpiringUser:
    def __init__(self):
        self.expired = False

    def _read(self, value):
        if self.expired:
            raise MissingGreenlet("expired user attribute requires async refresh")
        return value

    @property
    def id(self):
        return self._read(7)

    @property
    def username(self):
        return self._read("viewer")

    @property
    def role(self):
        return self._read("viewer")


class _ExpiringDB(_DB):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.refresh_count = 0
        self.added = []
        self.pending_audits = []
        self.saved_audits = []

    async def rollback(self):
        await super().rollback()
        self.pending_audits.clear()
        self.user.expired = True

    async def commit(self):
        await super().commit()
        self.saved_audits.extend(self.pending_audits)
        self.pending_audits.clear()

    async def refresh(self, item):
        assert item is self.user
        self.refresh_count += 1
        self.user.expired = False

    def add(self, item):
        item.id = 100
        self.added.append(item)

    async def flush(self):
        return None


@pytest.mark.parametrize(
    ("query", "expected_tools"),
    [
        ("查看近期质量趋势", ["quality_trend"]),
        ("查看近期失败任务和质量趋势", ["failed_tasks", "quality_trend"]),
    ],
)
def test_orchestration_refreshes_user_after_tool_audit_rollback(monkeypatch, query, expected_tools):
    user = _ExpiringUser()
    db = _ExpiringDB(user)
    access_checks = []

    async def check_access(_db, current_user, _project_id, _role):
        access_checks.append(current_user.role)

    async def execute_tool(_db, _user, _project_id, _tool, _arguments):
        return HermesToolExecution(status="ok", data={"count": 0, "items": []}, evidence=[])

    async def record_audit(_db, **kwargs):
        _db.pending_audits.append(kwargs)

    monkeypatch.setattr(hermes, "assert_project_access", check_access)
    monkeypatch.setattr(hermes, "execute_read_tool", execute_tool)
    monkeypatch.setattr(hermes, "write_audit_log", record_audit)

    result = asyncio.run(
        hermes.orchestrate_hermes(
            HermesOrchestrationIn(project_id=1, query=query, conversation_id="hermes-expired-user"),
            _request(),
            db,
            user,
        )
    )

    assert result.status == "matched"
    assert [step.tool for step in result.steps] == expected_tools
    assert db.rollback_count == len(expected_tools)
    assert db.refresh_count == len(expected_tools)
    assert db.commit_count == len(expected_tools) + 1
    assert [audit["action"] for audit in db.saved_audits] == ["hermes_read_tool"] * len(expected_tools)
    assert all(audit["user_id"] == 7 and audit["username"] == "viewer" for audit in db.saved_audits)
    assert len(access_checks) == len(expected_tools) + 1
    assert user.expired is False


def test_execute_tool_refreshes_user_when_audit_fails(monkeypatch):
    user = _ExpiringUser()
    db = _ExpiringDB(user)

    async def check_access(_db, current_user, _project_id, _role):
        assert current_user.role == "viewer"

    async def execute_tool(_db, _user, _project_id, _tool, _arguments):
        return HermesToolExecution(status="ok", data={"count": 0}, evidence=[])

    async def fail_audit(_db, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(hermes, "assert_project_access", check_access)
    monkeypatch.setattr(hermes, "execute_read_tool", execute_tool)
    monkeypatch.setattr(hermes, "write_audit_log", fail_audit)

    result = asyncio.run(
        hermes.execute_hermes_tool(
            HermesToolCallIn(
                project_id=1,
                conversation_id="hermes-audit-error",
                tool="failed_tasks",
            ),
            _request(),
            db,
            user,
        )
    )

    assert result.status == "ok"
    assert db.rollback_count == 2
    assert db.refresh_count == 1
    assert user.id == 7
    assert user.role == "viewer"
