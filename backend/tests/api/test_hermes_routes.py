"""Behavioral contracts for project-scoped Hermes retrieval."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import hermes
from app.schemas.hermes import HermesQueryIn
from app.services.hermes import HermesCandidate, build_answer, rank_candidates
from app.models.user_project import ProjectRole


NOW = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def all(self):
        return self.rows


class _DB:
    def __init__(self, results=None, project=None):
        self.results = list(results or [])
        self.project = project
        self.statements = []

    async def get(self, model, entity_id):
        if getattr(model, "__name__", "") == "Project" and self.project and entity_id == self.project.id:
            return self.project
        return None

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0) if self.results else _Result()


def _user():
    return SimpleNamespace(id=7, username="engineer", role="engineer")


def test_query_schema_trims_and_limits_input():
    result = HermesQueryIn(project_id=1, query="  登录  ", limit=3)

    assert result.query == "登录"
    assert result.limit == 3

    with pytest.raises(ValueError):
        HermesQueryIn(project_id=1, query="   ")


def test_rank_candidates_redacts_source_text_and_is_stable():
    sources = rank_candidates(
        "登录",
        [
            HermesCandidate(
                source_type="knowledge",
                source_id=2,
                project_id=1,
                title="登录排查手册",
                body="password: plain-secret；先检查认证服务",
                source_ref="SOP-LOGIN",
                path="/knowledge?project_id=1&knowledge_id=2",
                updated_at=NOW,
            ),
            HermesCandidate(
                source_type="requirement",
                source_id=3,
                project_id=1,
                title="邮箱登录需求",
                body="用户使用邮箱登录",
                source_ref="REQ-001-00003",
                path="/requirements?project_id=1&requirement_id=3",
                updated_at=NOW,
            ),
        ],
        8,
    )

    assert [item.source_type for item in sources] == ["knowledge", "requirement"]
    assert "plain-secret" not in sources[0].excerpt
    assert sources[0].match_terms
    answer, mode = build_answer(sources)
    assert mode == "project_retrieval"
    assert "SOP-LOGIN" in answer
    assert "plain-secret" not in answer


def test_query_hermes_returns_project_sources_and_citations(monkeypatch):
    access = []

    async def allow_access(_db, _user, project_id, role):
        access.append((project_id, role))

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)
    project = SimpleNamespace(id=1, name="核心项目")
    knowledge_entry = SimpleNamespace(
        id=2,
        project_id=1,
        title="登录排查手册",
        summary="认证服务排查",
        content="先检查认证服务和 Redis",
        source_ref="SOP-LOGIN",
        tags=["登录"],
        updated_at=NOW,
        created_at=NOW,
    )
    requirement = SimpleNamespace(
        id=3,
        project_id=1,
        title="邮箱登录需求",
        description="用户使用邮箱登录",
        acceptance_criteria=[{"text": "登录成功进入首页"}],
        requirement_code="REQ-001-00003",
        priority="P1",
        status="draft",
        updated_at=NOW,
        created_at=NOW,
    )
    case = SimpleNamespace(
        id=4,
        name="登录接口成功",
        summary="校验登录成功响应",
        description=None,
        case_code="ATP-API-0004",
        tags=["登录"],
        case_type="api",
        priority="P1",
        case_level="core",
        updated_at=NOW,
        created_at=NOW,
    )
    module = SimpleNamespace(id=5, project_id=1, name="认证")
    db = _DB(
        results=[
            _Result([(knowledge_entry, "核心项目")]),
            _Result([(requirement, "核心项目")]),
            _Result([(case, module)]),
        ],
        project=project,
    )

    result = asyncio.run(hermes.query_hermes(HermesQueryIn(project_id=1, query="登录"), db, _user()))

    assert access == [(1, ProjectRole.viewer)]
    assert result.mode == "project_retrieval"
    assert result.sources
    assert {item.source_type for item in result.sources} == {"knowledge", "requirement", "case"}
    assert "SOP-LOGIN" in result.answer
    assert result.sources[0].path.startswith("/")


def test_query_hermes_returns_explicit_no_result_state(monkeypatch):
    async def allow_access(*_args):
        return None

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)
    db = _DB(results=[_Result(), _Result(), _Result()], project=SimpleNamespace(id=1, name="核心项目"))

    result = asyncio.run(hermes.query_hermes(HermesQueryIn(project_id=1, query="不存在的关键词"), db, _user()))

    assert result.mode == "no_results"
    assert result.sources == []
    assert "没有找到" in result.answer


def test_query_hermes_rejects_missing_project(monkeypatch):
    async def allow_access(*_args):
        return None

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(hermes.query_hermes(HermesQueryIn(project_id=99, query="登录"), _DB(), _user()))

    assert exc.value.status_code == 404
