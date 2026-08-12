"""global_variables API 路由单元测试（Q13 补覆盖：此前 24%，路由函数零覆盖）。

聚焦加密变量库的安全编排：创建时先加密再落库、密钥掩码/揭示、全局作用域 admin 守卫、
key 唯一性、以及 created_by/updated_by 不可被请求体伪造。
FakeDB 承载对象与脚本化查询；assert_project_access / encrypt / decrypt 按测试注入。
"""

import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


async def _noop_async(*_a, **_kw):
    return None


_deps = sys.modules.setdefault("app.api.deps", types.SimpleNamespace())
for _name, _value in (
    ("get_current_user", lambda: None),
    ("require_engineer", lambda: None),
    ("require_admin", lambda: None),
    ("assert_project_access", _noop_async),
    ("assert_project_role", _noop_async),
):
    if not hasattr(_deps, _name):
        setattr(_deps, _name, _value)

from fastapi import HTTPException  # noqa: E402

from app.api.v1 import global_variables as gv  # noqa: E402
from app.models.bootstrap import load_all_models  # noqa: E402

load_all_models()

from app.models.global_variable import ScopeType  # noqa: E402
from app.models.user import UserRole  # noqa: E402
from app.models.user_project import ProjectRole  # noqa: E402
from app.schemas.global_variable import GlobalVariableCreate, GlobalVariableUpdate  # noqa: E402


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def scalars(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, objects=None, execute_results=None):
        self.objects = dict(objects or {})
        self.execute_results = list(execute_results or [])
        self.added = []
        self.deleted = []
        self.commits = 0

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = 700
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def execute(self, _query):
        return self.execute_results.pop(0) if self.execute_results else _FakeResult()

    async def refresh(self, obj):
        now = _now()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def _now():
    return datetime(2026, 7, 11, 9, 0, tzinfo=timezone.utc)


def _fake_decrypt(value):
    # enc(...) 包装可解；其它值模拟解密失败（覆盖 _serialize_variable 回退分支）
    if isinstance(value, str) and value.startswith("enc(") and value.endswith(")"):
        return value[4:-1]
    raise ValueError("not encrypted")


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    access_calls = []

    async def record_access(_db, _user, project_id, role):
        access_calls.append((project_id, role))

    monkeypatch.setattr(gv, "assert_project_access", record_access)
    monkeypatch.setattr(gv, "assert_project_role", record_access)
    monkeypatch.setattr(gv, "encrypt", lambda v: f"enc({v})")
    monkeypatch.setattr(gv, "decrypt", _fake_decrypt)
    return {"access": access_calls}


def _user(uid=9, role=UserRole.engineer):
    return _Obj(id=uid, role=role, username="amy")


def _var(vid=1, project_id=None, is_secret=True, value="enc(top-secret-token)"):
    return _Obj(
        id=vid,
        scope_type=ScopeType.project if project_id else ScopeType.global_scope,
        project_id=project_id,
        key="TOKEN",
        value_encrypted=value,
        is_secret=is_secret,
        description=None,
        created_at=_now(),
        updated_at=_now(),
    )


# ── 掩码与序列化边界 ────────────────────────────────────────


def test_mask_value_short_values_pass_through():
    assert gv._mask_value("abcdef", True) == "ab**ef"
    assert gv._mask_value("abcd", True) == "****"
    assert gv._mask_value("plain", False) == "plain"


def test_serialize_falls_back_to_raw_value_when_decrypt_fails():
    # 历史明文数据（无 enc 包装）→ 解密抛错 → 按原值返回
    out = gv._serialize_variable(_var(is_secret=False, value="legacy-raw"))
    assert out.value == "legacy-raw"


# ── list：项目访问检查 + 掩码 ───────────────────────────────


def test_list_variables_masks_secrets_and_checks_project_access(stubs):
    db = _FakeDB(execute_results=[_FakeResult(rows=[_var(project_id=5)])])

    out = asyncio.run(gv.list_variables(project_id=5, scope_type=None, db=db, user=_user()))

    assert stubs["access"] == [(5, ProjectRole.viewer)]
    assert out[0].value != "top-secret-token" and out[0].value.startswith("to")


def test_list_variables_global_scope_skips_access_check(stubs):
    db = _FakeDB(execute_results=[_FakeResult(rows=[_var(is_secret=False)])])
    out = asyncio.run(gv.list_variables(project_id=None, scope_type=ScopeType.global_scope, db=db, user=_user()))
    assert stubs["access"] == [] and out[0].value == "top-secret-token"


# ── create：加密落库 + 作用域守卫 + 唯一性 + 伪造防护 ───────


