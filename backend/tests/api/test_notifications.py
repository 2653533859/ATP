import asyncio
import inspect
import sys
import types
from datetime import datetime, timezone
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


async def _fake_persist_notification_delivery(*_a, **_kw):
    return None


def _fake_safe_exception_message(_error):
    return "redacted provider error"


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
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


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

    async def fake_send(channel, config, summary):
        called["channel"] = "email"
        called["config"] = config
        called["summary"] = summary

    sys.modules["app.services.notifier"] = types.SimpleNamespace(
        send_notification_channel=fake_send,
        persist_notification_delivery=_fake_persist_notification_delivery,
        _safe_exception_message=_fake_safe_exception_message,
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
    async def fake_send(_channel, _config, _summary):
        raise RuntimeError("invalid webhook with access_token=raw-secret")

    sys.modules["app.services.notifier"] = types.SimpleNamespace(
        send_notification_channel=fake_send,
        persist_notification_delivery=_fake_persist_notification_delivery,
        _safe_exception_message=_fake_safe_exception_message,
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
    assert "redacted provider error" in str(exc.value.detail)
    assert "raw-secret" not in str(exc.value.detail)


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


def test_create_notification_rejects_missing_delivery_target():
    body = notifications.NotificationConfigCreate(
        name="Empty Bot",
        project_id=1,
        channel=NotifyChannel.wechat,
        config={},
    )
    db = _FakeDB(project=_FakeProject(1))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(notifications.create_notification(body=body, db=db, user=None))

    assert exc.value.status_code == 422
    assert "webhook_url" in str(exc.value.detail)


def test_create_notification_rejects_unknown_routing_scope():
    body = notifications.NotificationConfigCreate(
        name="Broad Bot",
        project_id=1,
        channel=NotifyChannel.email,
        config={"recipients": ["qa@example.com"], "scope": "everything"},
    )
    db = _FakeDB(project=_FakeProject(1))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(notifications.create_notification(body=body, db=db, user=None))

    assert exc.value.status_code == 422
    assert "通知范围" in str(exc.value.detail)


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

    assert result["config"]["webhook_url"] == "******"
    assert result["config"]["secret"] == "******"
    assert result["config"]["keyword"] == "release"
    assert cfg.config["webhook_url"] == "enc:https://qy.example/hook"
    assert cfg.config["secret"] == "enc:top-secret"


# ── Q14-02 路由清扫：create/list/get/delete + 掩码 + 审计 ───

from app.models.bootstrap import load_all_models  # noqa: E402

load_all_models()

_NOW = datetime(2026, 7, 11, tzinfo=timezone.utc)


class _ListDB(_FakeDB):
    """execute 返回脚本化行，供 list_notifications 使用。"""

    def __init__(self, rows=None, **kw):
        super().__init__(**kw)
        self._rows = rows or []
        self.deleted = []

    async def execute(self, _stmt):
        rows = self._rows

        class _Scalars:
            def all(self):
                return rows

        class _Result:
            def scalars(self):
                return _Scalars()

        return _Result()

    async def delete(self, obj):
        self.deleted.append(obj)


class _DeliveryDB(_FakeDB):
    def __init__(self, rows):
        super().__init__()
        self._delivery_rows = rows

    async def execute(self, _stmt):
        class _Result:
            def all(inner_self):
                return self._delivery_rows

        return _Result()


@pytest.fixture()
def audit(monkeypatch):
    calls = []

    async def fake_audit(_db, **kw):
        calls.append(kw)

    monkeypatch.setattr(notifications, "write_audit_log", fake_audit)
    monkeypatch.setattr(notifications, "encrypt_config", lambda c: {k: f"enc:{v}" for k, v in c.items()})
    return calls


def test_create_notification_encrypts_and_audits(audit):
    body = notifications.NotificationConfigCreate(
        name="Ops Bot",
        project_id=1,
        channel=NotifyChannel.wechat,
        config={"webhook_url": "https://qy.example"},
        is_enabled=True,
    )
    db = _FakeDB(project=_FakeProject(1))

    result = asyncio.run(
        notifications.create_notification(body=body, db=db, user=types.SimpleNamespace(id=9, username="amy"))
    )

    assert result["config"] == {"webhook_url": "******"}
    assert db.added and db.added[0].config == {"webhook_url": "enc:https://qy.example"}
    assert audit[0]["action"] == "notification_config_create"


def test_list_notifications_masks_sensitive_config(monkeypatch):
    monkeypatch.setattr(notifications, "mask_config", lambda c: {k: "******" for k in c})
    cfg = _FakeNotificationConfig(
        id=1,
        name="n",
        project_id=5,
        channel=NotifyChannel.wechat,
        config={"webhook_url": "x"},
        is_enabled=True,
        created_at=_NOW,
        updated_at=_NOW,
    )
    db = _ListDB(rows=[cfg])

    out = asyncio.run(notifications.list_notifications(project_id=5, db=db, user=types.SimpleNamespace(id=9)))
    assert out[0]["config"] == {"webhook_url": "******"}

    # project_id=None 分支：不做访问校验，仍返回
    out2 = asyncio.run(notifications.list_notifications(project_id=None, db=db, user=types.SimpleNamespace(id=9)))
    assert len(out2) == 1


def test_list_notification_deliveries_returns_safe_status_and_deleted_name():
    delivery = types.SimpleNamespace(
        id=22,
        project_id=5,
        notification_config_id=None,
        channel=NotifyChannel.wechat,
        status="failed",
        attempts=2,
        summary={"title": "Nightly", "entity_type": "suite"},
        error_message="HTTP 429 token=old-secret\nforged-log-line",
        created_at=_NOW,
    )
    out = asyncio.run(
        notifications.list_notification_deliveries(
            project_id=5,
            config_id=None,
            delivery_status="failed",
            limit=20,
            db=_DeliveryDB([(delivery, None)]),
            user=types.SimpleNamespace(id=9),
        )
    )

    assert out[0].notification_name == "已删除通知"
    assert out[0].status == "failed"
    assert out[0].attempts == 2
    assert out[0].error_message == "HTTP 429 token=*** forged-log-line"


def test_get_notification_404_and_masked(monkeypatch):
    monkeypatch.setattr(notifications, "mask_config", lambda c: {k: "******" for k in c})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(notifications.get_notification(cfg_id=404, db=_FakeDB(cfg=None), user=types.SimpleNamespace(id=9)))
    assert exc.value.status_code == 404

    cfg = _FakeNotificationConfig(
        id=3,
        name="n",
        project_id=5,
        channel=NotifyChannel.wechat,
        config={"secret": "x"},
        is_enabled=True,
        created_at=_NOW,
        updated_at=_NOW,
    )
    out = asyncio.run(notifications.get_notification(cfg_id=3, db=_FakeDB(cfg=cfg), user=types.SimpleNamespace(id=9)))
    assert out["config"] == {"secret": "******"}


def test_update_notification_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            notifications.update_notification(
                cfg_id=404,
                body=notifications.NotificationConfigUpdate(name="x"),
                db=_FakeDB(cfg=None),
                user=types.SimpleNamespace(id=9),
            )
        )
    assert exc.value.status_code == 404


def test_update_notification_non_config_field_audits(audit):
    cfg = _FakeNotificationConfig(
        id=5,
        name="old",
        project_id=2,
        channel=NotifyChannel.dingtalk,
        config={},
        is_enabled=True,
    )
    db = _FakeDB(cfg=cfg)

    result = asyncio.run(
        notifications.update_notification(
            cfg_id=5,
            body=notifications.NotificationConfigUpdate(name="new", is_enabled=False),
            db=db,
            user=types.SimpleNamespace(id=9, username="amy"),
        )
    )
    assert result["name"] == "new" and result["is_enabled"] is False
    assert audit[0]["action"] == "notification_config_update"


def test_delete_notification_404_and_happy(audit):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            notifications.delete_notification(cfg_id=404, db=_FakeDB(cfg=None), user=types.SimpleNamespace(id=9))
        )
    assert exc.value.status_code == 404

    cfg = _FakeNotificationConfig(id=6, name="bye", project_id=2, channel=NotifyChannel.email, config={})
    db = _ListDB(cfg=cfg)
    asyncio.run(notifications.delete_notification(cfg_id=6, db=db, user=types.SimpleNamespace(id=9, username="amy")))
    assert db.deleted == [cfg]
    assert audit[0]["action"] == "notification_config_delete"


def test_test_notification_dingtalk_dispatch(monkeypatch):
    called = {}

    async def fake_send(_channel, config, summary):
        called["config"] = config

    monkeypatch.setattr(
        notifications,
        "decrypt_config",
        lambda c: {"webhook_url": "https://oapi.dingtalk.com/robot/send", "language": "en-US"},
    )
    sys.modules["app.services.notifier"] = types.SimpleNamespace(
        send_notification_channel=fake_send,
        persist_notification_delivery=_fake_persist_notification_delivery,
        _safe_exception_message=_fake_safe_exception_message,
    )
    cfg = _FakeNotificationConfig(id=9, project_id=1, channel=NotifyChannel.dingtalk, config={"webhook_url": "c"})

    result = asyncio.run(notifications.test_notification(cfg_id=9, db=_FakeDB(cfg=cfg), user=None))
    assert result["message"] and called["config"]["language"] == "en-US"
