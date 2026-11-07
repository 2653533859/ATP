"""android_lowcode_executor 覆盖率补齐：adb 辅助函数分支 + 低代码主流程/设备矩阵（全 fake）。

仅新建文件，不改动源码与既有测试；所有 adb/子进程/MinIO/Redis 调用均以 fake 隔离。
"""

import asyncio
import types
from pathlib import Path

import pytest

from app.models.bootstrap import load_all_models

load_all_models()

from app.models.case import RunStatus  # noqa: E402
from app.services.device_leases import DeviceLeaseConflict  # noqa: E402
from app.services.mobile_special.preflight import AndroidPreflightError  # noqa: E402
from app.worker.executors import android_lowcode_executor as ale  # noqa: E402


@pytest.fixture(autouse=True)
def _offline_run_control(monkeypatch):
    """执行控制默认离线：不访问 Redis 取消信号，租约心跳直接成功。"""

    async def heartbeat(_db, _device_id, lease_token, **_kwargs):
        return types.SimpleNamespace(lease_token=lease_token)

    monkeypatch.setattr(ale, "is_cancel_requested", lambda _run_id: False)
    monkeypatch.setattr(ale, "clear_cancel_request", lambda _run_id: None)
    monkeypatch.setattr(ale, "heartbeat_device_lease", heartbeat)


class _AdbRecorder:
    def __init__(self, result=(True, "ok")):
        self.calls = []
        self.result = result

    def __call__(self, serial, *args, **kwargs):
        self.calls.append((serial, args, kwargs))
        return self.result


def test_replace_vars_empty_string_is_passthrough():
    assert ale._replace_vars("", {"A": "1"}) == ""
    assert ale._replace_vars("x{{A}}", {"A": "1"}) == "x1"


def test_capture_android_text_artifact_paths(monkeypatch):
    adb = _AdbRecorder((True, "device-info-text"))
    uploads = []
    monkeypatch.setattr(ale, "_adb_cmd", adb)
    monkeypatch.setattr(ale, "upload_bytes", lambda name, data, ct: uploads.append((name, data, ct)))
    monkeypatch.setattr(ale, "presigned_url", lambda name, expires_seconds=None: f"https://minio/{name}")

    url = asyncio.run(ale._capture_android_text_artifact("S1", 7, "logcat", ("shell", "logcat")))
    assert url == "https://minio/android-artifacts/runs/7/logcat.txt"
    assert uploads[0][0] == "android-artifacts/runs/7/logcat.txt"
    assert uploads[0][1] == b"device-info-text"
    assert adb.calls[0][0] == "S1"
    assert adb.calls[0][2]["timeout"] == 30

    monkeypatch.setattr(ale, "_adb_cmd", _AdbRecorder((False, "err")))
    assert asyncio.run(ale._capture_android_text_artifact("S1", 7, "logcat", ("shell", "logcat"))) is None

    monkeypatch.setattr(ale, "_adb_cmd", _AdbRecorder((True, "")))
    assert asyncio.run(ale._capture_android_text_artifact("S1", 7, "logcat", ("shell", "logcat"))) is None

    monkeypatch.setattr(ale, "_adb_cmd", _AdbRecorder((True, "data")))

    def _boom(name, data, ct):
        raise RuntimeError("minio down")

    monkeypatch.setattr(ale, "upload_bytes", _boom)
    assert asyncio.run(ale._capture_android_text_artifact("S1", 7, "logcat", ("shell", "logcat"))) is None


class _RecProcess:
    def __init__(self, terminate_error=None):
        self.terminate_error = terminate_error
        self.terminated = False
        self.killed = False
        self.waited = []

    def terminate(self):
        self.terminated = True
        if self.terminate_error is not None:
            raise self.terminate_error

    def wait(self, timeout=None):
        self.waited.append(timeout)
        return 0

    def kill(self):
        self.killed = True


def _install_recording_env(monkeypatch, *, pull_returncode=0, upload_error=None, terminate_error=None):
    events = types.SimpleNamespace(uploads=[], runs=[])
    process = _RecProcess(terminate_error=terminate_error)

    def fake_run(cmd, **kwargs):
        events.runs.append(list(cmd))
        if "pull" in cmd:
            if pull_returncode == 0:
                Path(cmd[-1]).write_bytes(b"mp4-data")
            return types.SimpleNamespace(returncode=pull_returncode)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(ale.subprocess, "run", fake_run)

    def _upload(name, path, ct):
        if upload_error is not None:
            raise upload_error
        events.uploads.append((name, str(path), ct))

    monkeypatch.setattr(ale, "upload_file", _upload)
    monkeypatch.setattr(ale, "presigned_url", lambda name, expires_seconds=None: f"https://minio/{name}")
    return events, process


def test_start_screen_recording_branches(monkeypatch):
    started = []
    monkeypatch.setattr(ale.subprocess, "Popen", lambda cmd, **kwargs: started.append(cmd) or "proc")

    proc = ale._start_screen_recording("S1", "/sdcard/a.mp4", 999999)
    assert proc == "proc"
    assert started[0][started[0].index("--time-limit") + 1] == "1800"
    assert started[0][-1] == "/sdcard/a.mp4"

    def _boom(cmd, **kwargs):
        raise OSError("no adb")

    monkeypatch.setattr(ale.subprocess, "Popen", _boom)
    assert ale._start_screen_recording("S1", "/sdcard/a.mp4", 10) is None


def test_finish_screen_recording_paths(monkeypatch):
    events, process = _install_recording_env(monkeypatch)
    url = asyncio.run(ale._finish_screen_recording("S1", process, "/sdcard/a.mp4", 7))
    assert url == "https://minio/android-artifacts/runs/7/screen-recording.mp4"
    assert process.terminated and process.waited == [10] and not process.killed
    assert events.uploads[0][0] == "android-artifacts/runs/7/screen-recording.mp4"
    assert events.uploads[0][2] == "video/mp4"
    assert not Path(events.uploads[0][1]).exists()
    assert any("rm" in cmd and cmd[-1] == "/sdcard/a.mp4" for cmd in events.runs)

    _events2, process2 = _install_recording_env(monkeypatch, pull_returncode=1)
    assert asyncio.run(ale._finish_screen_recording("S1", process2, "/sdcard/a.mp4", 7)) is None
    assert any("rm" in cmd for cmd in _events2.runs)

    _events3, process3 = _install_recording_env(monkeypatch, terminate_error=RuntimeError("gone"))
    url3 = asyncio.run(ale._finish_screen_recording("S1", process3, "/sdcard/a.mp4", 8))
    assert process3.killed is True
    assert url3 == "https://minio/android-artifacts/runs/8/screen-recording.mp4"

    _events4, process4 = _install_recording_env(monkeypatch, upload_error=RuntimeError("minio down"))
    assert asyncio.run(ale._finish_screen_recording("S1", process4, "/sdcard/a.mp4", 7)) is None


def test_device_screen_size_variants(monkeypatch):
    monkeypatch.setattr(ale, "_adb_cmd", _AdbRecorder((False, "")))
    assert ale._device_screen_size("S1") is None
    monkeypatch.setattr(ale, "_adb_cmd", _AdbRecorder((True, "no size here")))
    assert ale._device_screen_size("S1") is None
    monkeypatch.setattr(ale, "_adb_cmd", _AdbRecorder((True, "Physical size: 1080x1920")))
    assert ale._device_screen_size("S1") == (1080, 1920)
    monkeypatch.setattr(ale, "_adb_cmd", _AdbRecorder((True, "Override size: 0x1920")))
    assert ale._device_screen_size("S1") is None


