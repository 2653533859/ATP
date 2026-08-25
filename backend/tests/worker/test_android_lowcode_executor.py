import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules.setdefault(
    "app.core.minio_client",
    types.SimpleNamespace(
        ensure_bucket=lambda: None,
        upload_bytes=lambda *args, **kwargs: None,
        upload_file=lambda *args, **kwargs: None,
        presigned_url=lambda *args, **kwargs: "",
        delete_file=lambda *args, **kwargs: None,
    ),
)
sys.modules.setdefault(
    "app.core.redis_client",
    types.SimpleNamespace(
        publish_run_event=lambda *args, **kwargs: None,
        get_json_cache=lambda *args, **kwargs: None,
        set_json_cache=lambda *args, **kwargs: None,
        delete_json_cache=lambda *args, **kwargs: None,
        delete_json_cache_pattern=lambda *args, **kwargs: None,
    ),
)

from app.worker.executors import android_lowcode_executor as executor


def test_input_clear_sends_repeated_delete_keyevents(monkeypatch):
    calls: list[tuple] = []

    def fake_adb_cmd(serial: str, *args: str, timeout: int = 15):
        calls.append((serial, args, timeout))
        return True, ""

    monkeypatch.setattr(executor, "_adb_cmd", fake_adb_cmd)

    result = executor._execute_step_sync(
        "serial-1",
        "input",
        {"text": "hello", "clear": True},
    )

    assert result["success"] is True

    delete_calls = [args for serial, args, _ in calls if args[:4] == ("shell", "input", "keyevent", "67")]
    assert len(delete_calls) == 50
    assert all(args[3] == "67" for args in delete_calls)
    assert all("--longpress" not in args for _, args, _ in calls)


# ── 变量替换 ────────────────────────────────────────────────


def test_replace_vars_and_recursion():
    ctx = {"PKG": "com.acme", "N": "3"}
    assert executor._replace_vars("{{PKG}}.app", ctx) == "com.acme.app"
    assert executor._replace_vars("{{MISSING}}", ctx) == "{{MISSING}}"
    result = executor._replace_vars_in_params(
        {"package": "{{PKG}}", "nested": {"n": "{{N}}", "raw": 9}, "b": True}, ctx
    )
    assert result == {"package": "com.acme", "nested": {"n": "3", "raw": 9}, "b": True}


@pytest.fixture()
def adb(monkeypatch):
    """替换 _adb_cmd：记录 adb 参数，按 responses 脚本化返回 (ok, output)，默认成功。"""
    recorder = {"calls": [], "responses": []}

    def fake_adb(serial, *args, timeout=15):
        recorder["calls"].append(args)
        if recorder["responses"]:
            return recorder["responses"].pop(0)
        return True, ""

    monkeypatch.setattr(executor, "_adb_cmd", fake_adb)
    return recorder


def _run(action, **params):
    return executor._execute_step_sync("emulator-5554", action, params)


# ── 坐标类动作 ──────────────────────────────────────────────


def test_click_by_coordinates(adb):
    assert _run("click", x=100, y=200) == {"success": True, "error": None}
    assert ("shell", "input", "tap", "100", "200") in adb["calls"]


def test_click_without_target_fails(adb):
    assert _run("click")["success"] is False


def test_long_click_by_coordinates_uses_swipe(adb):
    assert _run("long_click", x=50, y=60, duration=800) == {"success": True, "error": None}
    assert ("shell", "input", "swipe", "50", "60", "50", "60", "800") in adb["calls"]


def test_long_click_without_coordinates_errors(adb):
    assert _run("long_click")["success"] is False


def test_swipe_direction_unknown_and_custom(adb):
    assert _run("swipe", direction="up") == {"success": True, "error": None}
    assert ("shell", "input", "swipe", "540", "1600", "540", "400", "300") in adb["calls"]
    assert _run("swipe", direction="diagonal")["success"] is False
    _run("swipe", x1=10, y1=20, x2=30, y2=40, duration=500)
    assert ("shell", "input", "swipe", "10", "20", "30", "40", "500") in adb["calls"]
    assert _run("swipe")["success"] is False


# ── 屏幕尺寸与滑动缩放 ────────────────────────────────────────


