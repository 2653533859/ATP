"""environments API 路由单元测试（Q13 补覆盖：此前 0%）。

直接调用路由函数：FakeDB 承载对象与脚本化查询结果，assert_project_access 与
加密边界按测试注入；schema 校验、密钥掩码、批量保存的删/插走真实现。
"""

import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


async def _noop_async(*_a, **_kw):
    return None


# conftest 的 app.api.deps stub 缺 assert_project_access；仅补缺失字段
_deps = sys.modules.setdefault("app.api.deps", types.SimpleNamespace())
for _name, _value in (
    ("get_current_user", lambda: None),
    ("require_engineer", lambda: None),
    ("require_admin", lambda: None),
    ("assert_project_access", _noop_async),
):
    if not hasattr(_deps, _name):
        setattr(_deps, _name, _value)

from fastapi import HTTPException  # noqa: E402

from app.api.v1 import environments as envs  # noqa: E402
from app.models.bootstrap import load_all_models  # noqa: E402

load_all_models()

from app.schemas.environment import (  # noqa: E402
    EnvironmentCreate,
    EnvironmentUpdate,
    EnvVariableBatchSave,
    EnvVariableItem,
)


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, objects=None, execute_rows=None):
        self.objects = dict(objects or {})
        self.execute_rows = list(execute_rows or [])
        self.added = []
        self.deleted = []
        self.executed = []
        self.commits = 0
        self._next_id = 500

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        return None

    async def execute(self, query):
        self.executed.append(query)
        rows = self.execute_rows.pop(0) if self.execute_rows else []
        return _FakeResult(rows)


@pytest.fixture()
def access(monkeypatch):
    calls = []

    async def assert_access(_db, _user, project_id, role):
        calls.append((project_id, role))

    monkeypatch.setattr(envs, "assert_project_access", assert_access)
    return calls


def _user():
    return _Obj(id=9)


def _env(env_id=1, project_id=5, name="staging"):
    return _Obj(id=env_id, project_id=project_id, name=name)


def _var(var_id, key, value, is_secret=False):
    return _Obj(id=var_id, key=key, value=value, is_secret=is_secret)


# ── list / create ───────────────────────────────────────────


def test_list_environments_checks_viewer_access(access):
    db = _FakeDB(execute_rows=[[_env()]])

    result = asyncio.run(envs.list_environments(project_id=5, db=db, user=_user()))

    assert [e.id for e in result] == [1]
    assert access == [(5, envs.ProjectRole.viewer)]


def test_create_environment_persists_and_checks_editor(access):
    db = _FakeDB()
    body = EnvironmentCreate(name="prod", project_id=5)

    env = asyncio.run(envs.create_environment(body=body, db=db, user=_user()))

    assert env.name == "prod" and env.project_id == 5
    assert access == [(5, envs.ProjectRole.editor)]
    assert db.commits == 1 and db.added == [env]


# ── update / delete ─────────────────────────────────────────


def test_update_environment_applies_non_none_fields(access):
    env = _env(name="old")
    db = _FakeDB({("Environment", 1): env})

    updated = asyncio.run(
        envs.update_environment(env_id=1, body=EnvironmentUpdate(name="new"), db=db, user=_user())
    )

    assert updated.name == "new"
    assert access == [(5, envs.ProjectRole.editor)]


def test_update_environment_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(envs.update_environment(env_id=404, body=EnvironmentUpdate(name="x"), db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404


def test_delete_environment_removes_and_checks_editor(access):
    env = _env()
    db = _FakeDB({("Environment", 1): env})

    asyncio.run(envs.delete_environment(env_id=1, db=db, user=_user()))

    assert db.deleted == [env] and db.commits == 1
    assert access == [(5, envs.ProjectRole.editor)]


def test_delete_environment_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(envs.delete_environment(env_id=404, db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404


# ── variables：掩码 + 批量保存加密 ──────────────────────────


def test_get_variables_masks_secrets(access):
    env = _env()
    db = _FakeDB(
        {("Environment", 1): env},
        execute_rows=[[_var(1, "HOST", "example.com"), _var(2, "TOKEN", "s3cr3t", is_secret=True)]],
    )

    out = asyncio.run(envs.get_variables(env_id=1, db=db, user=_user()))

    assert out[0].value == "example.com"  # 非密文原样
    assert out[1].value == "******"  # 密文掩码
    assert access == [(5, envs.ProjectRole.viewer)]


def test_get_variables_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(envs.get_variables(env_id=404, db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404


def test_save_variables_encrypts_secrets_and_replaces(monkeypatch, access):
    monkeypatch.setattr(envs, "encrypt", lambda value: f"enc({value})")
    env = _env()
    db = _FakeDB({("Environment", 1): env})
    body = EnvVariableBatchSave(
        variables=[
            EnvVariableItem(key="HOST", value="example.com", is_secret=False),
            EnvVariableItem(key="TOKEN", value="s3cr3t", is_secret=True),
        ]
    )

    out = asyncio.run(envs.save_variables(env_id=1, body=body, db=db, user=_user()))

    # 旧变量先被 bulk delete（execute 收到一条 delete 语句）
    assert len(db.executed) == 1
    # 明文变量原样落库；密文变量加密后落库
    stored = {v.key: v.value for v in db.added}
    assert stored["HOST"] == "example.com"
    assert stored["TOKEN"] == "enc(s3cr3t)"
    # 返回值对密文掩码
    returned = {v.key: v.value for v in out}
    assert returned["HOST"] == "example.com" and returned["TOKEN"] == "******"
    assert access == [(5, envs.ProjectRole.editor)]


def test_save_variables_404():
    body = EnvVariableBatchSave(variables=[])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(envs.save_variables(env_id=404, body=body, db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404


def test_batch_save_rejects_duplicate_keys():
    with pytest.raises(ValueError):
        EnvVariableBatchSave(
            variables=[EnvVariableItem(key="DUP", value="a"), EnvVariableItem(key="DUP", value="b")]
        )
