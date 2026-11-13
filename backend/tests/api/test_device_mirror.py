"""设备屏幕镜像 tap/swipe 实时交互端点的契约与逻辑测试。

沿用本目录轻量单元风格：stub 掉 database/deps，权限用 inspect 断言依赖，
逻辑用 asyncio.run 直接调用端点函数并 monkeypatch 掉 adb 子进程调用。
"""

import asyncio
import base64
import inspect
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import BackgroundTasks, HTTPException

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
    """最小 AsyncSession 替身，仅实现 device_mirror 用到的 get/scalar/execute。"""

    def __init__(self, device, lease_token="test-lease-token", scalar_result=None, rows=None):
        self._device = device
        self._lease = (
            types.SimpleNamespace(
                lease_token=lease_token,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
            if lease_token
            else None
        )
        self._scalar = scalar_result
        self._rows = rows

    async def get(self, _model, _id):
        return self._device

    async def scalar(self, _statement):
        return self._scalar

    async def execute(self, _statement):
        if self._rows is not None:
            return types.SimpleNamespace(scalars=lambda: types.SimpleNamespace(all=lambda: self._rows))
        return types.SimpleNamespace(scalar_one_or_none=lambda: self._lease)


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


def test_ui_target_diagnostic_hides_adb_dump_error(monkeypatch):
    class _Process:
        returncode = 1
        stdout = b""
        stderr = b"Permission denied: raw device detail must not leave this helper"

    monkeypatch.setattr(device_mirror.subprocess, "run", lambda *_args, **_kwargs: _Process())

    target, diagnostic = device_mirror._adb_ui_target_diagnostic("DEV1", 10, 20)

    assert target is None
    assert diagnostic == {"status": "unavailable", "code": "uiautomator_dump_failed"}


def test_ui_target_diagnostic_reports_coordinate_without_locator(monkeypatch):
    class _Process:
        def __init__(self, returncode, stdout=b"", stderr=b""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    processes = iter(
        [
            _Process(0, stdout=b"UI hierarchy dumped to: /sdcard/atp-ui-hierarchy.xml"),
            _Process(0, stdout=b'<hierarchy><node bounds="[0,0][100,100]" /></hierarchy>'),
        ]
    )
    monkeypatch.setattr(device_mirror.subprocess, "run", lambda *_args, **_kwargs: next(processes))

    target, diagnostic = device_mirror._adb_ui_target_diagnostic("DEV1", 10, 20)

    assert target is None
    assert diagnostic == {"status": "not_found", "code": "target_not_found"}


def test_ui_target_endpoint_returns_locator(monkeypatch):
    target = {"text": "登录", "resourceId": "com.demo:id/login"}
    monkeypatch.setattr(
        device_mirror,
        "_adb_ui_target_diagnostic",
        lambda serial, x, y: (target, {"status": "found", "code": None}),
    )

    result = asyncio.run(
        device_mirror.device_ui_target(
            device_id=1,
            x=10,
            y=20,
            db=_FakeDB(_online_device("DEV1")),
            _=None,
        )
    )

    assert result == {"target": target, "diagnostic": {"status": "found", "code": None}}


def test_ui_target_endpoint_exposes_sanitized_unavailable_diagnostic(monkeypatch):
    monkeypatch.setattr(
        device_mirror,
        "_adb_ui_target_diagnostic",
        lambda serial, x, y: (None, {"status": "unavailable", "code": "uiautomator_dump_failed"}),
    )

    result = asyncio.run(
        device_mirror.device_ui_target(
            device_id=1,
            x=10,
            y=20,
            db=_FakeDB(_online_device("DEV1")),
            _=None,
        )
    )

    assert result == {
        "target": None,
        "diagnostic": {"status": "unavailable", "code": "uiautomator_dump_failed"},
    }


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
    tap = asyncio.run(
        device_mirror.device_tap(
            1,
            DeviceTapIn(x=10, y=20),
            db=device,
            lease_token="test-lease-token",
            _=None,
        )
    )
    target = asyncio.run(device_mirror.device_ui_target(1, x=10, y=20, db=device, _=None))
    swipe = asyncio.run(
        device_mirror.device_swipe(
            1,
            DeviceSwipeIn(x1=1, y1=2, x2=3, y2=4, duration_ms=50),
            db=device,
            lease_token="test-lease-token",
            _=None,
        )
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
            lease_token="test-lease-token",
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
            device_mirror.device_tap(
                device_id=1,
                body=DeviceTapIn(x=1, y=2),
                db=_FakeDB(_online_device()),
                lease_token="test-lease-token",
                _=None,
            )
        )
    assert exc.value.status_code == 503


def test_tap_requires_active_device_lease(monkeypatch):
    monkeypatch.setattr(device_mirror, "_adb_input", lambda *_args: True)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            device_mirror.device_tap(
                device_id=1,
                body=DeviceTapIn(x=1, y=2),
                db=_FakeDB(_online_device(), lease_token=None),
                lease_token=None,
                _=None,
            )
        )
    assert exc.value.status_code == 409
    assert exc.value.detail == "设备控制需要先获取有效租约"


def test_tap_offline_device_raises_400(monkeypatch):
    monkeypatch.setattr(device_mirror, "_adb_input", lambda *a: True)
    offline = types.SimpleNamespace(serial="X", status=DeviceStatus.offline)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            device_mirror.device_tap(
                device_id=1,
                body=DeviceTapIn(x=1, y=2),
                db=_FakeDB(offline),
                lease_token="test-lease-token",
                _=None,
            )
        )
    assert exc.value.status_code == 400


