"""项目级 API Cookie 会话的单元测试。"""

import asyncio
import json
from http.cookiejar import Cookie

import httpx

from app.services import api_session


def test_cookie_serialization_preserves_request_scope():
    cookies = httpx.Cookies()
    cookies.jar.set_cookie(
        Cookie(
            version=0,
            name="session",
            value="sid-1",
            port=None,
            port_specified=False,
            domain="api.example.com",
            domain_specified=True,
            domain_initial_dot=False,
            path="/v1",
            path_specified=True,
            secure=True,
            expires=1893456000,
            discard=False,
            comment=None,
            comment_url=None,
            rest={},
            rfc2109=False,
        )
    )

    serialized = api_session.serialize_cookies(cookies)
    restored = httpx.Cookies()
    api_session.apply_cookies(restored, serialized)

    assert serialized == [
        {
            "name": "session",
            "value": "sid-1",
            "domain": "api.example.com",
            "path": "/v1",
            "expires": 1893456000,
            "secure": True,
        }
    ]
    restored_cookie = next(iter(restored.jar))
    assert restored_cookie.value == "sid-1"
    assert restored_cookie.secure is True
    assert restored_cookie.expires == 1893456000


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

    asyncio.run(api_session.save_project_api_session(1, []))
    assert asyncio.run(api_session.load_project_api_session(1)) == []
    assert closed == [redis, redis, redis, redis]

    redis.value = "old-key-ciphertext"
    assert asyncio.run(api_session.load_project_api_session(1)) == []
    assert closed == [redis, redis, redis, redis, redis]