def test_direction_swipe_uses_current_screen_size(adb):
    adb["responses"] = [(True, "Physical size: 1440x2560")]

    assert _run("swipe", direction="up") == {"success": True, "error": None}
    assert ("shell", "input", "swipe", "720", "2133", "720", "533", "300") in adb["calls"]


def test_recorded_swipe_scales_to_current_screen_size(adb):
    adb["responses"] = [(True, "Physical size: 2160x4800")]

    assert _run(
        "swipe",
        x1=100,
        y1=200,
        x2=100,
        y2=1000,
        duration=400,
        screenWidth=1080,
        screenHeight=2400,
    ) == {"success": True, "error": None}
    assert ("shell", "input", "swipe", "200", "400", "200", "2000", "400") in adb["calls"]


# ── 按键与应用 ──────────────────────────────────────────────


def test_press_key_maps_named_and_raw(adb):
    _run("press_key", key="back")
    assert ("shell", "input", "keyevent", "4") in adb["calls"]
    _run("press_key", key="99")
    assert ("shell", "input", "keyevent", "99") in adb["calls"]


def test_start_app_with_and_without_activity(adb):
    _run("start_app", package="com.acme", activity=".Main")
    assert ("shell", "am", "start", "-n", "com.acme/.Main") in adb["calls"]
    _run("start_app", package="com.acme")
    assert any(c[:2] == ("shell", "monkey") for c in adb["calls"])


def test_stop_app(adb):
    _run("stop_app", package="com.acme")
    assert ("shell", "am", "force-stop", "com.acme") in adb["calls"]


# ── 断言与其它 ──────────────────────────────────────────────


def test_assert_text_and_element(adb):
    adb["responses"] = [(True, '<hierarchy><node text="登录成功" /></hierarchy>')]
    assert _run("assert_text", text="登录成功")["success"] is True
    adb["responses"] = [(True, "<hierarchy><node /></hierarchy>")]
    assert _run("assert_text", text="缺失")["success"] is False

    adb["responses"] = [(True, '<hierarchy><node resource-id="com.acme:id/btn" /></hierarchy>')]
    assert _run("assert_element", resourceId="com.acme:id/btn")["success"] is True
    adb["responses"] = [(True, "<hierarchy><node /></hierarchy>")]
    assert _run("assert_element", resource_id="missing")["success"] is False


def test_wait_screenshot_and_unknown(monkeypatch, adb):
    slept = []
    monkeypatch.setattr(executor.time, "sleep", lambda s: slept.append(s))
    assert _run("wait", ms=300) == {"success": True}
    assert slept == [0.3]
    assert _run("screenshot") == {"success": True, "data": {"manual_screenshot": True}}
    result = _run("teleport")
    assert result["success"] is False and "未知操作类型" in result["error"]


# ── _adb_cmd / _adb_screenshot：subprocess 边界四分支 ────────

import asyncio  # noqa: E402
import subprocess  # noqa: E402


def test_adb_cmd_success_and_nonzero(monkeypatch):
    monkeypatch.setattr(
        executor.subprocess,
        "run",
        lambda *a, **kw: types.SimpleNamespace(returncode=0, stdout="ok\n", stderr=""),
    )
    assert executor._adb_cmd("s1", "shell", "echo") == (True, "ok")

    monkeypatch.setattr(
        executor.subprocess,
        "run",
        lambda *a, **kw: types.SimpleNamespace(returncode=1, stdout="", stderr="err"),
    )
    assert executor._adb_cmd("s1", "shell", "echo") == (False, "err")


def test_adb_cmd_timeout_and_generic_error(monkeypatch):
    def raise_timeout(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="adb", timeout=15)

    monkeypatch.setattr(executor.subprocess, "run", raise_timeout)
    assert executor._adb_cmd("s1", "shell", "echo") == (False, "命令超时")

    def raise_generic(*_a, **_kw):
        raise OSError("adb missing")

    monkeypatch.setattr(executor.subprocess, "run", raise_generic)
    ok, out = executor._adb_cmd("s1", "shell", "echo")
    assert ok is False and "adb missing" in out