def test_tap_missing_device_raises_404(monkeypatch):
    monkeypatch.setattr(device_mirror, "_adb_input", lambda *a: True)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            device_mirror.device_tap(
                device_id=99,
                body=DeviceTapIn(x=1, y=2),
                db=_FakeDB(None),
                lease_token="test-lease-token",
                _=None,
            )
        )
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
            lease_token="test-lease-token",
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
            lease_token="test-lease-token",
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
                lease_token="test-lease-token",
                _=None,
            )
        )
    assert exc.value.status_code == 503


# --------------------------- 截图降采样 ---------------------------


def _png_bytes(width: int, height: int, noisy: bool = False) -> bytes:
    import io
    import os

    from PIL import Image

    buffer = io.BytesIO()
    if noisy:
        image = Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))
    else:
        image = Image.new("RGB", (width, height), (10, 120, 200))
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_encode_screenshot_downscales_and_transcodes_to_jpeg():
    """轮询用 JPEG 540 宽：体积要显著小于原始 PNG，且宽度按比例缩小。"""
    import io

    from PIL import Image

    original = _png_bytes(1080, 1920, noisy=True)
    encoded, media_type = device_mirror._encode_screenshot(original, 540, "jpeg")

    assert media_type == "image/jpeg"
    assert len(encoded) < len(original) / 5
    with Image.open(io.BytesIO(encoded)) as image:
        assert image.size == (540, 960)


def test_encode_screenshot_keeps_png_when_no_options():
    original = _png_bytes(1080, 1920)
    encoded, media_type = device_mirror._encode_screenshot(original, None, "png")
    assert encoded == original
    assert media_type == "image/png"


def test_screenshot_route_returns_jpeg_when_requested(monkeypatch):
    monkeypatch.setattr(device_mirror.settings, "ADB_SCAN_MODE", "local")
    monkeypatch.setattr(device_mirror, "_adb_screenshot", lambda *_a, **_k: _png_bytes(1080, 1920))

    response = asyncio.run(
        device_mirror.device_screenshot(1, max_width=540, fmt="jpeg", db=_FakeDB(_online_device()), _=None)
    )

    assert response.media_type == "image/jpeg"
    assert len(response.body) < 200_000


# --------------------------- 设备已安装包名与前台包名 ---------------------------


