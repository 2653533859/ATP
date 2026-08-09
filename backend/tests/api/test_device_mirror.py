"""设备屏幕镜像 tap/swipe 实时交互端点的契约与逻辑测试。

沿用本目录轻量单元风格：stub 掉 database/deps，权限用 inspect 断言依赖，
逻辑用 asyncio.run 直接调用端点函数并 monkeypatch 掉 adb 子进程调用。
"""

import asyncio
import inspect
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.api.conftest import fake_require_engineer as _fake_require_engineer


def _noop_current_user():
    return None


async def _noop_async(*_args, **_kwargs):
    return None


sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
_deps = sys.modules.setdefault("app.api.deps", types.SimpleNamespace())
_deps.get_current_user = _noop_current_user
_deps.require_engineer = _fake_require_engineer
for _name, _value in (
    ("require_admin", lambda: None),
    ("assert_project_access", _noop_async),
    ("require_project_access", lambda *_args, **_kwargs: _noop_async),
):
    if not hasattr(_deps, _name):
        setattr(_deps, _name, _value)

from app.models.device import DeviceStatus
from app.schemas.device import DeviceSwipeIn, DeviceTapIn
from app.api.v1 import device_mirror


class _FakeDB:
    """最小 AsyncSession 替身，仅实现 device_mirror 用到的 get。"""

    def __init__(self, device):
        self._device = device

    async def get(self, _model, _id):
        return self._device


def _online_device(serial="SERIAL123"):
    return types.SimpleNamespace(serial=serial, status=DeviceStatus.online)


def _dep_of(endpoint):
    return inspect.signature(endpoint).parameters["_"].default.dependency


# --------------------------- 权限契约 ---------------------------


def test_write_endpoints_require_engineer():
    """tap/swipe 写操作必须挂 require_engineer。"""
    assert _dep_of(device_mirror.device_tap) is _fake_require_engineer
    assert _dep_of(device_mirror.device_swipe) is _fake_require_engineer


def test_read_endpoints_only_require_login():
    """截图/流读操作仅需登录，且权限弱于写操作。"""
    shot_dep = _dep_of(device_mirror.device_screenshot)
    stream_dep = _dep_of(device_mirror.device_screen_stream)
    assert shot_dep is _noop_current_user
    assert stream_dep is _noop_current_user
    assert _dep_of(device_mirror.device_tap) is not shot_dep


# --------------------------- tap 逻辑 ---------------------------


def test_tap_success_invokes_adb_with_coords(monkeypatch):
    calls = {}

    def fake_input(serial, *args):
        calls["serial"] = serial
        calls["args"] = args
        return True

    monkeypatch.setattr(device_mirror, "_adb_input", fake_input)
    result = asyncio.run(
        device_mirror.device_tap(
            device_id=1,
            body=DeviceTapIn(x=10, y=20),
            db=_FakeDB(_online_device("DEV1")),
            _=None,
        )
    )
    assert result == {"success": True}
    assert calls["serial"] == "DEV1"
    assert calls["args"] == ("tap", "10", "20")


def test_tap_adb_failure_raises_503(monkeypatch):
    monkeypatch.setattr(device_mirror, "_adb_input", lambda *a: False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            device_mirror.device_tap(device_id=1, body=DeviceTapIn(x=1, y=2), db=_FakeDB(_online_device()), _=None)
        )
    assert exc.value.status_code == 503


def test_tap_offline_device_raises_400(monkeypatch):
    monkeypatch.setattr(device_mirror, "_adb_input", lambda *a: True)
    offline = types.SimpleNamespace(serial="X", status=DeviceStatus.offline)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(device_mirror.device_tap(device_id=1, body=DeviceTapIn(x=1, y=2), db=_FakeDB(offline), _=None))
    assert exc.value.status_code == 400


def test_tap_missing_device_raises_404(monkeypatch):
    monkeypatch.setattr(device_mirror, "_adb_input", lambda *a: True)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(device_mirror.device_tap(device_id=99, body=DeviceTapIn(x=1, y=2), db=_FakeDB(None), _=None))
    assert exc.value.status_code == 404


# --------------------------- swipe 逻辑 ---------------------------


def test_swipe_success_passes_all_coords(monkeypatch):
    calls = {}

    def fake_input(serial, *args):
        calls["args"] = args
        return True

    monkeypatch.setattr(device_mirror, "_adb_input", fake_input)
    result = asyncio.run(
        device_mirror.device_swipe(
            device_id=1,
            body=DeviceSwipeIn(x1=1, y1=2, x2=3, y2=4, duration_ms=300),
            db=_FakeDB(_online_device()),
            _=None,
        )
    )
    assert result == {"success": True}
    assert calls["args"] == ("swipe", "1", "2", "3", "4", "300")


@pytest.mark.parametrize("requested,expected", [(50, "100"), (300, "300"), (99999, "5000")])
def test_swipe_clamps_duration(monkeypatch, requested, expected):
    """duration_ms 被钳制到 [100, 5000]。"""
    calls = {}

    def fake_input(serial, *args):
        calls["args"] = args
        return True

    monkeypatch.setattr(device_mirror, "_adb_input", fake_input)
    asyncio.run(
        device_mirror.device_swipe(
            device_id=1,
            body=DeviceSwipeIn(x1=1, y1=2, x2=3, y2=4, duration_ms=requested),
            db=_FakeDB(_online_device()),
            _=None,
        )
    )
    assert calls["args"][-1] == expected


def test_swipe_adb_failure_raises_503(monkeypatch):
    monkeypatch.setattr(device_mirror, "_adb_input", lambda *a: False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            device_mirror.device_swipe(
                device_id=1,
                body=DeviceSwipeIn(x1=1, y1=2, x2=3, y2=4),
                db=_FakeDB(_online_device()),
                _=None,
            )
        )
    assert exc.value.status_code == 503