def test_adb_screenshot_three_states(monkeypatch):
    monkeypatch.setattr(
        executor.subprocess,
        "run",
        lambda *a, **kw: types.SimpleNamespace(returncode=0, stdout=b"png-bytes"),
    )
    assert executor._adb_screenshot("s1") == b"png-bytes"

    monkeypatch.setattr(
        executor.subprocess,
        "run",
        lambda *a, **kw: types.SimpleNamespace(returncode=1, stdout=b""),
    )
    assert executor._adb_screenshot("s1") is None

    def raise_err(*_a, **_kw):
        raise RuntimeError("device gone")

    monkeypatch.setattr(executor.subprocess, "run", raise_err)
    assert executor._adb_screenshot("s1") is None


def test_take_screenshot_upload_and_fallbacks(monkeypatch):
    uploads = []
    monkeypatch.setattr(executor, "_adb_screenshot", lambda serial: b"png")
    monkeypatch.setattr(executor, "upload_bytes", lambda name, data, ct: uploads.append((name, ct)))
    monkeypatch.setattr(executor, "presigned_url", lambda name: f"https://minio/{name}")

    url = asyncio.run(executor._take_screenshot("s1", 7, 2))
    assert url == "https://minio/screenshots/runs/7/step_2.png"
    assert uploads == [("screenshots/runs/7/step_2.png", "image/png")]

    # 截图无数据 → None，不上传
    monkeypatch.setattr(executor, "_adb_screenshot", lambda serial: None)
    assert asyncio.run(executor._take_screenshot("s1", 7, 3)) is None

    # 上传抛异常 → 吞掉返回 None
    monkeypatch.setattr(executor, "_adb_screenshot", lambda serial: b"png")

    def broken_upload(*_a):
        raise RuntimeError("minio down")

    monkeypatch.setattr(executor, "upload_bytes", broken_upload)
    assert asyncio.run(executor._take_screenshot("s1", 7, 4)) is None


def test_safe_publish_swallows_errors(monkeypatch):
    async def broken(run_id, payload):
        raise RuntimeError("redis down")

    monkeypatch.setattr(executor, "publish_run_event", broken)
    asyncio.run(executor._safe_publish(1, {"type": "x"}))  # 不抛异常即通过


def test_clear_input_text_stops_on_first_failure(adb):
    adb["responses"] = [(True, ""), (True, ""), (False, "")]  # MOVE_END、一次 DEL 成功、第二次失败
    executor._clear_input_text("s1")
    delete_calls = [c for c in adb["calls"] if c[:3] == ("shell", "input", "keyevent") and c[3] == "67"]
    assert len(delete_calls) == 2  # 失败即 break，不再发满 50 次


# ── _find_and_click：text / resourceId 的 dump 解析路径 ─────

_DUMP_TEXT = '<hierarchy><node bounds="[100,200][300,400]" text="登录" /></hierarchy>'
_DUMP_RID = '<hierarchy><node resource-id="com.acme:id/btn" bounds="[10,20][30,40]" /></hierarchy>'


def test_uiautomator_dump_falls_back_to_remote_file(adb):
    adb["responses"] = [(True, "UI hierchary dumped to: /dev/tty"), (True, "dumped"), (True, _DUMP_TEXT)]

    ok, dump = executor._uiautomator_dump("s1")

    assert ok is True
    assert dump == _DUMP_TEXT
    assert ("shell", "uiautomator", "dump", "/sdcard/atp-ui-hierarchy.xml") in adb["calls"]
    assert ("shell", "cat", "/sdcard/atp-ui-hierarchy.xml") in adb["calls"]


def test_find_and_click_by_text_via_dump_fallback(adb):
    # UIAutomator dump 解析 bounds → 中心点 tap
    adb["responses"] = [(True, _DUMP_TEXT), (True, "")]
    assert executor._find_and_click("s1", {"text": "登录"}) == {"success": True, "error": None}
    assert ("shell", "input", "tap", "200", "300") in adb["calls"]  # (100+300)/2, (200+400)/2