def test_scale_swipe_coordinates_variants(monkeypatch):
    coords = (10.4, 20.6, 30.4, 40.5)
    assert ale._scale_swipe_coordinates("S1", coords, {}) == (10, 21, 30, 40)
    assert ale._scale_swipe_coordinates("S1", coords, {"screenWidth": 0, "screenHeight": 10}) == (10, 21, 30, 40)

    monkeypatch.setattr(ale, "_device_screen_size", lambda serial: None)
    assert ale._scale_swipe_coordinates("S1", coords, {"screenWidth": 100, "screenHeight": 200}) == (10, 21, 30, 40)

    monkeypatch.setattr(ale, "_device_screen_size", lambda serial: (1080, 1920))
    scaled = ale._scale_swipe_coordinates("S1", (50, 100, 150, 200), {"screenWidth": 100, "screenHeight": 200})
    assert scaled == (540, 960, 1079, 1919)


def test_direction_coordinates_variants(monkeypatch):
    monkeypatch.setattr(ale, "_device_screen_size", lambda serial: None)
    assert ale._direction_coordinates("S1", "up") == (540, 1600, 540, 400)
    assert ale._direction_coordinates("S1", "left") == (900, 960, 100, 960)
    assert ale._direction_coordinates("S1", "sideways") is None

    monkeypatch.setattr(ale, "_device_screen_size", lambda serial: (1000, 2000))
    assert ale._direction_coordinates("S1", "up") == (500, 1666, 500, 416)
    assert ale._direction_coordinates("S1", "down") == (500, 416, 500, 1666)
    assert ale._direction_coordinates("S1", "left") == (833, 1000, 92, 1000)
    assert ale._direction_coordinates("S1", "right") == (92, 1000, 833, 1000)
    assert ale._direction_coordinates("S1", "diagonal") is None


def test_find_ui_bounds_paths():
    dump = '<hierarchy><node text="OK" bounds="[0,0][10,10]"/></hierarchy>'
    assert ale._find_ui_bounds(dump, "text", "OK") == (0, 0, 10, 10)
    assert ale._find_ui_bounds(dump, "text", "NOPE") is None

    broken = '<hierarchy><node text="OK" bounds="[0,0][10,10]"</hierarchy>'
    assert ale._find_ui_bounds(broken, "text", "OK") == (0, 0, 10, 10)

    reversed_dump = '<hierarchy><node bounds="[1,2][3,4]" text="ZZ"</hierarchy>'
    assert ale._find_ui_bounds(reversed_dump, "text", "ZZ") == (1, 2, 3, 4)

    assert ale._find_ui_bounds("<hierarchy></hierarchy>", "text", "OK") is None


class _AdbScript:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def __call__(self, serial, *args, **kwargs):
        self.calls.append((serial, args, kwargs))
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]


def test_find_and_click_content_desc_fallback(monkeypatch):
    monkeypatch.setattr(ale, "_adb_cmd", _AdbRecorder((True, "ok")))
    monkeypatch.setattr(ale, "_find_ui_center", lambda serial, selectors: None)

    result = ale._find_and_click("S1", {"contentDesc": "关闭"})
    assert result["success"] is False and result["error"] == "未找到元素: 关闭"

    result = ale._find_and_click("S1", {"resourceId": "com.x:id/btn"})
    assert result["success"] is False and result["error"] == "未找到元素: com.x:id/btn"

    result = ale._find_and_click("S1", {"text": "登录"})
    assert result["success"] is False and result["error"] == "未找到文本元素: 登录"

    result = ale._find_and_click("S1", {"x": 10, "y": 20})
    assert result["success"] is True

    result = ale._find_and_click("S1", {})
    assert result["success"] is False and result["error"] == "缺少定位参数（text/resourceId/x,y）"

    monkeypatch.setattr(ale, "_find_ui_center", lambda serial, selectors: (5, 6))
    result = ale._find_and_click("S1", {"contentDesc": "关闭"})
    assert result["success"] is True


def test_execute_step_sync_long_click_and_swipe(monkeypatch):
    adb = _AdbRecorder((True, "ok"))
    monkeypatch.setattr(ale, "_adb_cmd", adb)
    monkeypatch.setattr(ale, "_find_ui_center", lambda serial, selectors: (7, 8))

    result = ale._execute_step_sync("S1", "long_click", {"text": "OK", "duration": 900})
    assert result["success"] is True
    assert adb.calls[-1][1] == ("shell", "input", "swipe", "7", "8", "7", "8", "900")

    monkeypatch.setattr(ale, "_find_ui_center", lambda serial, selectors: None)
    result = ale._execute_step_sync("S1", "long_click", {})
    assert result["success"] is False and result["error"] == "长按需要定位属性或坐标（x, y）"

    result = ale._execute_step_sync("S1", "long_click", {"text": "OK"})
    assert result["success"] is False and result["error"] == "未找到长按目标元素"

    result = ale._execute_step_sync("S1", "long_click", {"x": 1, "y": 2, "duration": 500})
    assert result["success"] is True
    assert adb.calls[-1][1][-1] == "500"

    monkeypatch.setattr(ale, "_direction_coordinates", lambda serial, direction: (1, 2, 3, 4))
    result = ale._execute_step_sync("S1", "swipe", {"direction": "Up"})
    assert result["success"] is True
    assert adb.calls[-1][1] == ("shell", "input", "swipe", "1", "2", "3", "4", "300")

    monkeypatch.setattr(ale, "_direction_coordinates", lambda serial, direction: None)
    result = ale._execute_step_sync("S1", "swipe", {"direction": "sideways"})
    assert result["success"] is False and result["error"] == "未知滑动方向: sideways"

    result = ale._execute_step_sync("S1", "swipe", {})
    assert result["success"] is False and result["error"] == "滑动需要 direction 或坐标参数"

    result = ale._execute_step_sync("S1", "swipe", {"x1": 1, "y1": 2, "x2": 3, "y2": 4})
    assert result["success"] is True
    assert adb.calls[-1][1] == ("shell", "input", "swipe", "1", "2", "3", "4", "300")


def test_execute_step_sync_rotate_permissions_network(monkeypatch):
    adb = _AdbRecorder((True, "ok"))
    monkeypatch.setattr(ale, "_adb_cmd", adb)

    result = ale._execute_step_sync("S1", "rotate", {"orientation": "diagonal"})
    assert result["success"] is False and result["error"] == "未知屏幕方向: diagonal"

    result = ale._execute_step_sync("S1", "rotate", {"orientation": "landscape"})
    assert result["success"] is True
    assert adb.calls[-2][1][-1] == "0"
    assert adb.calls[-1][1][-1] == "1"

    monkeypatch.setattr(ale, "_adb_cmd", _AdbScript([(False, "denied"), (True, "ok")]))
    result = ale._execute_step_sync("S1", "rotate", {"orientation": "portrait"})
    assert result["success"] is False and result["error"] == "denied"

    monkeypatch.setattr(ale, "_adb_cmd", adb)
    result = ale._execute_step_sync("S1", "grant_permission", {"package": "com.x"})
    assert result["success"] is False and result["error"] == "权限步骤需要 package 和 permission"

    result = ale._execute_step_sync("S1", "grant_permission", {"package": "com.x", "permission": "p"})
    assert result["success"] is True and adb.calls[-1][1][:3] == ("shell", "pm", "grant")

    result = ale._execute_step_sync("S1", "revoke_permission", {"package": "com.x", "permission": "p"})
    assert result["success"] is True and adb.calls[-1][1][:3] == ("shell", "pm", "revoke")

    result = ale._execute_step_sync("S1", "network_profile", {"profile": "weird"})
    assert result["success"] is False and result["error"] == "未知网络配置: weird"

    result = ale._execute_step_sync("S1", "network_profile", {"profile": "offline"})
    assert result["success"] is True

    monkeypatch.setattr(ale, "_adb_cmd", _AdbScript([(True, "ok"), (False, "net err")]))
    result = ale._execute_step_sync("S1", "network_profile", {"profile": "normal"})
    assert result["success"] is False and result["error"] == "net err"


