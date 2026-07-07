"""Tests for app.api.v1.ai_llm_configs."""

import asyncio
import inspect
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.api.conftest import fake_require_admin as _fake_require_admin
from tests.api.conftest import fake_require_engineer as _fake_require_engineer

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    require_admin=_fake_require_admin,
    require_engineer=_fake_require_engineer,
    get_current_user=lambda: None,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)

from app.models.bootstrap import load_all_models

load_all_models()

from app.api.v1 import ai_llm_configs
from app.core import encryption as encryption_module
from app.schemas.ai_llm_config import (
    AILLMConfigCreateIn,
    AILLMConfigUpdateIn,
)


class _AwaitableScalars:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _AsyncDB:
    def __init__(self):
        self.added: list[object] = []
        self.commit_calls = 0
        self.refresh_calls = 0
        self.delete_calls: list[object] = []
        self._get_value = None
        self._execute_rows: list[object] = []
        self.commit_raises: Exception | None = None
        self.rollback_calls = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        if self.commit_raises:
            exc = self.commit_raises
            self.commit_raises = None
            raise exc
        self.commit_calls += 1

    async def rollback(self):
        self.rollback_calls += 1

    async def refresh(self, obj):
        self.refresh_calls += 1
        # 模拟数据库回填自增 / server_default 列
        if getattr(obj, "id", None) is None:
            obj.id = 1
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = datetime.now(timezone.utc)

    async def execute(self, stmt):
        return _AwaitableScalars(self._execute_rows)

    async def get(self, model, pk):
        return self._get_value

    async def delete(self, obj):
        self.delete_calls.append(obj)


def _make_config_row(**overrides):
    base = dict(
        id=1,
        name="deepseek-prod",
        provider="deepseek",
        api_key_encrypted="enc-token",
        endpoint=None,
        model_name="deepseek-chat",
        default_params={"temperature": 0.4},
        enabled=True,
        supports_vision=False,
        description="测试配置",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


def test_endpoints_require_admin():
    for fn in (
        ai_llm_configs.list_llm_configs,
        ai_llm_configs.create_llm_config,
        ai_llm_configs.get_llm_config,
        ai_llm_configs.update_llm_config,
        ai_llm_configs.delete_llm_config,
    ):
        dep = inspect.signature(fn).parameters["_"].default.dependency
        assert dep is _fake_require_admin


def test_list_returns_safe_output(monkeypatch):
    db = _AsyncDB()
    db._execute_rows = [_make_config_row()]

    out = asyncio.run(ai_llm_configs.list_llm_configs(db=db, _=None))
    assert len(out) == 1
    item = out[0]
    assert item.name == "deepseek-prod"
    assert item.has_api_key is True
    assert item.supports_vision is False
    assert not hasattr(item, "api_key_encrypted")


def test_create_encrypts_api_key(monkeypatch):
    captured_plaintext = {}

    def fake_encrypt(value):
        captured_plaintext["v"] = value
        return f"enc::{value}"

    monkeypatch.setattr(ai_llm_configs, "encrypt", fake_encrypt)

    db = _AsyncDB()
    body = AILLMConfigCreateIn(
        name="dp",
        provider="deepseek",
        api_key="sk-xxx",
        model_name="deepseek-chat",
        supports_vision=True,
    )
    out = asyncio.run(ai_llm_configs.create_llm_config(body=body, db=db, _=None))

    assert captured_plaintext["v"] == "sk-xxx"
    assert db.added and db.added[0].api_key_encrypted == "enc::sk-xxx"
    assert db.added[0].supports_vision is True
    assert out.name == "dp"
    assert out.has_api_key is True


def test_create_duplicate_name_returns_409(monkeypatch):
    monkeypatch.setattr(ai_llm_configs, "encrypt", lambda v: "enc")
    db = _AsyncDB()
    db.commit_raises = ai_llm_configs.IntegrityError("dup", {}, Exception())  # type: ignore[arg-type]
    body = AILLMConfigCreateIn(
        name="dup",
        provider="openai",
        api_key="k",
        model_name="gpt-4o-mini",
    )
    try:
        asyncio.run(ai_llm_configs.create_llm_config(body=body, db=db, _=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
        assert db.rollback_calls == 1
    else:
        raise AssertionError("应抛 409")


def test_get_404_when_missing():
    db = _AsyncDB()
    db._get_value = None
    try:
        asyncio.run(ai_llm_configs.get_llm_config(config_id=99, db=db, _=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("应抛 404")


def test_update_re_encrypts_when_api_key_provided(monkeypatch):
    encrypted_value: list[str] = []

    def fake_encrypt(value):
        encrypted_value.append(value)
        return f"enc::{value}"

    monkeypatch.setattr(ai_llm_configs, "encrypt", fake_encrypt)

    existing = _make_config_row()
    db = _AsyncDB()
    db._get_value = existing
    body = AILLMConfigUpdateIn(api_key="new-key", description="updated", supports_vision=True)
    out = asyncio.run(ai_llm_configs.update_llm_config(config_id=1, body=body, db=db, _=None))

    assert encrypted_value == ["new-key"]
    assert existing.api_key_encrypted == "enc::new-key"
    assert existing.description == "updated"
    assert existing.supports_vision is True
    assert out.description == "updated"
    assert db.commit_calls == 2


def test_update_skips_api_key_when_absent(monkeypatch):
    monkeypatch.setattr(ai_llm_configs, "encrypt", lambda v: pytest.fail("should not encrypt"))
    existing = _make_config_row(api_key_encrypted="keep-me")
    db = _AsyncDB()
    db._get_value = existing
    body = AILLMConfigUpdateIn(description="new desc")
    asyncio.run(ai_llm_configs.update_llm_config(config_id=1, body=body, db=db, _=None))
    assert existing.api_key_encrypted == "keep-me"


def test_delete_removes_record():
    existing = _make_config_row()
    db = _AsyncDB()
    db._get_value = existing
    asyncio.run(ai_llm_configs.delete_llm_config(config_id=1, db=db, _=None))
    assert db.delete_calls == [existing]
    assert db.commit_calls == 1


def test_real_encrypt_roundtrip_for_smoke():
    """端到端确认 encrypt/decrypt 仍可解密我们存入的值。"""
    cipher = encryption_module.encrypt("hello-secret")
    assert cipher != "hello-secret"
    assert encryption_module.decrypt(cipher) == "hello-secret"
