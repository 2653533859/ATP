"""设备屏幕镜像 tap/swipe 实时交互端点的契约与逻辑测试。

沿用本目录轻量单元风格：stub 掉 database/deps，权限用 inspect 断言依赖，
逻辑用 asyncio.run 直接调用端点函数并 monkeypatch 掉 adb 子进程调用。
"""

import asyncio
import base64
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


def test_ui_target_parser_prefers_clickable_locator():
    dump = """
    UI hierchary dumped to: /dev/tty
    <hierarchy rotation="0">
      <node class="android.widget.FrameLayout" bounds="[0,0][1080,1920]">
        <node class="android.widget.Button" text="登录" resource-id="com.demo:id/login"
              clickable="true" enabled="true" bounds="[40,100][400,180]" />
      </node>
    </hierarchy>
    """

    target = device_mirror._parse_ui_target(dump, 100, 130)

    assert target is not None
    assert target["text"] == "登录"
    assert target["resourceId"] == "com.demo:id/login"
    assert target["clickable"] is True
    assert target["bounds"] == {"left": 40, "top": 100, "right": 400, "bottom": 180}


def test_ui_target_parser_supports_content_description():
    dump = (
        '<hierarchy><node class="android.widget.ImageButton" '
        'content-desc="打开菜单" bounds="[0,0][80,80]" clickable="true" /></hierarchy>'
    )

    target = device_mirror._parse_ui_target(dump, 20, 20)

    assert target is not None
    assert target["contentDesc"] == "打开菜单"
    assert target["text"] is None


def test_ui_target_endpoint_returns_locator(monkeypatch):
    target = {"text": "登录", "resourceId": "com.demo:id/login"}
    monkeypatch.setattr(device_mirror, "_adb_ui_target", lambda serial, x, y: target)

    result = asyncio.run(
        device_mirror.device_ui_target(
            device_id=1,
            x=10,
            y=20,
            db=_FakeDB(_online_device("DEV1")),
            _=None,
        )
    )

    assert result == {"target": target}


def test_worker_mode_routes_device_operations_to_android_worker(monkeypatch):
    calls = []

    async def fake_dispatch(operation, serial, params=None):
        calls.append((operation, serial, params))
        if operation == "screenshot":
            return {"ok": True, "data_base64": base64.b64encode(b"png").decode("ascii")}
        if operation == "ui_target":
            return {"ok": True, "target": {"text": "登录"}}
        return {"ok": True}

    monkeypatch.setattr(device_mirror.settings, "ADB_SCAN_MODE", "worker")
    monkeypatch.setattr(device_mirror, "_dispatch_worker_operation", fake_dispatch)
    monkeypatch.setattr(
        device_mirror, "_adb_input", lambda *_args: (_ for _ in ()).throw(AssertionError("不应在 API 进程调用 ADB"))
    )
    device = _FakeDB(_online_device("WIN-DEVICE"))

    screenshot = asyncio.run(device_mirror.device_screenshot(1, db=device, _=None))
    tap = asyncio.run(device_mirror.device_tap(1, DeviceTapIn(x=10, y=20), db=device, _=None))
    target = asyncio.run(device_mirror.device_ui_target(1, x=10, y=20, db=device, _=None))
    swipe = asyncio.run(
        device_mirror.device_swipe(1, DeviceSwipeIn(x1=1, y1=2, x2=3, y2=4, duration_ms=50), db=device, _=None)
    )

    assert screenshot.body == b"png"
    assert tap == {"success": True}
    assert target == {"target": {"text": "登录"}}
    assert swipe == {"success": True}
    assert [call[0] for call in calls] == ["screenshot", "tap", "ui_target", "swipe"]
    assert calls[-1][2]["duration_ms"] == 100


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