def test_parse_package_list_and_foreground_app():
    pm_out = """
    package:com.hopesen.aiphytraining
    package:/data/app/~~abc/com.alibaba.android.rimet-1/base.apk=com.alibaba.android.rimet
    package:invalid_single_segment
    """
    win_out = """
      mCurrentFocus=Window{8ef51a2 u0 StatusBar}
      mFocusedApp=ActivityRecord{77bb13e u0 com.hopesen.aiphytraining/.view.list.ExaminationListActivity} t141}
    """
    assert device_mirror._parse_package_list(pm_out) == [
        "com.alibaba.android.rimet",
        "com.hopesen.aiphytraining",
    ]
    assert device_mirror._parse_foreground_app(win_out) == (
        "com.hopesen.aiphytraining",
        ".view.list.ExaminationListActivity",
    )


def _snapshot(read_at, packages=None, current_package=None, source="refresh"):
    return types.SimpleNamespace(
        id=1,
        device_id=7,
        serial="172.16.101.11:5555",
        current_package=current_package,
        current_activity=".view.list.ExaminationListActivity",
        packages=packages or [],
        source=source,
        triggered_by=3,
        read_at=read_at,
    )


def test_packages_endpoint_returns_empty_snapshot_before_first_read():
    out = asyncio.run(
        device_mirror.device_packages(
            device_id=7,
            db=_FakeDB(_online_device("172.16.101.11:5555")),
            _=None,
        )
    )

    assert out.device_id == 7
    assert out.serial == "172.16.101.11:5555"
    assert out.packages == []
    assert out.read_at is None
    assert out.stale is True


def test_packages_endpoint_serves_cached_snapshot_with_stale_flag():
    fresh = _snapshot(
        datetime.now(timezone.utc) - timedelta(seconds=30),
        packages=["com.hopesen.aiphytraining", "com.mgtv.tv"],
        current_package="com.hopesen.aiphytraining",
    )
    out = asyncio.run(
        device_mirror.device_packages(device_id=7, db=_FakeDB(_online_device(), scalar_result=fresh), _=None)
    )

    assert out.current_package == "com.hopesen.aiphytraining"
    assert out.packages == ["com.hopesen.aiphytraining", "com.mgtv.tv"]
    assert out.stale is False
    assert out.source == "refresh"


def test_packages_endpoint_marks_old_snapshot_stale():
    old = _snapshot(datetime.now(timezone.utc) - timedelta(minutes=11), packages=["com.demo"])
    out = asyncio.run(
        device_mirror.device_packages(device_id=7, db=_FakeDB(_online_device(), scalar_result=old), _=None)
    )
    assert out.stale is True


def test_packages_history_endpoint_lists_snapshots():
    rows = [_snapshot(datetime.now(timezone.utc)), _snapshot(datetime.now(timezone.utc) - timedelta(hours=1))]
    result = asyncio.run(
        device_mirror.device_package_history(
            device_id=7,
            limit=10,
            db=_FakeDB(_online_device(), rows=rows),
            _=None,
        )
    )
    assert [item.id for item in result] == [1, 1]
    assert result[0].read_at is not None


def test_refresh_endpoint_queues_background_capture(monkeypatch):
    queued = []

    async def fake_capture(device_id, serial, user_id, include_system):
        queued.append((device_id, serial, user_id, include_system))

    monkeypatch.setattr(device_mirror, "_capture_device_packages", fake_capture)
    tasks = BackgroundTasks()
    result = asyncio.run(
        device_mirror.refresh_device_packages(
            device_id=7,
            background=tasks,
            include_system=False,
            db=_FakeDB(_online_device("172.16.101.11:5555")),
            current_user=types.SimpleNamespace(id=3),
        )
    )

    assert result == {"status": "queued", "device_id": 7, "serial": "172.16.101.11:5555"}
    assert len(tasks.tasks) == 1
    asyncio.run(tasks.tasks[0]())
    assert queued == [(7, "172.16.101.11:5555", 3, False)]