def test_execute_step_sync_input_keys_apps(monkeypatch):
    adb = _AdbRecorder((True, "ok"))
    monkeypatch.setattr(ale, "_adb_cmd", adb)
    monkeypatch.setattr("time.sleep", lambda *_args: None)
    monkeypatch.setattr(ale, "_find_ui_center", lambda serial, selectors: (3, 4))

    result = ale._execute_step_sync("S1", "input", {"text": "hi"})
    assert result["success"] is True
    assert adb.calls[-1][1] == ("shell", "input", "text", "hi")

    result = ale._execute_step_sync("S1", "input", {"text": "搜索", "targetText": "搜索框", "clear": True})
    assert result["success"] is True
    arg_lists = [call[1] for call in adb.calls]
    assert ("shell", "input", "text", "搜索") in arg_lists
    assert ("shell", "input", "keyevent", "KEYCODE_MOVE_END") in arg_lists

    result = ale._execute_step_sync("S1", "press_key", {"key": "home"})
    assert result["success"] is True
    assert adb.calls[-1][1] == ("shell", "input", "keyevent", "3")

    ale._execute_step_sync("S1", "press_key", {"key": "CUSTOM_CODE"})
    assert adb.calls[-1][1] == ("shell", "input", "keyevent", "CUSTOM_CODE")

    ale._execute_step_sync("S1", "start_app", {"package": "com.x", "activity": ".Main"})
    assert adb.calls[-1][1] == ("shell", "am", "start", "-n", "com.x/.Main")

    ale._execute_step_sync("S1", "start_app", {"package": "com.x"})
    assert adb.calls[-1][1] == ("shell", "monkey", "-p", "com.x", "-c", "android.intent.category.LAUNCHER", "1")

    ale._execute_step_sync("S1", "stop_app", {"package": "com.x"})
    assert adb.calls[-1][1] == ("shell", "am", "force-stop", "com.x")

    result = ale._execute_step_sync("S1", "background", {})
    assert result["success"] is True and adb.calls[-1][1] == ("shell", "input", "keyevent", "3")

    result = ale._execute_step_sync("S1", "foreground", {})
    assert result["success"] is False and result["error"] == "前台步骤需要 package"

    result = ale._execute_step_sync("S1", "foreground", {"package": "com.x"})
    assert result["success"] is True


def test_execute_step_sync_assertions_visual_misc(monkeypatch):
    monkeypatch.setattr(ale, "_adb_cmd", _AdbRecorder((True, "ok")))
    monkeypatch.setattr(ale, "_uiautomator_dump", lambda serial, timeout=10: (True, "页面包含 OK 字样"))

    assert ale._execute_step_sync("S1", "assert_text", {"text": "OK"}) == {"success": True}
    result = ale._execute_step_sync("S1", "assert_text", {"text": "缺失"})
    assert result["success"] is False and result["error"] == "页面中未找到文本: 缺失"

    assert ale._execute_step_sync("S1", "assert_element", {"resourceId": "OK"}) == {"success": True}
    result = ale._execute_step_sync("S1", "assert_element", {"resourceId": "com.x:id/none"})
    assert result["success"] is False and result["error"] == "未找到元素: com.x:id/none"

    result = ale._execute_step_sync("S1", "assert_visual_element", {"expected_text": "缺失"})
    assert result["success"] is False and result["error"] == "视觉断言页面中未找到预期文本: 缺失"

    monkeypatch.setattr(ale, "_uiautomator_dump", lambda serial, timeout=10: (False, ""))
    result = ale._execute_step_sync("S1", "assert_visual_element", {"expected_text": "OK"})
    assert result["success"] is False and "未找到预期文本" in result["error"]

    monkeypatch.setattr(ale, "_uiautomator_dump", lambda serial, timeout=10: (True, "OK"))
    assert ale._execute_step_sync("S1", "assert_visual_element", {"expected_text": "OK"}) == {"success": True}

    monkeypatch.setattr(ale, "_adb_screenshot", lambda serial: None)
    result = ale._execute_step_sync("S1", "assert_visual_element", {"image_template": {"a": 1}})
    assert result["success"] is False and result["error"] == "获取设备截图失败"

    monkeypatch.setattr(ale, "_adb_screenshot", lambda serial: b"PNG")
    monkeypatch.setattr("app.services.visual_assertion.evaluate_visual_assertion", lambda *a, **kw: (True, 0.97, None))
    result = ale._execute_step_sync("S1", "assert_visual_element", {"image_template": {"a": 1}})
    assert result["success"] is True and result["data"]["similarity"] == 0.97

    monkeypatch.setattr(
        "app.services.visual_assertion.evaluate_visual_assertion", lambda *a, **kw: (False, 0.2, "差异过大")
    )
    result = ale._execute_step_sync("S1", "assert_visual_element", {"image_template": {"a": 1}})
    assert result["success"] is False and result["error"] == "差异过大"

    result = ale._execute_step_sync("S1", "assert_visual_element", {})
    assert result["success"] is False and "缺少预期文本或图像模板" in result["error"]

    assert ale._execute_step_sync("S1", "wait", {"ms": 1})["success"] is True
    assert ale._execute_step_sync("S1", "screenshot", {})["data"] == {"manual_screenshot": True}
    result = ale._execute_step_sync("S1", "teleport", {})
    assert result["success"] is False and result["error"] == "未知操作类型: teleport"


class _ApkDB:
    def __init__(self, module=None, apk=None):
        self.module = module
        self.apk = apk

    async def get(self, model, pk):
        if model is ale.Module:
            return self.module
        if model is ale.Apk:
            return self.apk
        return None


def test_resolve_lowcode_apk_branches():
    case = types.SimpleNamespace(id=7, module_id=22)
    module = types.SimpleNamespace(project_id=5)

    with pytest.raises(LookupError):
        asyncio.run(ale._resolve_lowcode_apk(_ApkDB(module=None), case, {}))

    with pytest.raises(PermissionError):
        asyncio.run(ale._resolve_lowcode_apk(_ApkDB(module=module), case, {"apk_object_name": "apks/projects/9/a.apk"}))

    object_name, package = asyncio.run(
        ale._resolve_lowcode_apk(_ApkDB(module=module), case, {"apk_object_name": "apks/projects/5/a.apk"})
    )
    assert (object_name, package) == ("apks/projects/5/a.apk", None)

    with pytest.raises(LookupError):
        asyncio.run(ale._resolve_lowcode_apk(_ApkDB(module=module), case, {"apk_id": "abc"}))

    with pytest.raises(LookupError):
        asyncio.run(ale._resolve_lowcode_apk(_ApkDB(module=module, apk=None), case, {"apk_id": 3}))

    apk = types.SimpleNamespace(project_id=99, object_name="apks/projects/99/a.apk", package_name="com.a")
    with pytest.raises(PermissionError):
        asyncio.run(ale._resolve_lowcode_apk(_ApkDB(module=module, apk=apk), case, {"apk_id": 3}))

    apk = types.SimpleNamespace(project_id=5, object_name="apks/projects/5/a.apk", package_name="com.a")
    object_name, package = asyncio.run(ale._resolve_lowcode_apk(_ApkDB(module=module, apk=apk), case, {"apk_id": "3"}))
    assert (object_name, package) == ("apks/projects/5/a.apk", "com.a")

    case_no_module = types.SimpleNamespace(id=7)
    object_name, package = asyncio.run(
        ale._resolve_lowcode_apk(_ApkDB(), case_no_module, {"apk_object_name": "whatever/x.apk"})
    )
    assert (object_name, package) == ("whatever/x.apk", None)


