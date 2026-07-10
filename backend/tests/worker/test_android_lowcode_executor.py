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