def test_refresh_endpoint_rejects_offline_device():
    offline = types.SimpleNamespace(serial="X", status=DeviceStatus.offline)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            device_mirror.refresh_device_packages(
                device_id=7,
                background=BackgroundTasks(),
                include_system=False,
                db=_FakeDB(offline),
                current_user=types.SimpleNamespace(id=3),
            )
        )
    assert exc.value.status_code == 400


class _StoreDB:
    def __init__(self):
        self.added = []
        self.deleted = []
        self.committed = 0

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None

    async def execute(self, statement):
        if statement.is_delete:
            self.deleted.append(statement)
        return types.SimpleNamespace(scalars=lambda: types.SimpleNamespace(all=lambda: []))

    async def commit(self):
        self.committed += 1


class _SessionCtx:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *_exc):
        return False


def test_background_capture_persists_snapshot(monkeypatch):
    async def fake_read(serial, include_system=False):
        assert serial == "172.16.101.11:5555"
        assert include_system is True
        return {
            "current_package": "com.hopesen.aiphytraining",
            "current_activity": ".MainActivity",
            "packages": ["com.hopesen.aiphytraining", "com.mgtv.tv"],
        }

    store = _StoreDB()
    monkeypatch.setattr(device_mirror, "_read_device_packages", fake_read)
    monkeypatch.setattr(sys.modules["app.core.database"], "AsyncSessionLocal", lambda: _SessionCtx(store))
    device_mirror._package_captures.discard(7)

    asyncio.run(device_mirror._capture_device_packages(7, "172.16.101.11:5555", 3, True))

    assert store.committed == 1
    saved = store.added[0]
    assert saved.device_id == 7
    assert saved.current_package == "com.hopesen.aiphytraining"
    assert saved.packages == ["com.hopesen.aiphytraining", "com.mgtv.tv"]
    assert saved.triggered_by == 3


def test_background_capture_deduplicates_same_device(monkeypatch):
    calls = []

    async def slow_read(serial, include_system=False):
        calls.append(serial)
        return {"packages": []}

    store = _StoreDB()
    monkeypatch.setattr(device_mirror, "_read_device_packages", slow_read)
    monkeypatch.setattr(sys.modules["app.core.database"], "AsyncSessionLocal", lambda: _SessionCtx(store))
    device_mirror._package_captures.add(7)
    try:
        asyncio.run(device_mirror._capture_device_packages(7, "SERIAL", None, False))
    finally:
        device_mirror._package_captures.discard(7)

    assert calls == []
    assert store.committed == 0


def test_parse_ui_anchors_extracts_stable_text_resource_and_ignores_system_and_noise():
    xml = """<hierarchy rotation="0">
      <node index="0" package="com.android.systemui" class="android.widget.TextView"
            text="12:34" resource-id="com.android.systemui:id/clock" bounds="[0,0][200,60]" />
      <node index="1" package="com.demo" class="android.widget.FrameLayout"
            resource-id="android:id/content" bounds="[0,60][1080,1920]">
        <node index="0" package="com.demo" class="android.widget.TextView"
              text="隐藏标题" resource-id="com.demo:id/hidden" visible-to-user="false" bounds="[40,80][400,120]" />
        <node index="1" package="com.demo" class="android.widget.TextView"
              text="99+" clickable="false" bounds="[40,120][140,170]" />
        <node index="2" package="com.demo" class="android.widget.TextView"
              text="欢迎使用" clickable="false" bounds="[40,180][420,240]" />
        <node index="3" package="com.demo" class="android.widget.EditText"
              text="alice" resource-id="com.demo:id/username" clickable="true" bounds="[40,280][600,360]" />
        <node index="4" package="com.demo" class="android.widget.ImageView"
              content-desc="课程封面" clickable="false" bounds="[40,400][300,600]" />
        <node index="5" package="com.demo" class="android.widget.Button"
              text="开始训练" resource-id="com.demo:id/btn_start" clickable="true" bounds="[80,700][500,820]" />
      </node>
    </hierarchy>"""

    anchors = device_mirror._parse_ui_anchors(xml)

    assert anchors == {
        "text": "欢迎使用",
        "resourceId": "com.demo:id/btn_start",
        "contentDesc": "课程封面",
        "packageName": "com.demo",
    }