class _DeviceDB:
    def __init__(self, device=None):
        self.device = device
        self.commits = 0
        self.added = []

    async def execute(self, stmt):
        device = self.device
        return types.SimpleNamespace(scalar_one_or_none=lambda: device)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commits += 1


def _install_android_run_env(
    monkeypatch, *, device=None, acquire_error=None, release_error=None, precheck=None, steps_recorder=None
):
    events = types.SimpleNamespace(published=[], acquired=[], released=[], steps_calls=[])
    db = _DeviceDB(device=device)
    run = types.SimpleNamespace(
        id=99,
        status=RunStatus.running,
        error_message=None,
        duration_ms=None,
        result_summary=None,
        triggered_by=1,
        trace_id="t",
        environment="e",
    )
    case = types.SimpleNamespace(id=7, module_id=22, config={})

    async def _acquire(database, device_id, **kwargs):
        events.acquired.append((device_id, kwargs))
        if acquire_error is not None:
            raise acquire_error
        return types.SimpleNamespace(lease_token="tok")

    async def _release(database, device_id, token):
        events.released.append((device_id, token))
        if release_error is not None:
            raise release_error

    async def _precheck(database, **kwargs):
        return precheck

    async def _steps(database, run_arg, case_arg, extra, **_kwargs):
        events.steps_calls.append(run_arg)
        if steps_recorder is not None:
            steps_recorder(run_arg)

    async def _publish(run_id, payload):
        events.published.append(payload)

    monkeypatch.setattr(ale, "acquire_device_lease", _acquire)
    monkeypatch.setattr(ale, "release_device_lease", _release)
    monkeypatch.setattr(ale, "precheck_android_execution", _precheck)
    monkeypatch.setattr(ale, "_run_android_lowcode_steps", _steps)
    monkeypatch.setattr(ale, "publish_run_event", _publish)
    return events, db, run, case


def test_run_android_lowcode_delegates_without_lease(monkeypatch):
    events, db, run, case = _install_android_run_env(monkeypatch)
    asyncio.run(ale.run_android_lowcode(db, run, case, {}))
    assert len(events.steps_calls) == 1 and events.acquired == []

    events2, db2, run2, case2 = _install_android_run_env(monkeypatch)
    case2.config = {"steps": [{"action": "click"}], "device_matrix": [{"serial": "S1"}]}
    asyncio.run(ale.run_android_lowcode(db2, run2, case2, {}))
    assert len(events2.steps_calls) == 1 and events2.acquired == []


def test_run_android_lowcode_unregistered_device(monkeypatch):
    events, db, run, case = _install_android_run_env(monkeypatch, device=None)
    case.config = {"steps": [{"action": "click"}], "device_serial": "S1"}
    asyncio.run(ale.run_android_lowcode(db, run, case, {}))
    assert run.status == RunStatus.error
    assert run.error_message == "设备未注册: S1"
    assert events.published[-1]["status"] == "error"


def test_run_android_lowcode_acquires_lease_and_runs(monkeypatch):
    device = types.SimpleNamespace(id=42, serial="S1")

    def _mark_passed(run_arg):
        run_arg.status = RunStatus.passed

    events, db, run, case = _install_android_run_env(
        monkeypatch, device=device, precheck=types.SimpleNamespace(ok=True, items=[]), steps_recorder=_mark_passed
    )
    case.config = {"steps": [{"action": "click"}], "device_serial": "S1", "device_lease_ttl_seconds": "abc"}
    asyncio.run(ale.run_android_lowcode(db, run, case, {}))
    assert events.acquired[0][0] == 42
    assert events.acquired[0][1]["ttl_seconds"] == 900
    assert events.released == [(42, "tok")]
    assert run.status == RunStatus.passed
    assert events.published[0]["type"] == "step_progress"
    assert events.steps_calls == [run]

    events2, db2, run2, case2 = _install_android_run_env(
        monkeypatch,
        device=device,
        precheck=types.SimpleNamespace(ok=True, items=[]),
        release_error=RuntimeError("lease gone"),
    )
    case2.config = {"steps": [{"action": "click"}], "device_serial": "S1"}
    asyncio.run(ale.run_android_lowcode(db2, run2, case2, {}))
    assert events2.released == [(42, "tok")]


def test_run_android_lowcode_lease_and_precheck_failures(monkeypatch):
    from app.schemas.android_precheck import PrecheckStatus

    device = types.SimpleNamespace(id=42, serial="S1")

    events, db, run, case = _install_android_run_env(
        monkeypatch, device=device, acquire_error=DeviceLeaseConflict("busy")
    )
    case.config = {"steps": [{"action": "click"}], "device_serial": "S1"}
    asyncio.run(ale.run_android_lowcode(db, run, case, {}))
    assert run.status == RunStatus.error and "设备租约冲突: busy" in run.error_message
    assert events.published[-1]["status"] == "error"

    events2, db2, run2, case2 = _install_android_run_env(
        monkeypatch, device=device, acquire_error=LookupError("missing")
    )
    case2.config = {"steps": [{"action": "click"}], "device_serial": "S1"}
    asyncio.run(ale.run_android_lowcode(db2, run2, case2, {}))
    assert "设备租约冲突: missing" in run2.error_message

    fail_item = types.SimpleNamespace(
        status=PrecheckStatus.FAIL, code="ADB_ENV", message="adb 不可用", suggestion="检查 adb"
    )
    events3, db3, run3, case3 = _install_android_run_env(
        monkeypatch, device=device, precheck=types.SimpleNamespace(ok=False, items=[fail_item])
    )
    case3.config = {"steps": [{"action": "click"}], "device_serial": "S1"}
    asyncio.run(ale.run_android_lowcode(db3, run3, case3, {}))
    assert run3.error_message == "执行前预检失败 [ADB_ENV]: adb 不可用 (建议: 检查 adb)"
    assert events3.steps_calls == []

    _events4, _db4, run4, case4 = _install_android_run_env(
        monkeypatch, device=device, precheck=types.SimpleNamespace(ok=False, items=[])
    )
    case4.config = {"steps": [{"action": "click"}], "device_serial": "S1"}
    asyncio.run(ale.run_android_lowcode(_db4, run4, case4, {}))
    assert run4.error_message == "执行前预检未通过"


def _android_steps_env(monkeypatch, config):
    events = types.SimpleNamespace(published=[], matrix_calls=[])
    db = _DeviceDB()
    run = types.SimpleNamespace(
        id=99, status=RunStatus.running, error_message=None, duration_ms=None, result_summary=None, triggered_by=1
    )
    case = types.SimpleNamespace(id=7, module_id=22, config=config)

    async def _publish(run_id, payload):
        events.published.append(payload)

    async def _matrix(db_arg, run_arg, case_arg, extra):
        events.matrix_calls.append(case_arg)
        run_arg.status = RunStatus.passed

    monkeypatch.setattr(ale, "publish_run_event", _publish)
    monkeypatch.setattr(ale, "_run_android_device_matrix", _matrix)
    return events, db, run, case


