"""补齐 device_mirror（设备投屏/镜像）未覆盖分支的覆盖率测试。

覆盖对象：backend/app/api/v1/device_mirror.py
- hierarchy XML 提取/解析的失败与节点过滤分支
- adb 截图/输入的包装函数（成功、失败、超时）
- Android Worker 派发（成功、结果无效、broker 异常）
- 租约校验与 keyevent/text 端点的 worker/adb 双路径
- MJPEG 生成器帧生产与 screen 流的 fps 钳制

全部直调模块级函数/端点函数，subprocess 与 worker 任务均以 fake 替身注入，
不依赖真机 ADB、scrcpy 二进制、PG/Redis/MinIO。
"""

import asyncio
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.api.v1 import device_mirror
from app.models.bootstrap import load_all_models
from app.models.device import DeviceStatus
from app.schemas.device import DeviceKeyEventIn, DeviceTextInputIn

load_all_models()


def _online_device(serial: str = "SERIAL123") -> SimpleNamespace:
    return SimpleNamespace(serial=serial, status=DeviceStatus.online)


def _valid_lease() -> SimpleNamespace:
    return SimpleNamespace(lease_token="tok-1", expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))


class _FakeDB:
    """最小 AsyncSession 替身：get 返回设备，execute 返回租约查询结果。"""

    def __init__(self, device, lease=None):
        self._device = device
        self._lease = lease

    async def get(self, _model, _id):
        return self._device

    async def execute(self, _statement):
        return SimpleNamespace(scalar_one_or_none=lambda: self._lease)


class _FakeProcess:
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakeAsyncResult:
    def __init__(self, result):
        self._result = result

    def get(self, timeout=None):
        return self._result


def _install_worker_task(monkeypatch, task):
    """把 app.worker.tasks_device 替换为最小替身——函数内的延迟导入会命中 sys.modules。"""
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks_device",
        SimpleNamespace(run_android_device_operation=task),
    )


# --------------------------- hierarchy 提取与解析 ---------------------------


def test_extract_hierarchy_xml_returns_none_without_open_marker():
    assert device_mirror._extract_hierarchy_xml("uiautomator output without xml") is None


def test_extract_hierarchy_xml_returns_none_without_close_marker():
    assert device_mirror._extract_hierarchy_xml('<hierarchy rotation="0">') is None


@pytest.mark.parametrize("value", [None, "", "junk", "[20,10][10,50]", "[5,0][5,10]"])
def test_parse_bounds_rejects_invalid_values(value):
    """缺值、格式错误、右界<=左界、下界<=上界 全部返回 None。"""
    assert device_mirror._parse_bounds(value) is None


def test_parse_ui_target_returns_none_without_hierarchy():
    assert device_mirror._parse_ui_target("plain text", 5, 5) is None


def test_parse_ui_target_returns_none_on_malformed_xml():
    dump = '<hierarchy rotation="0><node bounds="[0,0][10,10]"/></hierarchy>'
    assert device_mirror._parse_ui_target(dump, 5, 5) is None


def test_parse_ui_target_skips_invalid_and_hidden_nodes():
    """无 bounds/非法 bounds/点在界外/visible-to-user=false 的节点被跳过，无候选时返回 None。"""
    dump = (
        '<hierarchy rotation="0">'
        '<node class="android.widget.TextView" text="无坐标" />'
        '<node class="android.widget.TextView" text="坐标非法" bounds="bad" />'
        '<node class="android.widget.Button" text="界外" clickable="true" bounds="[500,500][600,600]" />'
        '<node class="android.widget.Button" text="隐藏" clickable="true" '
        'visible-to-user="false" bounds="[0,0][100,100]" />'
        "</hierarchy>"
    )
    assert device_mirror._parse_ui_target(dump, 10, 10) is None


# --------------------------- adb 截图/输入包装 ---------------------------


def test_adb_screenshot_returns_png_bytes_on_success(monkeypatch):
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return _FakeProcess(returncode=0, stdout=b"png-bytes")

    monkeypatch.setattr(device_mirror.subprocess, "run", fake_run)

    assert device_mirror._adb_screenshot("DEV1") == b"png-bytes"
    assert calls == [["adb", "-s", "DEV1", "exec-out", "screencap", "-p"]]


