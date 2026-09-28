"""Behavioral contracts for project-scoped knowledge search and redaction."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import knowledge
from app.models.bootstrap import load_all_models
from app.models.knowledge import KnowledgeEntry
from app.models.user import UserRole
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate
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


def test_structured_knowledge_value_redacts_nested_secret_fields():
    value = {
        "request": {"api_key": "private-key", "headers": [{"Authorization": "Bearer private"}]},
        "status": "failed",
    }

    redacted = knowledge.redact_knowledge_value(value)

    assert "private-key" not in redacted
    assert "Bearer private" not in redacted
    assert '"status": "failed"' in redacted


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


class _SearchResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def scalar_one_or_none(self):
        return self.rows[0] if self.rows else None


class _KnowledgeDB(_DB):
    def __init__(self, *, entry=None, results=None):
        super().__init__()
        self.entry = entry
        self.results = list(results or [])
        self.deleted = []

    async def get(self, _model, _key):
        return self.entry

    async def execute(self, _statement):
        return _SearchResult(self.results.pop(0) if self.results else [])

    async def delete(self, entry):
        self.deleted.append(entry)


def _entry(project_id=1):
    now = datetime(2026, 9, 28, tzinfo=timezone.utc)
    entry = KnowledgeEntry(
        id=12,
        project_id=project_id,
        source_type="runbook",
        title="登录故障手册",
        summary="排查登录失败",
        content="检查服务状态",
        tags=["登录"],
        status="published",
        author_id=7,
        version=1,
    )
    entry.created_at = now
    entry.updated_at = now
    return entry


def test_search_knowledge_aggregates_all_source_types_without_leaking_secret(monkeypatch):
    async def no_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(knowledge, "assert_project_access", no_access)
    now = datetime(2026, 9, 28, tzinfo=timezone.utc)
    requirement = SimpleNamespace(
        id=2,
        project_id=1,
        requirement_code="REQ-2",
        title="登录",
        description="token=secret",
        acceptance_criteria=[],
        priority="P1",
        status="active",
        updated_at=now,
    )
    defect = SimpleNamespace(
        id=3,
        project_id=1,
        title="登录失败",
        description="接口异常",
        resolution="已修复",
        priority="P2",
        severity="major",
        labels=["登录"],
        status="open",
        updated_at=now,
    )
    run = SimpleNamespace(
        id=4,
        error_message="登录失败",
        result_summary={"token": "secret"},
        status="failed",
        trace_id=None,
        environment="dev",
        updated_at=now,
    )
    db = _KnowledgeDB(
        results=[[(_entry(), "ATP")], [(requirement, "ATP")], [(defect, "ATP")], [(run, "登录", 1, "ATP")]]
    )

    result = asyncio.run(
        knowledge.search_knowledge(
            project_id=1,
            keyword="登录",
            source_type=None,
            status_filter=None,
            page=1,
            page_size=10,
            db=db,
            user=_user(UserRole.admin.value),
        )
    )

    assert result.total == 4
    assert result.source_counts == {"runbook": 1, "requirement": 1, "defect": 1, "execution": 1}
    assert "secret" not in str(result.model_dump())


def test_knowledge_detail_update_and_delete_enforce_editability(monkeypatch):
    entry = _entry()
    access_roles = []
    audits = []

    async def access(_db, _user, _project_id, role):
        access_roles.append(role)

    async def audit(_db, **kwargs):
        audits.append(kwargs["action"])

    monkeypatch.setattr(knowledge, "assert_project_access", access)
    monkeypatch.setattr(knowledge, "write_audit_log", audit)
    db = _KnowledgeDB(entry=entry, results=[[1]])
    viewer = _user("viewer")

    detail = asyncio.run(knowledge.get_knowledge(knowledge_id=12, db=db, user=viewer))
    updated = asyncio.run(
        knowledge.update_knowledge(
            knowledge_id=12,
            body=KnowledgeUpdate(title="新手册", content="password: secret", tags=["登录", "登录"]),
            db=db,
            user=viewer,
        )
    )
    removed = asyncio.run(knowledge.delete_knowledge(knowledge_id=12, db=db, user=viewer))

    assert detail.is_editable
    assert updated.version == 2 and updated.title == "新手册"
    assert "secret" not in entry.content
    assert entry.tags == ["登录"]
    assert removed == {"deleted": True, "id": 12}
    assert db.deleted == [entry]
    assert access_roles == [knowledge.ProjectRole.viewer, knowledge.ProjectRole.editor, knowledge.ProjectRole.editor]
    assert audits == ["knowledge_update", "knowledge_delete"]


def test_knowledge_search_rejects_invalid_filters_before_database_access():
    for source_type, status_filter in (("unknown", None), (None, "hidden")):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                knowledge.search_knowledge(
                    project_id=None,
                    keyword=None,
                    source_type=source_type,
                    status_filter=status_filter,
                    page=1,
                    page_size=10,
                    db=_KnowledgeDB(),
                    user=_user(),
                )
            )
        assert exc.value.status_code == 422