def test_run_android_lowcode_steps_delegates_to_matrix(monkeypatch):
    events, db, run, case = _android_steps_env(monkeypatch, {"steps": [{"action": "click"}], "device_matrix": ["S1"]})
    asyncio.run(ale._run_android_lowcode_steps(db, run, case, {}))
    assert len(events.matrix_calls) == 1
    assert run.status == RunStatus.passed


def test_run_android_lowcode_steps_requires_steps_and_device(monkeypatch):
    events, db, run, case = _android_steps_env(monkeypatch, {"steps": []})
    asyncio.run(ale._run_android_lowcode_steps(db, run, case, {}))
    assert run.status == RunStatus.error and run.error_message == "低代码用例未配置任何步骤"

    events2, db2, run2, case2 = _android_steps_env(monkeypatch, {"steps": [{"action": "click"}]})
    asyncio.run(ale._run_android_lowcode_steps(db2, run2, case2, {}))
    assert run2.status == RunStatus.error and run2.error_message == "未选择执行设备"


def test_run_android_lowcode_steps_apk_error_paths(monkeypatch):
    events, db, run, case = _android_steps_env(monkeypatch, {"steps": [{"action": "click"}], "device_serial": "S1"})

    async def _resolve_raise(db_arg, case_arg, cfg_arg):
        raise LookupError("绑定的 APK 资产不存在")

    monkeypatch.setattr(ale, "_resolve_lowcode_apk", _resolve_raise)
    asyncio.run(ale._run_android_lowcode_steps(db, run, case, {}))
    assert run.status == RunStatus.error and run.error_message == "绑定的 APK 资产不存在"

    events2, db2, run2, case2 = _android_steps_env(monkeypatch, {"steps": [{"action": "click"}], "device_serial": "S1"})

    async def _resolve_ok(db_arg, case_arg, cfg_arg):
        return "apks/projects/5/a.apk", "com.a"

    async def _preflight_raise(**kwargs):
        raise AndroidPreflightError("install failed")

    monkeypatch.setattr(ale, "_resolve_lowcode_apk", _resolve_ok)
    monkeypatch.setattr(ale, "run_android_preflight", _preflight_raise)
    asyncio.run(ale._run_android_lowcode_steps(db2, run2, case2, {}))
    assert run2.status == RunStatus.error and run2.error_message == "Android APK 前置操作失败: install failed"

    events3, db3, run3, case3 = _android_steps_env(monkeypatch, {"steps": [{"action": "click"}], "device_serial": "S1"})
    preflight_calls = []

    async def _preflight_ok(**kwargs):
        preflight_calls.append(kwargs)
        return {"actions": [{"type": "install"}]}

    monkeypatch.setattr(ale, "_resolve_lowcode_apk", _resolve_ok)
    monkeypatch.setattr(ale, "run_android_preflight", _preflight_ok)

    def _execute_ok(serial, action, params):
        return {"success": True}

    async def _shot(serial, run_id, step_index):
        return None

    async def _artifact(serial, run_id, name, command, *, max_bytes=2_000_000):
        return None

    monkeypatch.setattr(ale, "_execute_step_sync", _execute_ok)
    monkeypatch.setattr(ale, "_take_screenshot", _shot)
    monkeypatch.setattr(ale, "_capture_android_text_artifact", _artifact)
    case3.config["collect_device_artifacts"] = False
    asyncio.run(ale._run_android_lowcode_steps(db3, run3, case3, {}))
    assert run3.status == RunStatus.passed
    assert preflight_calls[0]["serial"] == "S1"
    assert preflight_calls[0]["apk_object_name"] == "apks/projects/5/a.apk"
    assert events3.published[0]["type"] == "step_progress"


def _fast_android_steps(monkeypatch):
    async def _resolve(db_arg, case_arg, cfg_arg):
        return None, None

    def _execute_ok(serial, action, params):
        return {"success": True}

    async def _shot(serial, run_id, step_index):
        return None

    async def _artifact(serial, run_id, name, command, *, max_bytes=2_000_000):
        return None

    monkeypatch.setattr(ale, "_resolve_lowcode_apk", _resolve)
    monkeypatch.setattr(ale, "_execute_step_sync", _execute_ok)
    monkeypatch.setattr(ale, "_take_screenshot", _shot)
    monkeypatch.setattr(ale, "_capture_android_text_artifact", _artifact)


_BASE_STEPS_CFG = {"steps": [{"action": "click"}], "device_serial": "S1", "collect_device_artifacts": False}