def test_adb_screenshot_returns_none_on_empty_output(monkeypatch):
    monkeypatch.setattr(device_mirror.subprocess, "run", lambda *_a, **_kw: _FakeProcess(returncode=0))

    assert device_mirror._adb_screenshot("DEV1") is None


def test_adb_screenshot_returns_none_on_failure_and_timeout(monkeypatch):
    monkeypatch.setattr(device_mirror.subprocess, "run", lambda *_a, **_kw: _FakeProcess(returncode=1, stdout=b"error"))
    assert device_mirror._adb_screenshot("DEV1") is None

    def raise_timeout(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="adb", timeout=10)

    monkeypatch.setattr(device_mirror.subprocess, "run", raise_timeout)
    assert device_mirror._adb_screenshot("DEV1") is None


def test_adb_input_reports_success_failure_and_timeout(monkeypatch):
    monkeypatch.setattr(device_mirror.subprocess, "run", lambda *_a, **_kw: _FakeProcess(returncode=0))
    assert device_mirror._adb_input("DEV1", "tap", "1", "2") is True

    monkeypatch.setattr(device_mirror.subprocess, "run", lambda *_a, **_kw: _FakeProcess(returncode=1))
    assert device_mirror._adb_input("DEV1", "tap", "1", "2") is False

    def raise_timeout(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="adb", timeout=10)

    monkeypatch.setattr(device_mirror.subprocess, "run", raise_timeout)
    assert device_mirror._adb_input("DEV1", "tap", "1", "2") is False


# --------------------------- ui-target 诊断包装 ---------------------------


def test_ui_target_diagnostic_cat_failure_is_unavailable(monkeypatch):
    processes = iter(
        [
            _FakeProcess(returncode=0, stdout=b"UI hierarchy dumped"),
            _FakeProcess(returncode=1, stderr=b"read denied"),
        ]
    )
    monkeypatch.setattr(device_mirror.subprocess, "run", lambda *_a, **_kw: next(processes))

    target, diagnostic = device_mirror._adb_ui_target_diagnostic("DEV1", 10, 20)

    assert target is None
    assert diagnostic == {"status": "unavailable", "code": "uiautomator_read_failed"}


def test_ui_target_diagnostic_timeout_is_unavailable(monkeypatch):
    def raise_timeout(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="adb", timeout=10)

    monkeypatch.setattr(device_mirror.subprocess, "run", raise_timeout)

    target, diagnostic = device_mirror._adb_ui_target_diagnostic("DEV1", 10, 20)

    assert target is None
    assert diagnostic == {"status": "unavailable", "code": "uiautomator_request_failed"}


def test_adb_ui_target_returns_only_locator(monkeypatch):
    locator = {"text": "登录"}
    monkeypatch.setattr(
        device_mirror,
        "_adb_ui_target_diagnostic",
        lambda serial, x, y, timeout=10: (locator, {"status": "found", "code": None}),
    )

    assert device_mirror._adb_ui_target("DEV1", 1, 2) == locator


# --------------------------- Worker 派发 ---------------------------


def test_dispatch_worker_operation_success_uses_queue_setting(monkeypatch):
    calls = []

    def apply_async(*, args, queue, ignore_result, expires):
        calls.append({"args": args, "queue": queue, "ignore_result": ignore_result, "expires": expires})
        return _FakeAsyncResult(result={"ok": True, "payload": 1})

    _install_worker_task(monkeypatch, SimpleNamespace(apply_async=apply_async))
    monkeypatch.setattr(device_mirror.settings, "ANDROID_WORKER_QUEUE", "mobile_special")

    result = asyncio.run(device_mirror._dispatch_worker_operation("tap", "DEV1", {"x": 1}))

    assert result == {"ok": True, "payload": 1}
    assert calls == [
        {"args": ["tap", "DEV1", {"x": 1}], "queue": "mobile_special", "ignore_result": False, "expires": 15}
    ]


