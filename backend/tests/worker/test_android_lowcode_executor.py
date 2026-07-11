import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.minio_client"] = types.SimpleNamespace(
    ensure_bucket=lambda: None,
    upload_bytes=lambda *args, **kwargs: None,
    upload_file=lambda *args, **kwargs: None,
    presigned_url=lambda *args, **kwargs: "",
    delete_file=lambda *args, **kwargs: None,
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
    adb["responses"] = [(True, '<node text="登录成功" />')]
    assert _run("assert_text", text="登录成功")["success"] is True
    adb["responses"] = [(True, "<node/>")]
    assert _run("assert_text", text="缺失")["success"] is False

    adb["responses"] = [(True, 'resource-id="com.acme:id/btn"')]
    assert _run("assert_element", resourceId="com.acme:id/btn")["success"] is True
    adb["responses"] = [(True, "<node/>")]
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

_DUMP_TEXT = '<node bounds="[100,200][300,400]" text="登录" />'
_DUMP_RID = '<node resource-id="com.acme:id/btn" bounds="[10,20][30,40]" />'


def test_find_and_click_by_text_via_dump_fallback(adb):
    # 组合命令失败 → uiautomator dump 解析 bounds → 中心点 tap
    adb["responses"] = [(True, ""), (False, ""), (True, _DUMP_TEXT), (True, "")]
    assert executor._find_and_click("s1", {"text": "登录"}) == {"success": True, "error": None}
    assert ("shell", "input", "tap", "200", "300") in adb["calls"]  # (100+300)/2, (200+400)/2


def test_find_and_click_by_text_reversed_attr_order(adb):
    dump = '<node text="登录" foo="1" bounds="[0,0][10,10]" />'
    adb["responses"] = [(True, ""), (False, ""), (True, dump), (True, "")]
    assert executor._find_and_click("s1", {"text": "登录"})["success"] is True
    assert ("shell", "input", "tap", "5", "5") in adb["calls"]


def test_find_and_click_by_text_not_found(adb):
    adb["responses"] = [(True, ""), (False, ""), (True, "<node text='其它' />")]
    result = executor._find_and_click("s1", {"text": "登录"})
    assert result["success"] is False and "未找到文本元素" in result["error"]


def test_find_and_click_by_text_combined_command_succeeds(adb):
    adb["responses"] = [(True, ""), (True, "")]  # 组合命令直接成功，无需 dump
    assert executor._find_and_click("s1", {"text": "登录"}) == {"success": True}
    assert not any(c[:2] == ("shell", "uiautomator") for c in adb["calls"])


def test_find_and_click_by_resource_id(adb):
    adb["responses"] = [(True, _DUMP_RID), (True, "")]
    assert executor._find_and_click("s1", {"resourceId": "com.acme:id/btn"}) == {"success": True, "error": None}
    assert ("shell", "input", "tap", "20", "30") in adb["calls"]

    adb["responses"] = [(True, "<node/>")]
    result = executor._find_and_click("s1", {"resource_id": "missing"})
    assert result["success"] is False and "未找到元素" in result["error"]


def test_long_click_by_text_delegates_to_find_and_click(adb):
    adb["responses"] = [(True, ""), (True, "")]
    assert _run("long_click", text="登录") == {"success": True}


def test_input_with_resource_id_focuses_first(monkeypatch, adb):
    focused = []
    monkeypatch.setattr(executor, "_find_and_click", lambda serial, params: focused.append(params) or {"success": True})
    monkeypatch.setattr(executor.time, "sleep", lambda s: None)

    assert _run("input", text="hi there", resourceId="com.acme:id/edit")["success"] is True
    assert focused == [{"resourceId": "com.acme:id/edit"}]
    assert ("shell", "input", "text", "hi%sthere") in adb["calls"]  # 空格转义为 %s


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
    return {"events": events, "steps": step_results}


def _run_case(steps, device_serial="emu-1"):
    cfg = {"steps": steps}
    if device_serial:
        cfg["device_serial"] = device_serial
    run = _Obj(id=7, status=RunStatus.running)
    case = _Obj(id=3, config=cfg)
    return run, case


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
    run, case = _run_case(
        [{"action": "click", "params": {}}, {"action": "wait", "params": {}}]
    )

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