def test_find_and_click_by_text_reversed_attr_order(adb):
    dump = '<node text="Login" foo="1" bounds="[0,0][10,10]" />'
    adb["responses"] = [(True, f"<hierarchy>{dump}</hierarchy>"), (True, "")]
    assert executor._find_and_click("s1", {"text": "Login"})["success"] is True
    assert ("shell", "input", "tap", "5", "5") in adb["calls"]


def test_find_and_click_by_text_not_found(adb):
    adb["responses"] = [(True, ""), (False, ""), (True, "<node text='其它' />")]
    result = executor._find_and_click("s1", {"text": "登录"})
    assert result["success"] is False and "未找到文本元素" in result["error"]


def test_find_and_click_by_text_uses_dump_on_all_devices(adb):
    adb["responses"] = [(True, _DUMP_TEXT), (True, "")]
    assert executor._find_and_click("s1", {"text": "登录"}) == {"success": True, "error": None}
    assert ("shell", "input", "tap", "200", "300") in adb["calls"]


def test_find_and_click_by_resource_id(adb):
    adb["responses"] = [(True, _DUMP_RID), (True, "")]
    assert executor._find_and_click("s1", {"resourceId": "com.acme:id/btn"}) == {"success": True, "error": None}
    assert ("shell", "input", "tap", "20", "30") in adb["calls"]

    adb["responses"] = [(True, "<node/>")]
    result = executor._find_and_click("s1", {"resource_id": "missing"})
    assert result["success"] is False and "未找到元素" in result["error"]


def test_find_and_click_prefers_resource_id_when_both_locators_are_recorded(adb):
    adb["responses"] = [(True, _DUMP_RID), (True, "")]

    assert executor._find_and_click(
        "s1",
        {"text": "登录", "resourceId": "com.acme:id/btn"},
    ) == {"success": True, "error": None}
    assert ("shell", "input", "tap", "20", "30") in adb["calls"]


def test_find_and_click_prefers_recorded_locator_over_coordinate_fallback(adb):
    adb["responses"] = [(True, _DUMP_RID), (True, "")]

    result = executor._find_and_click(
        "s1",
        {"resourceId": "com.acme:id/btn", "x": 900, "y": 1000},
    )

    assert result == {"success": True, "error": None}
    assert ("shell", "input", "tap", "20", "30") in adb["calls"]
    assert ("shell", "input", "tap", "900", "1000") not in adb["calls"]


def test_find_and_click_falls_back_to_recorded_coordinate(adb):
    adb["responses"] = [(True, _DUMP_RID), (True, "")]

    result = executor._find_and_click(
        "s1",
        {"resourceId": "com.acme:id/missing", "x": 900, "y": 1000},
    )

    assert result == {"success": True, "error": None}
    assert ("shell", "input", "tap", "900", "1000") in adb["calls"]


def test_find_and_click_by_content_description(adb):
    dump = '<hierarchy><node content-desc="打开菜单" bounds="[0,0][80,80]" /></hierarchy>'
    adb["responses"] = [(True, dump), (True, "")]

    assert executor._find_and_click("s1", {"contentDesc": "打开菜单"}) == {"success": True, "error": None}
    assert ("shell", "input", "tap", "40", "40") in adb["calls"]


def test_long_click_by_text_delegates_to_find_and_click(adb):
    adb["responses"] = [(True, _DUMP_TEXT), (True, "")]
    assert _run("long_click", text="登录") == {"success": True, "error": None}


def test_long_click_by_resource_id_uses_center_and_duration(adb):
    adb["responses"] = [(True, _DUMP_RID), (True, "")]

    result = _run("long_click", resourceId="com.acme:id/btn", duration=1200)

    assert result == {"success": True, "error": None}
    assert ("shell", "input", "swipe", "20", "30", "20", "30", "1200") in adb["calls"]


def test_input_with_resource_id_focuses_first(monkeypatch, adb):
    focused = []
    monkeypatch.setattr(executor, "_find_and_click", lambda serial, params: focused.append(params) or {"success": True})
    monkeypatch.setattr(executor.time, "sleep", lambda s: None)

    assert _run("input", text="hi there", resourceId="com.acme:id/edit")["success"] is True
    assert focused == [{"text": None, "resourceId": "com.acme:id/edit", "contentDesc": None}]
    assert ("shell", "input", "text", "hi%sthere") in adb["calls"]  # 空格转义为 %s