def test_dispatch_worker_operation_falls_back_to_default_queue(monkeypatch):
    calls = []

    def apply_async(*, args, queue, ignore_result, expires):
        calls.append((args, queue))
        return _FakeAsyncResult(result={"ok": True})

    _install_worker_task(monkeypatch, SimpleNamespace(apply_async=apply_async))
    monkeypatch.setattr(device_mirror.settings, "ANDROID_WORKER_QUEUE", "   ")

    result = asyncio.run(device_mirror._dispatch_worker_operation("screenshot", "DEV2"))

    assert result == {"ok": True}
    assert calls == [(["screenshot", "DEV2", {}], "mobile_special")]


def test_dispatch_worker_operation_raises_503_when_worker_reports_failure(monkeypatch):
    def apply_async(*, args, queue, ignore_result, expires):
        return _FakeAsyncResult(result={"ok": False, "error": "设备离线"})

    _install_worker_task(monkeypatch, SimpleNamespace(apply_async=apply_async))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(device_mirror._dispatch_worker_operation("tap", "DEV1"))

    assert exc.value.status_code == 503
    assert exc.value.detail == "设备离线"


def test_dispatch_worker_operation_raises_503_on_invalid_payload(monkeypatch):
    def apply_async(*, args, queue, ignore_result, expires):
        return _FakeAsyncResult(result="not-a-dict")

    _install_worker_task(monkeypatch, SimpleNamespace(apply_async=apply_async))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(device_mirror._dispatch_worker_operation("tap", "DEV1"))

    assert exc.value.status_code == 503
    assert exc.value.detail == "Worker 返回结果无效"


def test_dispatch_worker_operation_raises_503_when_broker_unavailable(monkeypatch):
    def apply_async(*, args, queue, ignore_result, expires):
        raise RuntimeError("celery broker down")

    _install_worker_task(monkeypatch, SimpleNamespace(apply_async=apply_async))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(device_mirror._dispatch_worker_operation("tap", "DEV1"))

    assert exc.value.status_code == 503
    assert exc.value.detail == "Android Worker 不可用或设备操作超时"


# --------------------------- 截图与租约 ---------------------------


def test_screenshot_local_mode_delegates_to_adb(monkeypatch):
    monkeypatch.setattr(device_mirror.settings, "ADB_SCAN_MODE", "local")
    monkeypatch.setattr(device_mirror, "_adb_screenshot", lambda serial: b"png")

    assert asyncio.run(device_mirror._screenshot("DEV1")) == b"png"


def test_screenshot_worker_mode_missing_payload_returns_none(monkeypatch):
    async def fake_dispatch(operation, serial, params=None):
        return {"ok": True}

    monkeypatch.setattr(device_mirror.settings, "ADB_SCAN_MODE", "worker")
    monkeypatch.setattr(device_mirror, "_dispatch_worker_operation", fake_dispatch)

    assert asyncio.run(device_mirror._screenshot("DEV1")) is None


def test_screenshot_worker_mode_invalid_base64_returns_none(monkeypatch):
    async def fake_dispatch(operation, serial, params=None):
        return {"ok": True, "data_base64": "%%%not-base64%%%"}

    monkeypatch.setattr(device_mirror.settings, "ADB_SCAN_MODE", "worker")
    monkeypatch.setattr(device_mirror, "_dispatch_worker_operation", fake_dispatch)

    assert asyncio.run(device_mirror._screenshot("DEV1")) is None


def test_require_control_lease_skips_in_local_mode(monkeypatch):
    monkeypatch.setattr(device_mirror.settings, "ATP_LOCAL_MODE", True)

    asyncio.run(device_mirror._require_control_lease(_FakeDB(_online_device()), 1, None))


def test_require_control_lease_missing_lease_raises_409(monkeypatch):
    monkeypatch.setattr(device_mirror.settings, "ATP_LOCAL_MODE", False)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(device_mirror._require_control_lease(_FakeDB(_online_device(), lease=None), 1, "stale-token"))

    assert exc.value.status_code == 409
    assert exc.value.detail == "设备租约不存在或已过期，请重新获取租约"


