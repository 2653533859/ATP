"""Hermes 草稿确认必须受项目边界和可执行类型约束。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.v1 import hermes
from app.models.case import TestCase
from app.models.project import Module
from app.schemas.hermes import HermesDraftConfirmIn, HermesDraftIn


@pytest.mark.asyncio
async def test_record_draft_cannot_update_case_in_another_project(monkeypatch):
    now = datetime.now(timezone.utc)
    case = TestCase(id=201, module_id=10, config={"original": True})
    case.updated_at = now
    session = SimpleNamespace(
        drafts=[
            {
                "id": "record-1",
                "draft_type": "record",
                "status": "pending_confirmation",
                "payload": {"case_id": 201, "expected_updated_at": now.isoformat(), "config": {"changed": True}},
            }
        ]
    )

    class FakeDB:
        async def get(self, model, obj_id):
            if model is TestCase and obj_id == 201:
                return case
            if model is Module and obj_id == 10:
                return Module(id=10, project_id=2)
            return None

    commit = AsyncMock()
    monkeypatch.setattr(hermes, "assert_project_access", AsyncMock())
    monkeypatch.setattr(hermes, "_owned_session", AsyncMock(return_value=session))
    monkeypatch.setattr(hermes, "_commit_hermes_state", commit)

    with pytest.raises(HTTPException) as exc_info:
        await hermes.confirm_hermes_draft(
            1,
            HermesDraftConfirmIn(project_id=1, draft_id="record-1", confirmation="CONFIRM"),
            FakeDB(),
            SimpleNamespace(id=7),
        )

    assert exc_info.value.status_code == 404
    assert case.config == {"original": True}
    assert session.drafts[0]["status"] == "pending_confirmation"
    commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("draft_type", ["api", "regression", "android", "summary"])
async def test_unimplemented_draft_types_cannot_be_created_or_confirmed(monkeypatch, draft_type):
    session = SimpleNamespace(drafts=[])
    commit = AsyncMock()
    monkeypatch.setattr(hermes, "assert_project_access", AsyncMock())
    monkeypatch.setattr(hermes, "_owned_session", AsyncMock(return_value=session))
    monkeypatch.setattr(hermes, "_commit_hermes_state", commit)
    user = SimpleNamespace(id=7)

    with pytest.raises(HTTPException) as create_error:
        await hermes.create_hermes_draft(
            1, HermesDraftIn(project_id=1, draft_type=draft_type, payload={}), SimpleNamespace(), user
        )
    assert create_error.value.status_code == 422
    assert session.drafts == []

    session.drafts = [{"id": "old-draft", "draft_type": draft_type, "status": "pending_confirmation", "payload": {}}]
    with pytest.raises(HTTPException) as confirm_error:
        await hermes.confirm_hermes_draft(
            1,
            HermesDraftConfirmIn(project_id=1, draft_id="old-draft", confirmation="CONFIRM"),
            SimpleNamespace(),
            user,
        )
    assert confirm_error.value.status_code == 422
    assert session.drafts[0]["status"] == "pending_confirmation"
    commit.assert_not_awaited()