def test_input_uses_target_text_and_content_desc_for_focus(monkeypatch, adb):
    dump = '<hierarchy><node content-desc="账号输入框" bounds="[10,20][30,40]" /></hierarchy>'
    adb["responses"] = [(True, dump), (True, ""), (True, "")]
    monkeypatch.setattr(executor.time, "sleep", lambda s: None)

    result = _run("input", text="tester", contentDesc="账号输入框")

    assert result == {"success": True, "error": None}
    assert ("shell", "input", "tap", "20", "30") in adb["calls"]
    assert ("shell", "input", "text", "tester") in adb["calls"]


def test_input_does_not_type_when_target_locator_is_missing(monkeypatch, adb):
    adb["responses"] = [(True, _DUMP_RID)]
    monkeypatch.setattr(executor.time, "sleep", lambda s: None)

    result = _run("input", text="tester", resourceId="com.acme:id/missing")

    assert result["success"] is False
    assert not any(call[:3] == ("shell", "input", "text") for call in adb["calls"])


# ── run_android_lowcode 主执行链 ────────────────────────────

from app.models.bootstrap import load_all_models  # noqa: E402
from app.models.case import RunStatus, StepResult  # noqa: E402

load_all_models()


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def execute(self, _statement):
        class _ScalarResult:
            def scalar_one_or_none(self):
                return _Obj(id=41)

        return _ScalarResult()


@pytest.fixture()
def run_env(monkeypatch):
    """主链缝：脚本化 _execute_step_sync，记录截图与事件。"""
    events = []
    step_results = {"queue": [], "calls": []}

    async def fake_publish(run_id, payload):
        events.append(payload)

    def fake_step(serial, action, params):
        step_results["calls"].append((serial, action, params))
        if step_results["queue"]:
            item = step_results["queue"].pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return {"success": True}

    async def fake_screenshot(serial, run_id, idx):
        return f"https://minio/screenshots/runs/{run_id}/step_{idx}.png"

    monkeypatch.setattr(executor, "publish_run_event", fake_publish)
    monkeypatch.setattr(executor, "_execute_step_sync", fake_step)
    monkeypatch.setattr(executor, "_take_screenshot", fake_screenshot)

    async def fake_acquire(_db, _device_id, **_kwargs):
        return _Obj(lease_token="test-lease")

    async def fake_release(_db, _device_id, _token):
        return True

    monkeypatch.setattr(executor, "acquire_device_lease", fake_acquire)
    monkeypatch.setattr(executor, "release_device_lease", fake_release)
    return {"events": events, "steps": step_results}


def _run_case(steps, device_serial="emu-1"):
    cfg = {"steps": steps}
    if device_serial:
        cfg["device_serial"] = device_serial
    run = _Obj(id=7, status=RunStatus.running)
    case = _Obj(id=3, config=cfg)
    return run, case