def test_device_screenshot_returns_503_when_capture_fails(monkeypatch):
    async def fake_screenshot(serial):
        return None

    monkeypatch.setattr(device_mirror, "_screenshot", fake_screenshot)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(device_mirror.device_screenshot(1, db=_FakeDB(_online_device("DEV1")), _=None))

    assert exc.value.status_code == 503
    assert exc.value.detail == "截图失败，请检查设备连接"


# --------------------------- ui-target / keyevent / text 端点 ---------------------------


def test_ui_target_worker_mode_includes_diagnostic(monkeypatch):
    async def fake_dispatch(operation, serial, params=None):
        assert operation == "ui_target"
        assert params == {"x": 10, "y": 20}
        return {"ok": True, "target": {"text": "登录"}, "diagnostic": {"status": "found", "code": None}}

    monkeypatch.setattr(device_mirror.settings, "ADB_SCAN_MODE", "worker")
    monkeypatch.setattr(device_mirror, "_dispatch_worker_operation", fake_dispatch)

    result = asyncio.run(
        device_mirror.device_ui_target(1, x=10, y=20, db=_FakeDB(_online_device("WIN-DEVICE")), _=None)
    )

    assert result == {"target": {"text": "登录"}, "diagnostic": {"status": "found", "code": None}}


def test_keyevent_worker_mode_dispatches_keycode(monkeypatch):
    calls = []

    async def fake_dispatch(operation, serial, params=None):
        calls.append((operation, serial, params))
        return {"ok": True}

    monkeypatch.setattr(device_mirror.settings, "ADB_SCAN_MODE", "worker")
    monkeypatch.setattr(device_mirror.settings, "ATP_LOCAL_MODE", False)
    monkeypatch.setattr(device_mirror, "_dispatch_worker_operation", fake_dispatch)

    result = asyncio.run(
        device_mirror.device_keyevent(
            1,
            DeviceKeyEventIn(keycode=3),
            db=_FakeDB(_online_device("WIN-DEVICE"), lease=_valid_lease()),
            lease_token="tok-1",
            _=None,
        )
    )

    assert result == {"success": True, "keycode": "3"}
    assert calls == [("keyevent", "WIN-DEVICE", {"keycode": "3"})]


def test_keyevent_adb_path_success(monkeypatch):
    calls = []

    def fake_input(serial, *args):
        calls.append((serial, args))
        return True

    monkeypatch.setattr(device_mirror.settings, "ADB_SCAN_MODE", "local")
    monkeypatch.setattr(device_mirror.settings, "ATP_LOCAL_MODE", False)
    monkeypatch.setattr(device_mirror, "_adb_input", fake_input)

    result = asyncio.run(
        device_mirror.device_keyevent(
            1,
            DeviceKeyEventIn(keycode="KEYCODE_HOME"),
            db=_FakeDB(_online_device("DEV1"), lease=_valid_lease()),
            lease_token="tok-1",
            _=None,
        )
    )

    assert result == {"success": True, "keycode": "KEYCODE_HOME"}
    assert calls == [("DEV1", ("keyevent", "KEYCODE_HOME"))]


def test_keyevent_adb_failure_raises_503(monkeypatch):
    monkeypatch.setattr(device_mirror.settings, "ATP_LOCAL_MODE", False)
    monkeypatch.setattr(device_mirror, "_adb_input", lambda *_a: False)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            device_mirror.device_keyevent(
                1,
                DeviceKeyEventIn(keycode=4),
                db=_FakeDB(_online_device("DEV1"), lease=_valid_lease()),
                lease_token="tok-1",
                _=None,
            )
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "按键执行失败，请检查设备连接"