def test_create_project_variable_encrypts_before_store_and_masks_response(stubs):
    db = _FakeDB(execute_results=[_FakeResult(rows=[])])
    body = GlobalVariableCreate(
        scope_type=ScopeType.project, project_id=5, key="DB_PWD", value_encrypted="plain-secret", is_secret=True
    )

    out = asyncio.run(gv.create_variable(body=body, db=db, current_user=_user(uid=9)))

    created = db.added[0]
    assert created.value_encrypted == "enc(plain-secret)"  # 落库前加密
    assert out.value != "plain-secret"  # 响应掩码
    assert stubs["access"] == [(5, ProjectRole.editor)]


def test_create_ignores_client_supplied_created_by():
    # 请求体伪造 created_by=999 → 以当前用户为准
    db = _FakeDB(execute_results=[_FakeResult(rows=[])])
    body = GlobalVariableCreate(
        scope_type=ScopeType.project, project_id=5, key="K", value_encrypted="v", created_by=999
    )

    asyncio.run(gv.create_variable(body=body, db=db, current_user=_user(uid=9)))

    assert db.added[0].created_by == 9


def test_create_global_scope_requires_admin():
    body = GlobalVariableCreate(scope_type=ScopeType.global_scope, key="K", value_encrypted="v")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(gv.create_variable(body=body, db=_FakeDB(), current_user=_user(role=UserRole.engineer)))
    assert exc.value.status_code == 403 and "管理员" in exc.value.detail

    # admin 可建
    db = _FakeDB(execute_results=[_FakeResult(rows=[])])
    out = asyncio.run(gv.create_variable(body=body, db=db, current_user=_user(role=UserRole.admin)))
    assert out.key == "K"


def test_create_rejects_duplicate_key():
    db = _FakeDB(execute_results=[_FakeResult(rows=[_var()])])
    body = GlobalVariableCreate(scope_type=ScopeType.project, project_id=5, key="TOKEN", value_encrypted="v")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(gv.create_variable(body=body, db=db, current_user=_user()))
    assert exc.value.status_code == 400 and "already exists" in exc.value.detail


# ── get：404 / 掩码与揭示 / 项目访问 ────────────────────────


def test_get_variable_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(gv.get_variable(var_id=404, reveal_secret=False, db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404


def test_get_variable_masks_by_default_and_reveals_on_request(stubs):
    db = _FakeDB({("GlobalVariable", 1): _var(project_id=5)})

    masked = asyncio.run(gv.get_variable(var_id=1, reveal_secret=False, db=db, user=_user()))
    revealed = asyncio.run(gv.get_variable(var_id=1, reveal_secret=True, db=db, user=_user()))

    assert masked.value != "top-secret-token"
    assert revealed.value == "top-secret-token"
    assert stubs["access"] == [
        (5, ProjectRole.viewer),
        (5, ProjectRole.viewer),
        (5, ProjectRole.editor),
    ]


def test_get_global_secret_reveal_requires_admin():
    db = _FakeDB({("GlobalVariable", 1): _var()})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(gv.get_variable(var_id=1, reveal_secret=True, db=db, user=_user()))

    assert exc.value.status_code == 403


# ── update：重加密 / 伪造防护 / 404 ─────────────────────────


def test_update_variable_reencrypts_new_value_and_stamps_updater(stubs):
    var = _var(project_id=5)
    db = _FakeDB({("GlobalVariable", 1): var})
    body = GlobalVariableUpdate(value_encrypted="new-secret", updated_by=777)  # 伪造 updated_by

    asyncio.run(gv.update_variable(var_id=1, body=body, db=db, current_user=_user(uid=9)))

    assert var.value_encrypted == "enc(new-secret)"
    assert var.updated_by == 9  # 以当前用户为准，覆盖请求体伪造值
    assert stubs["access"] == [(5, ProjectRole.editor)]


def test_update_without_value_keeps_ciphertext():
    var = _var()
    db = _FakeDB({("GlobalVariable", 1): var})

    asyncio.run(
        gv.update_variable(
            var_id=1,
            body=GlobalVariableUpdate(description="备注"),
            db=db,
            current_user=_user(role=UserRole.admin),
        )
    )

    assert var.value_encrypted == "enc(top-secret-token)"  # 未动 value → 密文不变
    assert var.description == "备注"


def test_update_variable_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            gv.update_variable(var_id=404, body=GlobalVariableUpdate(key="X"), db=_FakeDB(), current_user=_user())
        )
    assert exc.value.status_code == 404


# ── delete ──────────────────────────────────────────────────


def test_delete_variable_removes_with_access_check_and_404(stubs):
    var = _var(project_id=5)
    db = _FakeDB({("GlobalVariable", 1): var})

    asyncio.run(gv.delete_variable(var_id=1, db=db, user=_user()))

    assert db.deleted == [var] and stubs["access"] == [(5, ProjectRole.editor)]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(gv.delete_variable(var_id=404, db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404