def test_run_android_lowcode_steps_recording_success(monkeypatch):
    events, db, run, case = _android_steps_env(monkeypatch, dict(_BASE_STEPS_CFG, record_video=True))
    _fast_android_steps(monkeypatch)
    started = []
    finished = []

    def _start(serial, remote_path, max_seconds):
        started.append((serial, remote_path, max_seconds))
        return object()

    async def _finish(serial, process, remote_path, run_id):
        finished.append((serial, remote_path, run_id))
        return "https://minio/android-artifacts/runs/99/screen-recording.mp4"

    monkeypatch.setattr(ale, "_start_screen_recording", _start)
    monkeypatch.setattr(ale, "_finish_screen_recording", _finish)
    asyncio.run(ale._run_android_lowcode_steps(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert len(started) == 1 and started[0][0] == "S1"
    assert finished and finished[0][0] == "S1" and finished[0][2] == 99
    assert run.result_summary["android_artifacts"]["screen_recording"] == (
        "https://minio/android-artifacts/runs/99/screen-recording.mp4"
    )


def test_run_android_lowcode_steps_recording_failure_paths(monkeypatch):
    events, db, run, case = _android_steps_env(monkeypatch, dict(_BASE_STEPS_CFG, record_video=True))
    _fast_android_steps(monkeypatch)

    def _start_none(serial, remote_path, max_seconds):
        return None

    monkeypatch.setattr(ale, "_start_screen_recording", _start_none)
    asyncio.run(ale._run_android_lowcode_steps(db, run, case, {}))
    assert run.result_summary["android_artifacts"]["screen_recording_error"] == "设备不支持或无法启动录屏"

    events2, db2, run2, case2 = _android_steps_env(monkeypatch, dict(_BASE_STEPS_CFG, record_video=True))
    _fast_android_steps(monkeypatch)

    async def _finish_none(serial, process, remote_path, run_id):
        return None

    monkeypatch.setattr(ale, "_start_screen_recording", lambda serial, remote_path, max_seconds: object())
    monkeypatch.setattr(ale, "_finish_screen_recording", _finish_none)
    asyncio.run(ale._run_android_lowcode_steps(db2, run2, case2, {}))
    assert run2.result_summary["android_artifacts"]["screen_recording_error"] == "设备未生成可上传的录屏文件"


def test_run_android_lowcode_steps_collector_failure(monkeypatch):
    events, db, run, case = _android_steps_env(monkeypatch, dict(_BASE_STEPS_CFG))
    _fast_android_steps(monkeypatch)

    class _BadCollector:
        def __init__(self, db_arg):
            self.db = db_arg

        async def add(self, item):
            raise RuntimeError("collector boom")

        async def flush(self):
            return None

    monkeypatch.setattr(ale, "StepResultBatchCollector", _BadCollector)
    asyncio.run(ale._run_android_lowcode_steps(db, run, case, {}))
    assert run.status == RunStatus.failed
    assert run.error_message == "collector boom"
    assert events.published[-1]["status"] == "failed"


def test_run_android_lowcode_steps_step_failure_breaks(monkeypatch):
    events, db, run, case = _android_steps_env(
        monkeypatch,
        {"steps": [{"action": "click"}, {"action": "click"}], "device_serial": "S1", "collect_device_artifacts": False},
    )
    _fast_android_steps(monkeypatch)
    results = [{"success": False, "error": "tap failed"}, {"success": True}]
    calls = []

    def _execute(serial, action, params):
        calls.append(action)
        return results[min(len(calls), len(results)) - 1]

    monkeypatch.setattr(ale, "_execute_step_sync", _execute)
    asyncio.run(ale._run_android_lowcode_steps(db, run, case, {}))
    assert len(calls) == 1
    assert run.status == RunStatus.failed
    assert len(db.added) == 1
    assert db.added[0].error_message == "tap failed"
    assert events.published[-1]["status"] == "failed"


class _MatrixDB:
    def __init__(self, devices=None):
        self.devices = devices or []
        self.added = []
        self.commits = 0
        self.refreshed = []
        self._next_id = 500

    async def execute(self, stmt):
        devices = self.devices
        return types.SimpleNamespace(scalars=lambda: types.SimpleNamespace(all=lambda: devices))

    def add(self, obj):
        self._next_id += 1
        obj.id = self._next_id
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshed.append(obj)


def _matrix_parent():
    run = types.SimpleNamespace(
        id=99,
        status=RunStatus.running,
        error_message=None,
        result_summary=None,
        triggered_by=1,
        trace_id="trace-1",
        environment=None,
    )
    case = types.SimpleNamespace(
        id=7, module_id=22, config={"device_matrix": ["S1", "S2"], "steps": [{"action": "click"}]}
    )
    return run, case


def _device(device_id, serial):
    return types.SimpleNamespace(
        id=device_id,
        serial=serial,
        model="m",
        brand="b",
        os_version="14",
        sdk_version=34,
        resolution="1080x1920",
    )


def test_run_android_device_matrix_rejects_unregistered_devices(monkeypatch):
    published = []

    async def _publish(run_id, payload):
        published.append(payload)

    monkeypatch.setattr(ale, "_safe_publish", _publish)
    db = _MatrixDB([_device(1, "S1")])
    run, case = _matrix_parent()
    asyncio.run(ale._run_android_device_matrix(db, run, case, {}))
    assert run.status == RunStatus.error
    assert run.error_message == "设备矩阵中包含未注册设备"
    assert run.result_summary["device_matrix_error"] == "设备矩阵中包含未注册设备"
    assert published[-1]["status"] == "error"


def test_run_android_device_matrix_aggregates_child_results(monkeypatch):
    published = []
    calls = []

    async def _publish(run_id, payload):
        published.append(payload)

    monkeypatch.setattr(ale, "_safe_publish", _publish)
    db = _MatrixDB([_device(1, "S1"), _device(2, "S2")])
    variants = [{"serial": "S1", "device_id": 1}, {"serial": "S2", "device_id": 2}]
    monkeypatch.setattr(ale, "build_android_device_matrix", lambda requested, available_devices: variants)

    async def _variant(**kwargs):
        calls.append(kwargs)
        status = "passed" if kwargs["index"] == 0 else "failed"
        return {
            "run_id": kwargs["child_id"],
            "index": kwargs["index"],
            "serial": kwargs["variant"]["serial"],
            "status": status,
            "duration_ms": 5,
            "error": None,
        }

    monkeypatch.setattr(ale, "_run_android_device_matrix_variant", _variant)
    run, case = _matrix_parent()
    asyncio.run(ale._run_android_device_matrix(db, run, case, {}))
    assert run.status == RunStatus.failed
    assert run.result_summary["device_matrix_total"] == 2
    assert run.result_summary["device_matrix_passed"] == 1
    assert run.result_summary["device_matrix_failed"] == 1
    assert run.result_summary["device_matrix_error"] == 0
    assert [child.iteration_index for child in db.added] == [0, 1]
    assert [child.iteration_data for child in db.added] == variants
    assert all(child.parent_run_id == 99 for child in db.added)
    assert len(db.refreshed) == 2
    assert calls[0]["case_id"] == 7 and calls[0]["module_id"] == 22
    assert calls[0]["owner_id"] == 1 and calls[0]["base_config"] is case.config
    assert published[0]["type"] == "run_status"
    assert published[-1] == {"type": "completed", "run_id": 99, "status": "failed"}


def test_run_android_device_matrix_all_passed(monkeypatch):
    published = []

    async def _publish(run_id, payload):
        published.append(payload)

    monkeypatch.setattr(ale, "_safe_publish", _publish)
    db = _MatrixDB([_device(1, "S1")])
    monkeypatch.setattr(
        ale, "build_android_device_matrix", lambda requested, available_devices: [{"serial": "S1", "device_id": 1}]
    )

    async def _variant(**kwargs):
        return {
            "run_id": kwargs["child_id"],
            "index": 0,
            "serial": "S1",
            "status": "passed",
            "duration_ms": 1,
            "error": None,
        }

    monkeypatch.setattr(ale, "_run_android_device_matrix_variant", _variant)
    run, case = _matrix_parent()
    case.config["device_matrix"] = ["S1"]
    asyncio.run(ale._run_android_device_matrix(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert run.result_summary["device_matrix_results"][0]["status"] == "passed"
    assert published[-1]["status"] == "passed"


class _ChildSession:
    def __init__(self, child):
        self.child = child
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, model, pk):
        return self.child

    async def commit(self):
        self.commits += 1

    def add(self, obj):
        pass


def _variant_child(child_id=41):
    return types.SimpleNamespace(id=child_id, status=RunStatus.error, duration_ms=None, error_message=None)


def test_run_android_device_matrix_variant_missing_child(monkeypatch):
    import app.core.database as app_db

    session = _ChildSession(None)
    monkeypatch.setattr(app_db, "AsyncSessionLocal", lambda: session, raising=False)
    result = asyncio.run(
        ale._run_android_device_matrix_variant(
            child_id=1,
            case_id=7,
            module_id=22,
            base_config={},
            extra_vars={},
            index=0,
            variant={"serial": "S1"},
            owner_id=1,
        )
    )
    assert result["error"] == "设备矩阵子运行不存在"
    assert result["status"] == RunStatus.error.value


def test_run_android_device_matrix_variant_lease_error_paths(monkeypatch):
    import app.core.database as app_db

    child = _variant_child()
    session = _ChildSession(child)
    monkeypatch.setattr(app_db, "AsyncSessionLocal", lambda: session, raising=False)
    result = asyncio.run(
        ale._run_android_device_matrix_variant(
            child_id=41,
            case_id=7,
            module_id=22,
            base_config={},
            extra_vars={},
            index=0,
            variant={"serial": "S1"},
            owner_id=1,
        )
    )
    assert child.error_message == "设备租约冲突: 设备 S1 缺少注册 ID"
    assert child.status == RunStatus.error
    assert result["error"] == child.error_message

    child2 = _variant_child(42)
    session2 = _ChildSession(child2)
    monkeypatch.setattr(app_db, "AsyncSessionLocal", lambda: session2, raising=False)

    async def _acquire_conflict(*args, **kwargs):
        raise DeviceLeaseConflict("设备被占用")

    monkeypatch.setattr(ale, "acquire_device_lease", _acquire_conflict)
    result2 = asyncio.run(
        ale._run_android_device_matrix_variant(
            child_id=42,
            case_id=7,
            module_id=22,
            base_config={},
            extra_vars={},
            index=0,
            variant={"serial": "S1", "device_id": 3},
            owner_id=1,
        )
    )
    assert child2.error_message == "设备租约冲突: 设备被占用"
    assert result2["error"] == child2.error_message

    child3 = _variant_child(43)
    session3 = _ChildSession(child3)
    monkeypatch.setattr(app_db, "AsyncSessionLocal", lambda: session3, raising=False)
    released = []

    async def _acquire_ok(*args, **kwargs):
        return types.SimpleNamespace(lease_token="tok")

    async def _steps_boom(*args, **kwargs):
        raise RuntimeError("variant boom")

    async def _release_ok(db_arg, device_id, token):
        released.append((device_id, token))

    monkeypatch.setattr(ale, "acquire_device_lease", _acquire_ok)
    monkeypatch.setattr(ale, "_run_android_lowcode_steps", _steps_boom)
    monkeypatch.setattr(ale, "release_device_lease", _release_ok)
    result3 = asyncio.run(
        ale._run_android_device_matrix_variant(
            child_id=43,
            case_id=7,
            module_id=22,
            base_config={},
            extra_vars={},
            index=0,
            variant={"serial": "S1", "device_id": 3},
            owner_id=1,
        )
    )
    assert child3.error_message == "variant boom"
    assert result3["error"] == "variant boom"
    assert released == [(3, "tok")]


def test_run_android_device_matrix_variant_success_config(monkeypatch):
    import app.core.database as app_db

    child = _variant_child()
    session = _ChildSession(child)
    monkeypatch.setattr(app_db, "AsyncSessionLocal", lambda: session, raising=False)
    seen = {}

    async def _acquire(db_arg, device_id, *, owner_id=None, owner_label=None, ttl_seconds=900):
        seen["lease"] = (device_id, owner_id, owner_label, ttl_seconds)
        return types.SimpleNamespace(lease_token="tok")

    async def _steps(db_arg, child_run, child_case, extra, **_kwargs):
        seen["case"] = child_case
        child_run.status = RunStatus.passed
        child_run.duration_ms = 12

    released = []

    async def _release_boom(db_arg, device_id, token):
        released.append((device_id, token))
        raise RuntimeError("release boom")

    monkeypatch.setattr(ale, "acquire_device_lease", _acquire)
    monkeypatch.setattr(ale, "_run_android_lowcode_steps", _steps)
    monkeypatch.setattr(ale, "release_device_lease", _release_boom)
    result = asyncio.run(
        ale._run_android_device_matrix_variant(
            child_id=41,
            case_id=7,
            module_id=22,
            base_config={"steps": [{"action": "click"}], "device_matrix": ["S1"], "device_lease_ttl_seconds": 100},
            extra_vars={"K": "V"},
            index=1,
            variant={"serial": "S1", "device_id": 3},
            owner_id=1,
        )
    )
    assert result["status"] == "passed"
    assert result["duration_ms"] == 12
    assert released == [(3, "tok")]
    cfg = seen["case"].config
    assert cfg["device_serial"] == "S1"
    assert cfg["_device_matrix_variant"] is True
    assert "device_matrix" not in cfg
    assert seen["lease"] == (3, 1, "case-run:41", 900)


def test_replace_vars_in_params_and_safe_publish(monkeypatch):
    params = {"a": "{{X}}-{{MISS}}", "b": {"c": "{{X}}"}, "d": 5}
    assert ale._replace_vars_in_params(params, {"X": "1"}) == {"a": "1-{{MISS}}", "b": {"c": "1"}, "d": 5}
    assert params == {"a": "{{X}}-{{MISS}}", "b": {"c": "{{X}}"}, "d": 5}

    async def _boom(run_id, payload):
        raise RuntimeError("redis down")

    monkeypatch.setattr(ale, "publish_run_event", _boom)
    asyncio.run(ale._safe_publish(1, {"type": "x"}))


def test_adb_cmd_real_body(monkeypatch):
    def _result(returncode, stdout, stderr=b""):
        return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(ale.subprocess, "run", lambda cmd, **kw: _result(0, b"out\n", b"err\n"))
    assert ale._adb_cmd("S1", "shell", "echo") == (True, "out\nerr")

    monkeypatch.setattr(ale.subprocess, "run", lambda cmd, **kw: _result(0, "text-out", "text-err"))
    assert ale._adb_cmd("S1", "shell", "echo") == (True, "text-outtext-err")

    monkeypatch.setattr(ale.subprocess, "run", lambda cmd, **kw: _result(1, b"", b"fail"))
    assert ale._adb_cmd("S1", "bad") == (False, "fail")

    def _timeout(cmd, **kw):
        raise ale.subprocess.TimeoutExpired(cmd, 15)

    monkeypatch.setattr(ale.subprocess, "run", _timeout)
    assert ale._adb_cmd("S1", "slow") == (False, "命令超时")

    def _boom(cmd, **kw):
        raise OSError("adb missing")

    monkeypatch.setattr(ale.subprocess, "run", _boom)
    assert ale._adb_cmd("S1", "x") == (False, "adb missing")


def test_adb_screenshot_and_take_screenshot_real_body(monkeypatch):
    monkeypatch.setattr(
        ale.subprocess, "run", lambda cmd, **kw: types.SimpleNamespace(returncode=0, stdout=b"PNG", stderr=b"")
    )
    assert ale._adb_screenshot("S1") == b"PNG"

    monkeypatch.setattr(
        ale.subprocess, "run", lambda cmd, **kw: types.SimpleNamespace(returncode=1, stdout=b"PNG", stderr=b"")
    )
    assert ale._adb_screenshot("S1") is None

    def _boom(cmd, **kw):
        raise OSError("adb gone")

    monkeypatch.setattr(ale.subprocess, "run", _boom)
    assert ale._adb_screenshot("S1") is None

    uploaded = []
    monkeypatch.setattr(ale, "_adb_screenshot", lambda serial: b"PNG")
    monkeypatch.setattr(ale, "upload_bytes", lambda name, data, ct: uploaded.append((name, data, ct)))
    monkeypatch.setattr(ale, "presigned_url", lambda name, expires_seconds=None: f"https://minio/{name}")
    url = asyncio.run(ale._take_screenshot("S1", 9, 0))
    assert url == "https://minio/screenshots/runs/9/step_0.png"
    assert uploaded == [("screenshots/runs/9/step_0.png", b"PNG", "image/png")]

    monkeypatch.setattr(ale, "_adb_screenshot", lambda serial: None)
    assert asyncio.run(ale._take_screenshot("S1", 9, 1)) is None

    def _upload_boom(name, data, ct):
        raise RuntimeError("minio down")

    monkeypatch.setattr(ale, "_adb_screenshot", lambda serial: b"PNG")
    monkeypatch.setattr(ale, "upload_bytes", _upload_boom)
    assert asyncio.run(ale._take_screenshot("S1", 9, 2)) is None


def test_run_android_lowcode_steps_collects_device_artifacts_by_default(monkeypatch):
    events, db, run, case = _android_steps_env(monkeypatch, {"steps": [{"action": "click"}], "device_serial": "S1"})
    _fast_android_steps(monkeypatch)
    calls = []

    async def _artifact(serial, run_id, name, command, *, max_bytes=2_000_000):
        calls.append((name, command))
        return f"https://minio/android-artifacts/runs/{run_id}/{name}.txt"

    monkeypatch.setattr(ale, "_capture_android_text_artifact", _artifact)
    asyncio.run(ale._run_android_lowcode_steps(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert calls == [
        ("device-info", ("shell", "getprop")),
        ("logcat", ("shell", "logcat", "-d", "-v", "time", "-t", "10000")),
    ]
    artifacts = run.result_summary["android_artifacts"]
    assert artifacts["device_info"] == "https://minio/android-artifacts/runs/99/device-info.txt"
    assert artifacts["logcat"] == "https://minio/android-artifacts/runs/99/logcat.txt"

    events2, db2, run2, case2 = _android_steps_env(monkeypatch, {"steps": [{"action": "click"}], "device_serial": "S1"})
    _fast_android_steps(monkeypatch)
    asyncio.run(ale._run_android_lowcode_steps(db2, run2, case2, {}))
    assert run2.result_summary["android_artifacts"] == {}


def test_uiautomator_dump_fallback_paths(monkeypatch):
    seq = [(True, "plain"), (True, "dumped"), (True, "<hierarchy>x</hierarchy>")]
    monkeypatch.setattr(ale, "_adb_cmd", lambda serial, *args, **kwargs: seq.pop(0))
    assert ale._uiautomator_dump("S1") == (True, "<hierarchy>x</hierarchy>")

    seq2 = [(False, ""), (False, "dump failed")]
    monkeypatch.setattr(ale, "_adb_cmd", lambda serial, *args, **kwargs: seq2.pop(0))
    assert ale._uiautomator_dump("S1") == (False, "dump failed")


def test_find_ui_center_paths(monkeypatch):
    assert ale._find_ui_center("S1", ()) is None

    monkeypatch.setattr(ale, "_uiautomator_dump", lambda serial, timeout=10: (False, "boom"))
    assert ale._find_ui_center("S1", (("text", "A"),)) is None

    monkeypatch.setattr(ale, "_uiautomator_dump", lambda serial, timeout=10: (True, "dump"))
    lookups = []

    def _bounds(dump, attribute, value):
        lookups.append((attribute, value))
        return (10, 20, 30, 40) if value == "B" else None

    monkeypatch.setattr(ale, "_find_ui_bounds", _bounds)
    assert ale._find_ui_center("S1", (("text", "A"), ("resource-id", "B"))) == (20, 30)
    assert lookups == [("text", "A"), ("resource-id", "B")]

    monkeypatch.setattr(ale, "_find_ui_bounds", lambda dump, attribute, value: None)
    assert ale._find_ui_center("S1", (("text", "A"),)) is None


def test_clear_input_text_stops_on_failure(monkeypatch):
    calls = []

    def _adb(serial, *args, **kwargs):
        calls.append(args)
        return (True, "") if len(calls) == 1 else (False, "")

    monkeypatch.setattr(ale, "_adb_cmd", _adb)
    ale._clear_input_text("S1", max_delete=5)
    assert len(calls) == 2
    assert calls[0] == ("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    assert calls[1] == ("shell", "input", "keyevent", "67")

    ok_calls = []
    monkeypatch.setattr(ale, "_adb_cmd", lambda serial, *args, **kwargs: ok_calls.append(args) or (True, ""))
    ale._clear_input_text("S1", max_delete=3)
    assert len(ok_calls) == 4


def test_uiautomator_dump_direct_hierarchy(monkeypatch):
    monkeypatch.setattr(ale, "_adb_cmd", lambda *args, **kwargs: (True, "<hierarchy>直接返回</hierarchy>"))
    assert ale._uiautomator_dump("S1") == (True, "<hierarchy>直接返回</hierarchy>")


def test_find_ui_bounds_fallback_edges():
    assert ale._find_ui_bounds("no markup", "text", "OK") is None
    two_nodes = '<hierarchy><node text="OK" bounds="bad"/><node text="OK" bounds="[5,6][7,8]"/></hierarchy>'
    assert ale._find_ui_bounds(two_nodes, "text", "OK") == (5, 6, 7, 8)


def test_find_and_click_coordinate_fallback_with_selectors(monkeypatch):
    monkeypatch.setattr(ale, "_adb_cmd", _AdbRecorder((True, "ok")))
    monkeypatch.setattr(ale, "_find_ui_center", lambda serial, selectors: None)
    result = ale._find_and_click("S1", {"text": "登录", "x": 10, "y": 20})
    assert result["success"] is True


def test_execute_step_sync_click_dispatch_and_input_target_failure(monkeypatch):
    seen = []
    monkeypatch.setattr(ale, "_find_and_click", lambda serial, params: seen.append(params) or {"success": True})
    assert ale._execute_step_sync("S1", "click", {"text": "A"}) == {"success": True}
    assert seen == [{"text": "A"}]

    monkeypatch.setattr(
        ale, "_find_and_click", lambda serial, params: {"success": False, "error": "未找到文本元素: 用户名"}
    )
    result = ale._execute_step_sync("S1", "input", {"text": "hi", "targetText": "用户名"})
    assert result == {"success": False, "error": "未找到文本元素: 用户名"}


def test_resolve_lowcode_apk_no_module_with_apk_id():
    case_no_module = types.SimpleNamespace(id=7)
    apk = types.SimpleNamespace(project_id=5, object_name="apks/projects/5/a.apk", package_name="com.a")
    object_name, package = asyncio.run(
        ale._resolve_lowcode_apk(_ApkDB(module=None, apk=apk), case_no_module, {"apk_id": 3})
    )
    assert (object_name, package) == ("apks/projects/5/a.apk", "com.a")


def test_run_android_lowcode_steps_execute_exception(monkeypatch):
    events, db, run, case = _android_steps_env(
        monkeypatch, {"steps": [{"action": "click"}], "device_serial": "S1", "collect_device_artifacts": False}
    )
    _fast_android_steps(monkeypatch)

    def _boom(serial, action, params):
        raise RuntimeError("adb exploded")

    monkeypatch.setattr(ale, "_execute_step_sync", _boom)
    asyncio.run(ale._run_android_lowcode_steps(db, run, case, {}))
    assert run.status == RunStatus.failed
    assert db.added[0].error_message == "adb exploded"
    assert events.published[-1]["status"] == "failed"


def test_finish_screen_recording_kill_and_cleanup_failures(monkeypatch):
    class _KillBoom(_RecProcess):
        def kill(self):
            self.killed = True
            raise OSError("kill failed")

    _install_recording_env(monkeypatch)
    boom = _KillBoom(terminate_error=RuntimeError("no term"))
    result = asyncio.run(ale._finish_screen_recording("S1", boom, "/sdcard/a.mp4", 9))
    assert result == "https://minio/android-artifacts/runs/9/screen-recording.mp4"
    assert boom.killed is True

    events2, process = _install_recording_env(monkeypatch)

    def fake_run(cmd, **kwargs):
        if "rm" in cmd:
            raise OSError("rm failed")
        if "pull" in cmd:
            Path(cmd[-1]).write_bytes(b"mp4-data")
            return types.SimpleNamespace(returncode=0)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(ale.subprocess, "run", fake_run)
    result = asyncio.run(ale._finish_screen_recording("S1", process, "/sdcard/a.mp4", 9))
    assert result == "https://minio/android-artifacts/runs/9/screen-recording.mp4"


def test_finish_screen_recording_unlink_failure(monkeypatch):
    events, process = _install_recording_env(monkeypatch)

    class _BoomPath(Path):
        def unlink(self, *args, **kwargs):
            raise OSError("locked")

    monkeypatch.setattr(ale, "Path", _BoomPath)
    url = asyncio.run(ale._finish_screen_recording("S1", process, "/sdcard/a.mp4", 6))
    assert url == "https://minio/android-artifacts/runs/6/screen-recording.mp4"
    assert events.uploads[0][0] == "android-artifacts/runs/6/screen-recording.mp4"