def test_text_worker_mode_encodes_spaces(monkeypatch):
    calls = []

    async def fake_dispatch(operation, serial, params=None):
        calls.append((operation, serial, params))
        return {"ok": True}

    monkeypatch.setattr(device_mirror.settings, "ADB_SCAN_MODE", "worker")
    monkeypatch.setattr(device_mirror.settings, "ATP_LOCAL_MODE", False)
    monkeypatch.setattr(device_mirror, "_dispatch_worker_operation", fake_dispatch)

    result = asyncio.run(
        device_mirror.device_text(
            1,
            DeviceTextInputIn(text="hello world"),
            db=_FakeDB(_online_device("WIN-DEVICE"), lease=_valid_lease()),
            lease_token="tok-1",
            _=None,
        )
    )

    assert result == {"success": True}
    assert calls == [("text", "WIN-DEVICE", {"text": "hello%sworld"})]


def test_text_adb_path_success(monkeypatch):
    calls = []

    def fake_input(serial, *args):
        calls.append(args)
        return True

    monkeypatch.setattr(device_mirror.settings, "ADB_SCAN_MODE", "local")
    monkeypatch.setattr(device_mirror.settings, "ATP_LOCAL_MODE", False)
    monkeypatch.setattr(device_mirror, "_adb_input", fake_input)

    result = asyncio.run(
        device_mirror.device_text(
            1,
            DeviceTextInputIn(text="hi"),
            db=_FakeDB(_online_device("DEV1"), lease=_valid_lease()),
            lease_token="tok-1",
            _=None,
        )
    )

    assert result == {"success": True}
    assert calls == [("text", "hi")]


def test_text_adb_failure_raises_503(monkeypatch):
    monkeypatch.setattr(device_mirror.settings, "ATP_LOCAL_MODE", False)
    monkeypatch.setattr(device_mirror, "_adb_input", lambda *_a: False)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            device_mirror.device_text(
                1,
                DeviceTextInputIn(text="hi"),
                db=_FakeDB(_online_device("DEV1"), lease=_valid_lease()),
                lease_token="tok-1",
                _=None,
            )
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "文本输入失败，请检查设备连接"


# --------------------------- MJPEG 帧流 ---------------------------


def test_mjpeg_generator_yields_frames_and_skips_errors(monkeypatch):
    """截图异常被吞掉、空帧不产出；正常帧按 MJPEG 分帧格式输出，间隔由 fps 决定。"""
    shots = []

    async def fake_screenshot(serial):
        shots.append(serial)
        if len(shots) == 1:
            raise HTTPException(status_code=503, detail="截图失败")
        if len(shots) in (2, 4):
            return b"png-frame"
        return None

    sleeps = []

    async def fake_sleep(interval):
        sleeps.append(interval)

    monkeypatch.setattr(device_mirror, "_screenshot", fake_screenshot)
    monkeypatch.setattr(device_mirror.asyncio, "sleep", fake_sleep)

    async def drive():
        generator = device_mirror._mjpeg_generator("DEV1", fps=2.0)
        first = await anext(generator)
        second = await anext(generator)
        await generator.aclose()
        return first, second

    first, second = asyncio.run(drive())

    expected = b"--frame\r\nContent-Type: image/png\r\nContent-Length: 9\r\n\r\npng-frame\r\n"
    assert first == expected
    assert second == expected
    assert sleeps == [0.5, 0.5, 0.5]
    assert shots == ["DEV1", "DEV1", "DEV1", "DEV1"]


@pytest.mark.parametrize("requested_fps,expected_fps", [(0.2, 0.5), (2.0, 2.0), (9.0, 5.0)])
def test_screen_stream_clamps_fps_and_returns_mjpeg(monkeypatch, requested_fps, expected_fps):
    seen = []

    async def fake_generator(serial, fps=2.0):
        seen.append((serial, fps))
        yield b"frame"

    monkeypatch.setattr(device_mirror, "_mjpeg_generator", fake_generator)

    async def drive():
        response = await device_mirror.device_screen_stream(
            1, fps=requested_fps, db=_FakeDB(_online_device("DEV1")), _=None
        )
        chunks = [chunk async for chunk in response.body_iterator]
        return response, chunks

    response, chunks = asyncio.run(drive())

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "multipart/x-mixed-replace; boundary=frame"
    assert chunks == [b"frame"]
    assert seen == [("DEV1", expected_fps)]
