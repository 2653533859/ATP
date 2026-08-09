"""项目级 API Cookie 会话的单元测试。"""

import asyncio
import json

import httpx

from app.services import api_session


def test_cookie_serialization_preserves_request_scope():
    cookies = httpx.Cookies()
    cookies.set("session", "sid-1", domain="api.example.com", path="/v1")

    serialized = api_session.serialize_cookies(cookies)
    restored = httpx.Cookies()
    api_session.apply_cookies(restored, serialized)

    assert serialized == [
        {
            "name": "session",
            "value": "sid-1",
            "domain": "api.example.com",
            "path": "/v1",
            "expires": None,
            "secure": False,
        }
    ]
    assert next(iter(restored.jar)).value == "sid-1"


def test_project_session_is_encrypted_and_saved_with_ttl(monkeypatch):
    class _FakeRedis:
        def __init__(self):
            self.value = None
            self.set_args = None

        async def get(self, _key):
            return self.value

        async def set(self, _key, value, ex):
            self.value = value
            self.set_args = {"ex": ex}

    redis = _FakeRedis()
    closed = []

    async def close(client):
        closed.append(client)

    monkeypatch.setattr(api_session, "get_async_redis", lambda: redis)
    monkeypatch.setattr(api_session, "close_async_redis", close)
    cookies = [{"name": "session", "value": "sid-1", "domain": "api.example.com", "path": "/"}]

    asyncio.run(api_session.save_project_api_session(1, cookies))
    restored = asyncio.run(api_session.load_project_api_session(1))

    assert restored == cookies
    assert redis.set_args == {"ex": api_session.API_SESSION_TTL_SECONDS}
    assert redis.value != json.dumps(cookies, ensure_ascii=False)
    assert closed == [redis, redis]
