"""Tests for current-user settings API."""
import asyncio
import inspect
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)


def _fake_get_current_user():
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(get_current_user=_fake_get_current_user)

from app.api.v1 import user_settings
from app.models.bootstrap import load_all_models
from app.models.user_setting import UserSetting
from app.schemas.user_setting import UserSettingUpdateIn

load_all_models()


class _FakeUser:
    id = 7
    username = "alice"


class _Result:
    def __init__(self, items):
        self.items = list(items)

    def scalar_one_or_none(self):
        return self.items[0] if self.items else None

    def scalars(self):
        return self

    def all(self):
        return self.items


class _FakeDB:
    def __init__(self, items=None):
        self.items = list(items or [])
        self.added = []
        self.deleted = []
        self.commits = 0

    async def execute(self, _stmt):
        return _Result(self.items)

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = len(self.items) + 1
        now = datetime(2026, 5, 28, tzinfo=timezone.utc)
        obj.created_at = now
        obj.updated_at = now
        self.items.append(obj)
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = datetime(2026, 5, 28, tzinfo=timezone.utc)

    async def delete(self, obj):
        self.deleted.append(obj)
        self.items = [item for item in self.items if item is not obj]


def _setting(key="dashboard.layout", value=None):
    now = datetime(2026, 5, 28, tzinfo=timezone.utc)
    return UserSetting(
        id=1,
        user_id=7,
        key=key,
        value=value or {"charts": ["passRate"]},
        created_at=now,
        updated_at=now,
    )


def test_endpoints_use_current_user_dependency():
    for fn in (
        user_settings.list_my_settings,
        user_settings.get_my_setting,
        user_settings.upsert_my_setting,
        user_settings.delete_my_setting,
    ):
        dep = inspect.signature(fn).parameters["current_user"].default.dependency
        assert dep is _fake_get_current_user


def test_list_my_settings_returns_values():
    db = _FakeDB([_setting("language", {"value": "zh-CN"})])
    result = asyncio.run(user_settings.list_my_settings(db=db, current_user=_FakeUser()))
    assert len(result) == 1
    assert result[0].key == "language"
    assert result[0].value == {"value": "zh-CN"}


def test_get_my_setting_404_when_missing():
    db = _FakeDB([])
    try:
        asyncio.run(user_settings.get_my_setting(key="missing", db=db, current_user=_FakeUser()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("应 404")


def test_upsert_my_setting_creates_when_missing():
    db = _FakeDB([])
    body = UserSettingUpdateIn(value={"visible": ["duration"]})
    result = asyncio.run(
        user_settings.upsert_my_setting(key="dashboard.layout", body=body, db=db, current_user=_FakeUser())
    )
    assert result.key == "dashboard.layout"
    assert result.user_id == 7
    assert result.value == {"visible": ["duration"]}
    assert db.commits == 1
    assert len(db.added) == 1


def test_upsert_my_setting_updates_existing():
    existing = _setting(value={"visible": ["old"]})
    db = _FakeDB([existing])
    body = UserSettingUpdateIn(value={"visible": ["new"]})
    result = asyncio.run(
        user_settings.upsert_my_setting(key="dashboard.layout", body=body, db=db, current_user=_FakeUser())
    )
    assert result is existing
    assert existing.value == {"visible": ["new"]}
    assert db.commits == 1
    assert not db.added


def test_upsert_rejects_blank_key():
    db = _FakeDB([])
    body = UserSettingUpdateIn(value={})
    try:
        asyncio.run(user_settings.upsert_my_setting(key="  ", body=body, db=db, current_user=_FakeUser()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("应 400")


def test_upsert_rejects_oversized_value():
    db = _FakeDB([])
    body = UserSettingUpdateIn(value={"blob": "x" * (65 * 1024)})
    try:
        asyncio.run(user_settings.upsert_my_setting(key="dashboard.layout", body=body, db=db, current_user=_FakeUser()))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert "64KB" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("应 400")


def test_delete_my_setting_is_idempotent():
    existing = _setting()
    db = _FakeDB([existing])
    result = asyncio.run(user_settings.delete_my_setting(key="dashboard.layout", db=db, current_user=_FakeUser()))
    assert result is None
    assert db.deleted == [existing]
    assert db.commits == 1