def test_android_device_matrix_runs_children_in_parallel(monkeypatch):
    class _ScalarResult:
        def __init__(self, values):
            self.values = values

        def scalars(self):
            return self

        def all(self):
            return self.values

    class _MatrixDB(_FakeDB):
        async def execute(self, _statement):
            return _ScalarResult(
                [
                    _Obj(
                        id=41,
                        serial="emu-1",
                        model="Pixel 8",
                        brand="Google",
                        os_version="14",
                        sdk_version="34",
                        resolution="1080x2400",
                    ),
                    _Obj(
                        id=42,
                        serial="emu-2",
                        model="Pixel 7",
                        brand="Google",
                        os_version="13",
                        sdk_version="33",
                        resolution="1080x2400",
                    ),
                ]
            )

        async def refresh(self, _obj):
            return None

    active = 0
    max_active = 0

    async def fake_variant(**kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {
            "run_id": kwargs["child_id"],
            "index": kwargs["index"],
            "serial": kwargs["variant"]["serial"],
            "status": "passed",
            "duration_ms": 10,
            "error": None,
        }

    monkeypatch.setattr(executor, "_run_android_device_matrix_variant", fake_variant)

    parent = _Obj(id=100, status=RunStatus.running, triggered_by=7, environment=None, result_summary={})
    case = _Obj(id=3, config={"device_matrix": [{"serial": "emu-1"}, {"serial": "emu-2"}]})

    asyncio.run(executor._run_android_device_matrix(_MatrixDB(), parent, case, {}))

    assert max_active == 2
    assert parent.status == RunStatus.passed
    assert parent.result_summary["device_matrix_passed"] == 2


def test_android_device_matrix_variant_acquires_and_releases_own_lease(monkeypatch):
    import app.core.database as database

    child = _Obj(id=701, status=RunStatus.pending, duration_ms=12, error_message=None)

    class _ChildDB:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, _model, child_id):
            assert child_id == child.id
            return child

        async def commit(self):
            return None

    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: _ChildDB())
    leases = []
    releases = []

    async def acquire(_db, device_id, **kwargs):
        leases.append((device_id, kwargs["owner_label"]))
        return _Obj(lease_token="lease-1")

    async def release(_db, device_id, token):
        releases.append((device_id, token))
        return True

    async def fake_run(_db, child_run, _case, _extra_vars):
        child_run.status = RunStatus.passed

    monkeypatch.setattr(executor, "acquire_device_lease", acquire)
    monkeypatch.setattr(executor, "release_device_lease", release)
    monkeypatch.setattr(executor, "_run_android_lowcode_steps", fake_run)

    result = asyncio.run(
        executor._run_android_device_matrix_variant(
            child_id=child.id,
            case_id=3,
            base_config={"steps": [], "device_lease_ttl_seconds": 901},
            extra_vars={},
            index=0,
            variant={"serial": "emu-1", "device_id": 41},
            owner_id=7,
        )
    )

    assert result["status"] == "passed"
    assert leases == [(41, "case-run:701")]
    assert releases == [(41, "lease-1")]


def test_run_android_lowcode_no_steps_marks_error(run_env):
    db = _FakeDB()
    run, case = _run_case([])

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.error and "未配置任何步骤" in run.error_message
    assert run_env["events"][-1]["status"] == "error"


def test_run_android_lowcode_missing_device_marks_error(run_env):
    db = _FakeDB()
    run, case = _run_case([{"action": "wait", "params": {}}], device_serial=None)

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.error and "未选择执行设备" in run.error_message


def test_run_android_lowcode_acquires_and_releases_device_lease(run_env, monkeypatch):
    db = _FakeDB()
    run, case = _run_case([{"action": "wait", "params": {"ms": 1}}])
    calls = []

    async def acquire(_db, device_id, **kwargs):
        calls.append(("acquire", device_id, kwargs["owner_label"]))
        return _Obj(lease_token="lease-42")

    async def release(_db, device_id, token):
        calls.append(("release", device_id, token))
        return True

    monkeypatch.setattr(executor, "acquire_device_lease", acquire)
    monkeypatch.setattr(executor, "release_device_lease", release)

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.passed
    assert calls == [("acquire", 41, "case-run:7"), ("release", 41, "lease-42")]


def test_run_android_lowcode_lease_conflict_stops_before_steps(run_env, monkeypatch):
    db = _FakeDB()
    run, case = _run_case([{"action": "wait", "params": {"ms": 1}}])
    called = []

    async def acquire(_db, _device_id, **_kwargs):
        raise executor.DeviceLeaseConflict("设备已被其他任务占用")

    async def fake_steps(*_args):
        called.append(True)

    monkeypatch.setattr(executor, "acquire_device_lease", acquire)
    monkeypatch.setattr(executor, "_run_android_lowcode_steps", fake_steps)

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.error
    assert "设备租约冲突" in run.error_message
    assert called == []


