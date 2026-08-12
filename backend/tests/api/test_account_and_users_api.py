"""账号资料、管理员用户管理和成员用户搜索回归测试。"""

from __future__ import annotations

import asyncio
import types

import pytest
from fastapi import HTTPException, Response

from app.api.v1 import auth as auth_module
from app.api.v1 import users as users_module
from app.models.user import UserRole
from app.schemas.auth import UserAdminCreate, UserAdminUpdate, UserProfileUpdate


class _Result:
    def __init__(self, value=None, rows=None):
        self.value = value
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _DB:
    def __init__(self, execute_values=None, scalar_value=0):
        self.execute_values = list(execute_values or [])
        self.scalar_value = scalar_value
        self.object = None
        self.added = []
        self.commits = 0

    async def execute(self, _statement):
        return self.execute_values.pop(0) if self.execute_values else _Result()

    async def get(self, _model, _object_id):
        return self.object

    async def scalar(self, _statement):
        return self.scalar_value

    def add(self, value):
        value.id = 11
        self.added.append(value)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def refresh(self, _value):
        return None


def _request():
    return types.SimpleNamespace(headers={"x-requested-with": "XMLHttpRequest"})


def _user(**overrides):
    values = {
        "id": 1,
        "username": "admin",
        "email": "admin@example.com",
        "hashed_password": "old-hash",
        "role": UserRole.admin,
        "is_active": True,
    }
    values.update(overrides)
    return types.SimpleNamespace(**values)


def test_update_me_changes_profile_and_rotates_browser_session(monkeypatch):
    user = _user()
    db = _DB(execute_values=[_Result()])
    monkeypatch.setattr(
        auth_module, "verify_password", lambda plain, hashed: plain == "current" and hashed == "old-hash"
    )
    monkeypatch.setattr(auth_module, "hash_password", lambda _value: "new-hash")
    monkeypatch.setattr(auth_module, "write_audit_log", _noop_audit)

    result = asyncio.run(
        auth_module.update_me(
            _request(),
            Response(),
            UserProfileUpdate(
                current_password="current",
                username="new-admin",
                email="new-admin@example.com",
                new_password="new-password",
            ),
            user,
            db,
        )
    )

    assert result.authenticated is True
    assert user.username == "new-admin"
    assert user.email == "new-admin@example.com"
    assert user.hashed_password == "new-hash"
    assert db.commits == 1


async def _noop_audit(*_args, **_kwargs):
    return None


def test_update_me_rejects_wrong_current_password(monkeypatch):
    monkeypatch.setattr(auth_module, "verify_password", lambda *_args: False)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            auth_module.update_me(
                _request(),
                Response(),
                UserProfileUpdate(current_password="wrong", email="new@example.com"),
                _user(),
                _DB(),
            )
        )

    assert exc_info.value.status_code == 400


def test_admin_can_create_user(monkeypatch):
    db = _DB(execute_values=[_Result()])
    monkeypatch.setattr(users_module, "hash_password", lambda _value: "hashed")
    monkeypatch.setattr(users_module, "write_audit_log", _noop_audit)

    result = asyncio.run(
        users_module.create_user(
            UserAdminCreate(
                username="tester",
                email="tester@example.com",
                password="password123",
                role="tester",
            ),
            db,
            _user(),
        )
    )

    assert result.username == "tester"
    assert db.added[0].hashed_password == "hashed"
    assert db.commits == 1


def test_admin_cannot_disable_last_admin(monkeypatch):
    target = _user(id=2, username="only-admin")
    db = _DB(execute_values=[_Result()], scalar_value=0)
    db.object = target

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            users_module.update_user(
                target.id,
                UserAdminUpdate(is_active=False),
                db,
                _user(),
            )
        )

    assert exc_info.value.status_code == 400
    assert target.is_active is True


def test_lookup_returns_active_users(monkeypatch):
    expected = [_user(id=3, username="tester", role=UserRole.tester)]
    db = _DB(execute_values=[_Result(rows=expected)])

    result = asyncio.run(users_module.lookup_users("test", db, _user()))

    assert result == expected


def test_lookup_ignores_whitespace_only_keyword():
    result = asyncio.run(users_module.lookup_users("   ", _DB(), _user()))

    assert result == []


def test_list_users_supports_filtered_and_unfiltered_queries():
    expected = [_user(id=3, username="tester", role=UserRole.tester)]
    filtered_db = _DB(execute_values=[_Result(rows=expected)])
    unfiltered_db = _DB(execute_values=[_Result(rows=expected)])

    assert asyncio.run(users_module.list_users(" test ", filtered_db, _user())) == expected
    assert asyncio.run(users_module.list_users(None, unfiltered_db, _user())) == expected


def test_create_user_rejects_invalid_role_and_duplicate_identity():
    with pytest.raises(HTTPException) as invalid:
        users_module._role("not-a-role")
    assert invalid.value.status_code == 422

    duplicate_db = _DB(execute_values=[_Result(value=_user(id=2, username="tester"))])
    with pytest.raises(HTTPException) as duplicate:
        asyncio.run(
            users_module.create_user(
                UserAdminCreate(
                    username="tester",
                    email="tester@example.com",
                    password="password123",
                    role="tester",
                ),
                duplicate_db,
                _user(),
            )
        )
    assert duplicate.value.status_code == 409


def test_update_user_reports_missing_user_and_preserves_another_admin(monkeypatch):
    missing_db = _DB()
    with pytest.raises(HTTPException) as missing:
        asyncio.run(users_module.update_user(99, UserAdminUpdate(is_active=False), missing_db, _user()))
    assert missing.value.status_code == 404

    target = _user(id=2, username="second-admin")
    db = _DB(execute_values=[_Result(), _Result()], scalar_value=1)
    db.object = target
    monkeypatch.setattr(users_module, "write_audit_log", _noop_audit)
    result = asyncio.run(users_module.update_user(target.id, UserAdminUpdate(is_active=False), db, _user()))

    assert result.is_active is False
