"""Behavioral contracts for project-scoped knowledge search and redaction."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import knowledge
from app.models.bootstrap import load_all_models
from app.models.knowledge import KnowledgeEntry
from app.models.user import UserRole
from app.schemas.knowledge import KnowledgeCreate
from app.services.knowledge import make_excerpt, redact_knowledge_tags, redact_knowledge_text, score_text


load_all_models()


class _DB:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if isinstance(value, KnowledgeEntry) and value.id is None:
                value.id = 12

    async def commit(self):
        self.commits += 1

    async def scalar(self, _statement):
        return None


def _user(role: str = "engineer"):
    return SimpleNamespace(id=7, username="engineer", role=role)


def test_knowledge_text_redacts_credentials_and_url_secrets():
    value = "Authorization: Bearer abc123 https://example.test?token=secret-value"

    redacted = redact_knowledge_text(value)

    assert redacted is not None
    assert "abc123" not in redacted
    assert "secret-value" not in redacted
    assert "[已脱敏]" in redacted


def test_search_helpers_rank_title_and_keep_excerpt_bounded():
    score, terms = score_text("登录", "登录规范", "用户登录后进入首页", ["认证"])

    assert score > 0
    assert "登录" in terms
    assert len(make_excerpt("登录 " * 500, "登录", limit=80)) <= 82
    assert redact_knowledge_tags(["token=secret", "token=secret", "部署"]) == ["token=[已脱敏]", "部署"]


def test_non_admin_cannot_create_global_knowledge():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            knowledge.create_knowledge(
                body=KnowledgeCreate(title="全局规范", content="正文"),
                db=_DB(),
                user=_user(),
            )
        )

    assert exc.value.status_code == 403


def test_create_project_knowledge_sanitizes_before_persisting(monkeypatch):
    async def no_access(*_args, **_kwargs):
        return None

    async def no_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(knowledge, "assert_project_access", no_access)
    monkeypatch.setattr(knowledge, "write_audit_log", no_audit)
    db = _DB()

    result = asyncio.run(
        knowledge.create_knowledge(
            body=KnowledgeCreate(
                project_id=1,
                source_type="runbook",
                title="部署手册",
                content="password: plain-secret\n先检查服务状态",
                source_ref="https://example.test/runbook?token=abc",
                tags=["部署", "部署"],
            ),
            db=db,
            user=_user(),
        )
    )

    entry = db.added[0]
    assert result.document_id == 12
    assert entry.content == "password=[已脱敏]\n先检查服务状态"
    assert entry.source_ref == "https://example.test/runbook?token=[已脱敏]"
    assert entry.tags == ["部署"]
    assert db.commits == 1


def test_global_entry_can_be_read_by_authenticated_user():
    entry = KnowledgeEntry(id=4, title="测试规范", content="安全检查", source_type="standard", status="published")

    asyncio.run(knowledge._assert_entry_access(_DB(), _user("viewer"), entry, knowledge.ProjectRole.viewer))


def test_global_draft_is_not_visible_to_non_admin():
    entry = KnowledgeEntry(id=5, title="未发布规范", content="草稿", source_type="standard", status="draft")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(knowledge._assert_entry_access(_DB(), _user("viewer"), entry, knowledge.ProjectRole.viewer))

    assert exc.value.status_code == 404
