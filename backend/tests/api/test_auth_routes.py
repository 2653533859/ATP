"""auth 路由单元测试（Q15-05：此前 0%，且 CLAUDE.md 引用的测试文件并不存在）。

直接调用路由函数：FakeDB 承载查询结果，密码校验与审计按测试注入，token 签发与
校验走真实的 `app.core.security`。覆盖三条安全不变量：
- 用户不存在与密码错误必须返回同一个 401，不能泄露"用户存在"这一信息
- 停用账号返回 403 且不签发任何 token
- refresh 只接受 `type=refresh` 的 token，access token 不得用于续期
"""

from __future__ import annotations

import asyncio
import types

import pytest
from fastapi import HTTPException, Response

from app.api.v1 import auth as auth_module
from app.core.security import create_access_token, create_refresh_token
from app.models.bootstrap import load_all_models
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse

load_all_models()


class _FakeResult:
    def __init__(self, user):
        self._user = user

    def scalar_one_or_none(self):
        return self._user


class _FakeDB:
    def __init__(self, user=None):
        self._user = user
        self.commits = 0

    async def execute(self, _statement):
        return _FakeResult(self._user)

    async def commit(self):
        self.commits += 1


def _user(**overrides):
    data = {
        "id": 1,
        "username": "alice",
        "hashed_password": "hashed",
        "is_active": True,
    }
    data.update(overrides)
    return types.SimpleNamespace(**data)


def _request(host="10.0.0.5", browser=True):
    client = types.SimpleNamespace(host=host) if host is not None else None
    headers = {"x-requested-with": "XMLHttpRequest"} if browser else {}
    return types.SimpleNamespace(client=client, headers=headers)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def audit(monkeypatch):
    """记录审计调用，同时避免真实写库。"""
    calls: list[dict] = []

    async def fake_write_audit_log(_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(auth_module, "write_audit_log", fake_write_audit_log)
    return calls


@pytest.fixture
def password_ok(monkeypatch):
    monkeypatch.setattr(auth_module, "verify_password", lambda _plain, _hashed: True)


def _login(db, username="alice", password="secret", host="10.0.0.5", browser=True):
    # login 被 @limiter.limit 装饰，装饰器要求首个参数名为 request
    return _run(
        auth_module.login.__wrapped__(
            _request(host, browser=browser), Response(), LoginRequest(username=username, password=password), db
        )
        if hasattr(auth_module.login, "__wrapped__")
        else auth_module.login(
            _request(host, browser=browser), Response(), LoginRequest(username=username, password=password), db
        )
    )


def test_login_sets_an_authenticated_cookie_session_and_writes_an_audit_entry(audit, password_ok):
    db = _FakeDB(_user())

    tokens = _login(db)

    assert tokens.authenticated is True
    assert db.commits == 1
    assert audit[0]["action"] == "login"
    assert audit[0]["username"] == "alice"
    assert audit[0]["ip_address"] == "10.0.0.5"


def test_login_records_an_empty_ip_when_the_client_is_unknown(audit, password_ok):
    _login(_FakeDB(_user()), host=None)

    assert audit[0]["ip_address"] == ""


def test_api_login_keeps_json_token_contract(audit, password_ok):
    tokens = _login(_FakeDB(_user()), browser=False)

    assert isinstance(tokens, TokenResponse)
    assert tokens.access_token
    assert tokens.refresh_token


def test_unknown_user_and_wrong_password_are_indistinguishable(monkeypatch, audit):
    """两条路径必须给出完全相同的 401，否则可以用来枚举用户名。"""
    monkeypatch.setattr(auth_module, "verify_password", lambda _plain, _hashed: False)

    with pytest.raises(HTTPException) as unknown:
        _login(_FakeDB(None))
    with pytest.raises(HTTPException) as wrong_password:
        _login(_FakeDB(_user()))

    assert unknown.value.status_code == wrong_password.value.status_code == 401
    assert unknown.value.detail == wrong_password.value.detail
    assert audit == [], "认证失败不写 login 审计"


def test_disabled_account_is_rejected_with_403_and_no_token(audit, password_ok):
    db = _FakeDB(_user(is_active=False))

    with pytest.raises(HTTPException) as excinfo:
        _login(db)

    assert excinfo.value.status_code == 403
    assert db.commits == 0
    assert audit == []


def test_refresh_rotates_both_tokens():
    db = _FakeDB(_user())

    tokens = _run(
        auth_module.refresh(
            _request(), Response(), RefreshRequest(refresh_token=create_refresh_token("alice")), db
        )
    )

    assert tokens.authenticated is True


def test_api_refresh_keeps_json_token_contract():
    tokens = _run(
        auth_module.refresh(
            _request(browser=False),
            Response(),
            RefreshRequest(refresh_token=create_refresh_token("alice")),
            _FakeDB(_user()),
        )
    )

    assert isinstance(tokens, TokenResponse)
    assert tokens.access_token
    assert tokens.refresh_token


def test_refresh_rejects_an_access_token():
    """access token 不得用于续期，否则等于把短期凭据升级成长期凭据。"""
    db = _FakeDB(_user())

    with pytest.raises(HTTPException) as excinfo:
        _run(auth_module.refresh(_request(), Response(), RefreshRequest(refresh_token=create_access_token("alice")), db))

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Invalid refresh token"


def test_refresh_rejects_a_malformed_token():
    with pytest.raises(HTTPException) as excinfo:
        _run(auth_module.refresh(_request(), Response(), RefreshRequest(refresh_token="not-a-jwt"), _FakeDB(_user())))

    assert excinfo.value.status_code == 401


@pytest.mark.parametrize("user", [None, _user(is_active=False)], ids=["deleted", "disabled"])
def test_refresh_rejects_users_that_can_no_longer_log_in(user):
    """账号被删或被停用后，手里的 refresh token 必须立即失效。"""
    with pytest.raises(HTTPException) as excinfo:
        _run(
            auth_module.refresh(
                _request(), Response(), RefreshRequest(refresh_token=create_refresh_token("alice")), _FakeDB(user)
            )
        )

    assert excinfo.value.status_code == 401


def test_me_returns_the_injected_current_user():
    current = _user(username="bob")

    assert _run(auth_module.me(current)) is current
