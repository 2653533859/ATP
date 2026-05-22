import asyncio
import inspect
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _fake_get_current_user():
    return None


def _fake_require_engineer():
    return None


sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)

def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None

sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=_fake_get_current_user,
    require_engineer=_fake_require_engineer,
        require_admin=_p3c_noop,
        require_project_access=lambda *a, **kw: _p3c_noop,
        assert_project_access=_p3c_noop_async,
        ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
    )

from app.api.v1 import notifications
from app.models.notification import NotifyChannel


class _FakeNotificationConfig:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeProject:
    def __init__(self, project_id: int):
        self.id = project_id


class _FakeDB:
    def __init__(self, cfg=None, project=None):
        self._cfg = cfg
        self._project = project
        self.added = []

    async def get(self, model, _pk):
        model_name = getattr(model, "__name__", "")
        if model_name == "NotificationConfig":
            return self._cfg
        if model_name == "Project":
            return self._project
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        return None

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 101


def test_notification_read_endpoints_require_engineer_dependency():
    list_dep = inspect.signature(notifications.list_notifications).parameters["user"].default.dependency
    get_dep = inspect.signature(notifications.get_notification).parameters["user"].default.dependency

    assert list_dep is _fake_require_engineer
    assert get_dep is _fake_require_engineer


def test_notification_test_send_returns_404_for_missing_config():
    db = _FakeDB(cfg=None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(notifications.test_notification(cfg_id=99, db=db, user=None))

    assert exc.value.status_code == 404


def test_notification_test_send_dispatches_email(monkeypatch):
    called = {}

    async def fake_email(config, summary):
        called["channel"] = "email"
        called["config"] = config
        called["summary"] = summary

    sys.modules["app.services.notifier"] = types.SimpleNamespace(
        _send_email=fake_email,
        _send_wechat=None,
        _send_dingtalk=None,
    )

    cfg = _FakeNotificationConfig(
        id=3,
        project_id=1,
        channel=NotifyChannel.email,
        config={"recipients": ["qa@example.com"]},
    )
    db = _FakeDB(cfg=cfg)

    result = asyncio.run(notifications.test_notification(cfg_id=3, db=db, user=None))

    assert result["message"]
    assert called["channel"] == "email"
    assert called["config"] == {"recipients": ["qa@example.com"]}
    assert called["summary"]["title"]


def test_notification_test_send_converts_delivery_failure_to_http_500():
    async def fake_wechat(_config, _summary):
        raise RuntimeError("invalid webhook")

    sys.modules["app.services.notifier"] = types.SimpleNamespace(
        _send_email=None,
        _send_wechat=fake_wechat,
        _send_dingtalk=None,
    )

    cfg = _FakeNotificationConfig(
        id=8,
        project_id=1,
        channel=NotifyChannel.wechat,
        config={"webhook_url": "https://qy.example"},
    )
    db = _FakeDB(cfg=cfg)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(notifications.test_notification(cfg_id=8, db=db, user=None))

    assert exc.value.status_code == 500
    assert "invalid webhook" in str(exc.value.detail)


def test_create_notification_returns_404_for_missing_project():
    body = notifications.NotificationConfigCreate(
        name="Project Bot",
        project_id=7,
        channel=NotifyChannel.wechat,
        config={"webhook_url": "https://qy.example"},
        is_enabled=True,
    )
    db = _FakeDB(project=None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(notifications.create_notification(body=body, db=db, user=None))

    assert exc.value.status_code == 404


def test_update_notification_preserves_masked_sensitive_fields_without_double_encryption(monkeypatch):
    def fake_decrypt_config(config):
        assert config == {"webhook_url": "cipher-webhook", "secret": "cipher-secret", "keyword": "old"}
        return {"webhook_url": "https://qy.example/hook", "secret": "top-secret", "keyword": "old"}

    def fake_encrypt_config(config):
        result = dict(config)
        for key in ("webhook_url", "secret"):
            if key in result:
                result[key] = f"enc:{result[key]}"
        return result

    monkeypatch.setattr(notifications, "decrypt_config", fake_decrypt_config)
    monkeypatch.setattr(notifications, "encrypt_config", fake_encrypt_config)

    cfg = _FakeNotificationConfig(
        id=5,
        name="Ops Bot",
        project_id=2,
        channel=NotifyChannel.dingtalk,
        config={"webhook_url": "cipher-webhook", "secret": "cipher-secret", "keyword": "old"},
        is_enabled=True,
    )
    db = _FakeDB(cfg=cfg)
    body = notifications.NotificationConfigUpdate(
        config={"webhook_url": "******", "secret": "******", "keyword": "release"},
    )

    result = asyncio.run(notifications.update_notification(cfg_id=5, body=body, db=db, user=None))

    assert result.config["webhook_url"] == "enc:https://qy.example/hook"
    assert result.config["secret"] == "enc:top-secret"
    assert result.config["keyword"] == "release"
