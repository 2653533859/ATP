"""账号资料、管理员用户管理和成员用户搜索回归测试。"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import types

import pytest
from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient

from app.api.v1 import auth as auth_module
from app.api.v1 import users as users_module
from app.models.user import UserRole
from app.schemas.auth import UserAdminCreate, UserAdminUpdate, UserProfileUpdate


def _load_real_deps_module():
    deps_path = Path(__file__).resolve().parents[2] / "app" / "api" / "deps.py"
    spec = importlib.util.spec_from_file_location("_real_api_deps_for_user_test", deps_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    def __init__(self, execute_values=None, scalar_value=0, scalar_values=None):
        self.execute_values = list(execute_values or [])
        self.scalar_value = scalar_value
        self.scalar_values = list(scalar_values) if scalar_values is not None else None
        self.object = None
        self.added = []
        self.deleted = []
        self.executed = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        self.executed.append(statement)
        return self.execute_values.pop(0) if self.execute_values else _Result()

    async def get(self, _model, _object_id):
        return self.object

    async def scalar(self, _statement):
        if self.scalar_values is not None:
            return self.scalar_values.pop(0) if self.scalar_values else 0
        return self.scalar_value

    def add(self, value):
        value.id = 11
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

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


def test_initial_password_is_admin_only_and_not_cached(monkeypatch):
    monkeypatch.setattr(users_module.settings, "DEFAULT_USER_INITIAL_PASSWORD", "example-password")
    app = FastAPI()
    app.include_router(users_module.router)
    app.dependency_overrides[users_module.get_db] = lambda: _DB()

    def reject_non_admin():
        raise HTTPException(status_code=403)

    app.dependency_overrides[users_module.require_admin] = reject_non_admin
    client = TestClient(app)
    assert client.get("/users/initial-password").status_code == 403

    app.dependency_overrides[users_module.require_admin] = lambda: _user(role=UserRole.admin)
    response = client.get("/users/initial-password")
    assert response.status_code == 200
    assert response.json() == {"password": "example-password"}
    assert response.headers["cache-control"] == "no-store"


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


def test_admin_cannot_self_disable_self_demote_or_rename_via_user_management(monkeypatch):
    current = _user(id=1, username="admin", role=UserRole.admin, is_active=True)
    for payload, expected_detail in [
        (UserAdminUpdate(is_active=False), "不能停用当前登录账号"),
        (UserAdminUpdate(role="engineer"), "不能降级当前登录管理员角色"),
        (UserAdminUpdate(username="renamed-admin"), "请前往「账号设置」修改当前登录账号的用户名"),
    ]:
        db = _DB()
        db.object = current
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(users_module.update_user(1, payload, db, current))
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == expected_detail


def test_delete_user_detaches_preferences_and_deletes_unreferenced_account(monkeypatch):
    target = _user(id=2, username="unused-tester", role=UserRole.tester, is_active=True)
    # 13 blocking asset count checks -> all 0
    db = _DB(scalar_values=[0] * 13)
    db.object = target
    audit_calls = []

    async def _capture_audit(*args, **kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(users_module, "write_audit_log", _capture_audit)
    asyncio.run(users_module.delete_user(2, db, _user(id=1)))

    assert db.deleted == [target]
    assert len(db.executed) == 6  # UserSetting delete + 5 nullable FK updates
    assert db.commits == 1
    assert audit_calls[0]["action"] == "delete_user"
    assert audit_calls[0]["resource_id"] == 2


def test_delete_user_rejects_self_last_admin_and_blocking_assets():
    with pytest.raises(HTTPException) as self_exc:
        asyncio.run(users_module.delete_user(1, _DB(), _user(id=1)))
    assert self_exc.value.status_code == 400
    assert self_exc.value.detail == "不能删除当前登录账号"

    last_admin_db = _DB(scalar_value=0)
    last_admin_db.object = _user(id=2, username="only-admin", role=UserRole.admin, is_active=True)
    with pytest.raises(HTTPException) as last_exc:
        asyncio.run(users_module.delete_user(2, last_admin_db, _user(id=1)))
    assert last_exc.value.status_code == 400

    # First blocking check (Project.owner_id) returns 2 projects
    blocking_db = _DB(scalar_values=[2] + [0] * 12)
    blocking_db.object = _user(id=3, username="legacy-eng", role=UserRole.engineer, is_active=True)
    with pytest.raises(HTTPException) as conflict_exc:
        asyncio.run(users_module.delete_user(3, blocking_db, _user(id=1)))
    assert conflict_exc.value.status_code == 409
    assert "项目 2 个" in conflict_exc.value.detail
    assert blocking_db.deleted == []


@pytest.mark.parametrize("role", [UserRole.engineer, UserRole.tester, UserRole.viewer])
def test_non_admin_cannot_manage_other_users(role):
    admin_routes = [route for route in users_module.router.routes if route.path != "/users/lookup"]
    assert len(admin_routes) == 6
    for route in admin_routes:
        calls = [dep.call for dep in route.dependant.dependencies]
        assert users_module.require_admin in calls

    real_deps = _load_real_deps_module()
    real_checker = real_deps.require_roles(UserRole.admin)

    async def _enforce_admin():
        return await real_checker(_user(id=10, username="member", role=role))

    app = FastAPI()
    app.include_router(users_module.router)
    app.dependency_overrides[users_module.get_db] = lambda: _DB()
    app.dependency_overrides[users_module.require_admin] = _enforce_admin
    client = TestClient(app)

    assert client.get("/users").status_code == 403
    assert client.get("/users/initial-password").status_code == 403
    assert client.put("/users/initial-password", json={"password": "password123"}).status_code == 403
    assert (
        client.post(
            "/users",
            json={
                "username": "someone",
                "email": "someone@example.com",
                "password": "password123",
                "role": "tester",
            },
        ).status_code
        == 403
    )
    assert client.patch("/users/2", json={"email": "hack@example.com"}).status_code == 403
    assert client.delete("/users/2").status_code == 403


def test_standard_user_can_only_update_own_profile_without_changing_role(monkeypatch):
    member = _user(id=5, username="tester", email="tester@example.com", role=UserRole.tester)
    db = _DB(execute_values=[_Result()])
    monkeypatch.setattr(
        auth_module, "verify_password", lambda plain, hashed: plain == "current" and hashed == "old-hash"
    )
    monkeypatch.setattr(auth_module, "hash_password", lambda _value: "new-hash")
    monkeypatch.setattr(auth_module, "write_audit_log", _noop_audit)

    payload = UserProfileUpdate(
        current_password="current",
        username="tester-renamed",
        email="tester-renamed@example.com",
        role="admin",
        is_active=False,
    )
    assert not hasattr(payload, "role")
    assert not hasattr(payload, "is_active")

    result = asyncio.run(auth_module.update_me(_request(), Response(), payload, member, db))
    assert result.authenticated is True
    assert member.username == "tester-renamed"
    assert member.role == UserRole.tester
    assert member.is_active is True