def test_parse_ui_anchors_returns_none_when_only_system_or_hidden_nodes_exist():
    xml = """<hierarchy rotation="0">
      <node index="0" package="com.android.systemui" class="android.widget.TextView"
            text="WLAN" resource-id="com.android.systemui:id/wifi" bounds="[0,0][100,50]" />
      <node index="1" package="com.demo" class="android.widget.TextView"
            text="隐藏" resource-id="com.demo:id/hidden" visible-to-user="false" bounds="[0,60][200,120]" />
    </hierarchy>"""

    assert device_mirror._parse_ui_anchors(xml) is None


def test_adb_ui_anchors_diagnostic_handles_found_not_found_and_unavailable(monkeypatch):
    valid_xml = (
        b'<hierarchy><node package="com.demo" class="android.widget.TextView" '
        b'text="\xe9\xa6\x96\xe9\xa1\xb5" resource-id="com.demo:id/home_title" '
        b'bounds="[10,100][300,180]" /></hierarchy>'
    )
    processes = iter(
        [
            types.SimpleNamespace(returncode=0, stdout=b"UI hierchary dumped", stderr=b""),
            types.SimpleNamespace(returncode=0, stdout=valid_xml, stderr=b""),
            types.SimpleNamespace(returncode=0, stdout=b"UI hierchary dumped", stderr=b""),
            types.SimpleNamespace(returncode=0, stdout=b"<hierarchy></hierarchy>", stderr=b""),
            types.SimpleNamespace(returncode=1, stdout=b"", stderr=b"ERROR: dump failed"),
        ]
    )
    monkeypatch.setattr(device_mirror.subprocess, "run", lambda *_args, **_kwargs: next(processes))

    found_anchors, found_diag = device_mirror._adb_ui_anchors_diagnostic("DEV1")
    missing_anchors, missing_diag = device_mirror._adb_ui_anchors_diagnostic("DEV1")
    failed_anchors, failed_diag = device_mirror._adb_ui_anchors_diagnostic("DEV1")

    assert found_anchors == {
        "text": "首页",
        "resourceId": "com.demo:id/home_title",
        "contentDesc": None,
        "packageName": "com.demo",
    }
    assert found_diag == {"status": "found", "code": None}
    assert missing_anchors is None
    assert missing_diag == {"status": "not_found", "code": "anchor_not_found"}
    assert failed_anchors is None
    assert failed_diag == {"status": "unavailable", "code": "uiautomator_dump_failed"}


def test_ui_anchors_endpoint_supports_local_and_worker_modes(monkeypatch):
    assert _dep_of(device_mirror.device_ui_anchors) is _noop_current_user

    anchors = {"text": "工作台", "resourceId": "com.demo:id/tab_home", "contentDesc": None, "packageName": "com.demo"}
    monkeypatch.setattr(
        device_mirror,
        "_adb_ui_anchors_diagnostic",
        lambda serial: (anchors, {"status": "found", "code": None}),
    )

    local_result = asyncio.run(device_mirror.device_ui_anchors(device_id=1, db=_FakeDB(_online_device("DEV1")), _=None))
    assert local_result == {"anchors": anchors, "diagnostic": {"status": "found", "code": None}}

    calls = []

    async def fake_dispatch(operation, serial, params=None):
        calls.append((operation, serial, params))
        return {"ok": True, "anchors": anchors, "diagnostic": {"status": "found", "code": None}}

    monkeypatch.setattr(device_mirror.settings, "ADB_SCAN_MODE", "worker")
    monkeypatch.setattr(device_mirror, "_dispatch_worker_operation", fake_dispatch)

    worker_result = asyncio.run(
        device_mirror.device_ui_anchors(device_id=1, db=_FakeDB(_online_device("WIN-DEV")), _=None)
    )
    assert worker_result == {"anchors": anchors, "diagnostic": {"status": "found", "code": None}}
    assert calls == [("ui_anchors", "WIN-DEV", None)]