def test_lowcode_selected_apk_is_project_scoped_and_installed(run_env, monkeypatch):
    from app.models.apk import Apk
    from app.models.project import Module

    class _ApkDB(_FakeDB):
        async def get(self, model, object_id):
            if model is Apk:
                assert object_id == 5
                return _Obj(project_id=12, object_name="apks/projects/12/demo.apk", package_name="com.demo")
            assert model is Module
            assert object_id == 9
            return _Obj(project_id=12)

    preflight_calls = []

    async def fake_preflight(**kwargs):
        preflight_calls.append(kwargs)
        return {"actions": ["install"], "package": kwargs["package"]}

    monkeypatch.setattr(executor, "run_android_preflight", fake_preflight)
    db = _ApkDB()
    run, case = _run_case([{"action": "wait", "params": {"ms": 1}}])
    case.module_id = 9
    case.config["apk_id"] = 5

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.passed
    assert preflight_calls[0]["apk_object_name"] == "apks/projects/12/demo.apk"
    assert preflight_calls[0]["package"] == "com.demo"
    assert preflight_calls[0]["config"]["install_apk"] is True


def test_lowcode_rejects_apk_from_another_project(run_env, monkeypatch):
    from app.models.apk import Apk

    class _CrossProjectDB(_FakeDB):
        async def get(self, model, _object_id):
            if model is Apk:
                return _Obj(project_id=99, object_name="apks/projects/99/other.apk", package_name="com.other")
            return _Obj(project_id=12)

    preflight_called = []

    async def fake_preflight(**_kwargs):
        preflight_called.append(True)
        return {"actions": ["install"]}

    monkeypatch.setattr(executor, "run_android_preflight", fake_preflight)
    db = _CrossProjectDB()
    run, case = _run_case([{"action": "wait", "params": {"ms": 1}}])
    case.module_id = 9
    case.config["apk_id"] = 5

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.error
    assert run.error_message == "APK 资产不属于用例所在项目"
    assert preflight_called == []


def test_lowcode_recording_start_failure_is_reported(run_env, monkeypatch):
    monkeypatch.setattr(executor, "_start_screen_recording", lambda *_args: None)
    db = _FakeDB()
    run, case = _run_case([{"action": "wait", "params": {}}])
    case.config["record_video"] = True
    case.config["collect_device_artifacts"] = False

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.passed
    assert run.result_summary["android_artifacts"] == {"screen_recording_error": "设备不支持或无法启动录屏"}


def test_run_android_lowcode_happy_path_publishes_steps(run_env):
    db = _FakeDB()
    run, case = _run_case(
        [
            {"action": "start_app", "name": "启动", "params": {"package": "{{PKG}}"}},
            {"action": "click", "params": {"text": "登录"}},
        ]
    )

    asyncio.run(executor.run_android_lowcode(db, run, case, {"PKG": "com.acme"}))

    assert run.status == RunStatus.passed and run.duration_ms is not None
    # 变量替换 + DEVICE_SERIAL 注入
    assert run_env["steps"]["calls"][0] == ("emu-1", "start_app", {"package": "com.acme"})
    rows = [o for o in db.added if isinstance(o, StepResult)]
    assert len(rows) == 2
    assert rows[0].name == "启动" and rows[1].name == "click_1"
    assert rows[0].screenshot_url.endswith("step_0.png")
    step_events = [e for e in run_env["events"] if e["type"] == "step_result"]
    assert len(step_events) == 2 and step_events[0]["step"]["status"] == "passed"
    assert run_env["events"][-1] == {
        "type": "completed",
        "run_id": 7,
        "status": "passed",
        "duration_ms": run.duration_ms,
    }


def test_run_android_lowcode_failed_step_stops(run_env):
    run_env["steps"]["queue"] = [{"success": False, "error": "元素不存在"}]
    db = _FakeDB()
    run, case = _run_case([{"action": "click", "params": {}}, {"action": "wait", "params": {}}])

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.failed
    rows = [o for o in db.added if isinstance(o, StepResult)]
    assert len(rows) == 1 and rows[0].error_message == "元素不存在"
    assert len(run_env["steps"]["calls"]) == 1  # 第二步未执行


def test_run_android_lowcode_step_exception_truncated(run_env):
    run_env["steps"]["queue"] = [RuntimeError("x" * 3000)]
    db = _FakeDB()
    run, case = _run_case([{"action": "click", "params": {}}])

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    rows = [o for o in db.added if isinstance(o, StepResult)]
    assert rows[0].status == RunStatus.failed and len(rows[0].error_message) == 2000
    assert run.status == RunStatus.failed and run_env["events"][-1]["status"] == "failed"
