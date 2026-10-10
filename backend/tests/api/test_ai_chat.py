import asyncio
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import ai_chat
from app.api.v1.ai_chat import AiChatMessage, AiChatRequest
from app.models.user import User


class _Result:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def scalars(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None


class _DB:
    def __init__(self, llm_config=None, project=None):
        self.llm_config = llm_config
        self.project = project

    async def get(self, model, entity_id):
        if getattr(model, "__name__", "") == "Project" and self.project and entity_id == self.project.id:
            return self.project
        if getattr(model, "__name__", "") == "AILLMConfig" and self.llm_config and entity_id == self.llm_config.id:
            return self.llm_config
        return None

    async def execute(self, _statement):
        return _Result([self.llm_config] if self.llm_config else [])


def _user() -> User:
    return cast(User, SimpleNamespace(id=1, username="test_user", role="admin"))


def test_ai_chat_stream_yields_tokens(monkeypatch):
    config = SimpleNamespace(
        id=1,
        provider="openai",
        api_key_encrypted="enc",
        enabled=True,
        model_name="gpt-4o",
        endpoint=None,
        default_params={},
        daily_limit=1000,
        monthly_limit=50000,
    )
    db = cast(AsyncSession, _DB(llm_config=config))

    async def mock_stream_llm(_request):
        yield "你好"
        yield "！我是"
        yield " Hermes。"

    monkeypatch.setattr(ai_chat, "stream_llm", mock_stream_llm)
    monkeypatch.setattr(ai_chat, "decrypt", lambda _x: "secret")

    async def mock_limit(*_args, **_kwargs):
        return True

    monkeypatch.setattr(ai_chat, "check_and_incr_daily_limit", mock_limit)

    request = AiChatRequest(
        query="介绍你自己",
        history=[AiChatMessage(role="user", content="hello")],
    )

    async def run_test():
        response = await ai_chat.chat_stream(request, db, _user())
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        return "".join(chunks)

    body = asyncio.run(run_test())
    assert 'data: {"token": "你好"}' in body
    assert 'data: {"token": "！我是"}' in body
    assert 'data: {"token": " Hermes。"}' in body
    assert "data: [DONE]" in body


def test_ai_chat_stream_no_config_fallback():
    db = cast(AsyncSession, _DB(llm_config=None))
    request = AiChatRequest(query="介绍你自己")

    async def run_test():
        response = await ai_chat.chat_stream(request, db, _user())
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        return "".join(chunks)

    body = asyncio.run(run_test())
    assert "当前平台尚未配置可用的大语言模型" in body
    assert "data: [DONE]" in body


def test_ai_chat_rejects_unrelated_project_before_loading_model(monkeypatch):
    db = cast(AsyncSession, _DB())
    request = AiChatRequest(query="介绍你自己", project_id=77)
    checked = []

    async def deny_access(_db, _user, project_id, _role):
        checked.append(project_id)
        raise HTTPException(status_code=403, detail="No access to this project")

    async def should_not_load(_db, _project_id):
        raise AssertionError("model config must not be loaded before project access is checked")

    monkeypatch.setattr(ai_chat, "assert_project_access", deny_access)
    monkeypatch.setattr(ai_chat, "_resolve_active_llm", should_not_load)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(ai_chat.chat_stream(request, db, _user()))

    assert exc_info.value.status_code == 403
    assert checked == [77]
