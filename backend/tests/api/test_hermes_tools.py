"""Hermes read-tool API permissions, timeout, and audit contract tests."""

import asyncio
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.api.v1 import hermes
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
