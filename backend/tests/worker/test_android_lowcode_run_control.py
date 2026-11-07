"""Android 低代码执行控制：协作式取消、租约续期/失效、严格回放分派。"""

import asyncio
import types

import pytest

from app.models.bootstrap import load_all_models
from app.models.case import RunStatus, StepResult
from app.services.device_leases import DeviceLeaseConflict
from app.worker.executors import android_lowcode_executor as executor

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

    def steps(self):
        return [obj for obj in self.added if isinstance(obj, StepResult)]


@pytest.fixture()
def env(monkeypatch):
    state = {
        "cancelled": set(),
        "cleared": [],
        "heartbeats": [],
        "heartbeat_error": None,
        "calls": [],
        "events": [],
        "released": [],
        "on_step": None,
    }

    async def publish(_run_id, payload):
        state["events"].append(payload)

    def step(serial, action, params):
        state["calls"].append((action, params))
        if state["on_step"]:
            state["on_step"](action, params)
        return {"success": True}

    async def screenshot(*_args):
        return None

    async def acquire(_db, _device_id, **_kwargs):
        return _Obj(lease_token="lease-9")

    async def release(_db, device_id, token):
        state["released"].append((device_id, token))
        return True

    async def heartbeat(_db, device_id, token, **kwargs):
        if state["heartbeat_error"]:
            raise state["heartbeat_error"]
        state["heartbeats"].append((device_id, token, kwargs["ttl_seconds"]))
        return _Obj(lease_token=token)

    async def precheck(*_args, **_kwargs):
        return _Obj(ok=True)

    monkeypatch.setattr(executor, "publish_run_event", publish)
    monkeypatch.setattr(executor, "_execute_step_sync", step)
    monkeypatch.setattr(executor, "_take_screenshot", screenshot)
    monkeypatch.setattr(executor, "acquire_device_lease", acquire)
    monkeypatch.setattr(executor, "release_device_lease", release)
    monkeypatch.setattr(executor, "heartbeat_device_lease", heartbeat)
    monkeypatch.setattr(executor, "precheck_android_execution", precheck)
    monkeypatch.setattr(executor, "is_cancel_requested", lambda run_id: run_id in state["cancelled"])
    monkeypatch.setattr(executor, "clear_cancel_request", state["cleared"].append)
    monkeypatch.setattr(executor, "CANCEL_POLL_INTERVAL_SECONDS", 0)
    return state


def _case(steps, **cfg):
    run = _Obj(id=7, status=RunStatus.running)
    case = _Obj(id=3, config={"steps": steps, "device_serial": "emu-1", "collect_device_artifacts": False, **cfg})
    return run, case


CLICK = {"action": "click", "params": {"resourceId": "a:id/x"}}


def test_each_step_renews_lease_and_summary_reports_control(env):
    db = _FakeDB()
    run, case = _case([CLICK, CLICK], device_lease_ttl_seconds=1200)

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.passed
    assert env["heartbeats"] == [(41, "lease-9", 1200), (41, "lease-9", 1200)]
    assert env["released"] == [(41, "lease-9")] and env["cleared"] == [7]
    control = run.result_summary["execution_control"]
    assert control["lease_held"] is True and control["lease_heartbeats"] == 2
    assert control["executed_steps"] == 2 and control["cancelled"] is False


def test_cancel_between_steps_marks_run_cancelled_and_skips_rest(env):
    def on_step(_action, _params):
        env["cancelled"].add(7)

    env["on_step"] = on_step
    db = _FakeDB()
    run, case = _case([CLICK, CLICK, CLICK])

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.cancelled
    assert "停止于第 2 步" in run.error_message
    assert len(env["calls"]) == 1 and len(db.steps()) == 1
    assert env["released"] == [(41, "lease-9")] and env["cleared"] == [7]
    assert env["events"][-1]["type"] == "completed" and env["events"][-1]["status"] == "cancelled"


def test_cancel_during_long_wait_interrupts_slices(env):
    def on_step(action, _params):
        if action == "wait" and len(env["calls"]) == 2:
            env["cancelled"].add(7)

    env["on_step"] = on_step
    db = _FakeDB()
    run, case = _case([{"action": "wait", "params": {"ms": 5000}}, CLICK])

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.cancelled
    assert [call[1]["ms"] for call in env["calls"]] == [1000, 1000]
    step = db.steps()[0]
    assert step.status == RunStatus.cancelled and "本步骤未完成" in step.error_message


def test_cancel_before_any_write_never_touches_device(env):
    env["cancelled"].add(7)
    db = _FakeDB()
    run, case = _case([CLICK])

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.cancelled and env["calls"] == [] and db.steps() == []


def test_lease_renewal_failure_stops_with_error(env):
    env["heartbeat_error"] = DeviceLeaseConflict("设备租约不存在或已过期")
    db = _FakeDB()
    run, case = _case([CLICK, CLICK])

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.error and "设备租约已失效" in run.error_message
    assert env["calls"] == []
    assert run.result_summary["execution_control"]["lease_lost"] is True


def test_expired_local_lease_deadline_blocks_write(monkeypatch):
    control = executor.AndroidRunControl(1, device_id=2, lease_token="t", ttl_seconds=900)
    monkeypatch.setattr(executor, "is_cancel_requested", lambda _run_id: False)
    control._deadline = 0.0
    with pytest.raises(executor.AndroidLeaseLost):
        control.assert_write_allowed()
    # 未持有租约（直接调用步骤函数的旧路径）只做取消检查。
    executor.AndroidRunControl(1).assert_write_allowed()


def test_matrix_child_honours_parent_cancel(monkeypatch):
    seen = []
    monkeypatch.setattr(executor, "is_cancel_requested", lambda run_id: seen.append(run_id) or run_id == 50)
    control = executor.AndroidRunControl(51, cancel_run_ids=(50,))
    with pytest.raises(executor.AndroidRunCancelled):
        control.check_cancel()
    assert seen == [51, 50]


def test_wait_until_requires_strict_mode(env):
    db = _FakeDB()
    run, case = _case([{"action": "wait_until", "params": {"resourceId": "a:id/x"}}])

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.failed and "仅在严格回放模式下可用" in db.steps()[0].error_message


class _FakeEngine:
    def __init__(self):
        self.calls = []

    def execute(self, action, params, *, assert_write_allowed, check_cancel):
        assert_write_allowed()
        check_cancel()
        self.calls.append((action, params))
        return {"success": True, "data": {"strict": action}}


def test_strict_mode_routes_locator_steps_to_engine_and_keeps_passthrough(env, monkeypatch):
    engine = _FakeEngine()
    connected = []

    def connect(serial, package):
        connected.append((serial, package))
        return engine

    monkeypatch.setattr(executor, "connect_strict_engine", connect)
    steps = [
        {"action": "start_app", "params": {"package": "com.luna.music"}},
        {"action": "wait_until", "params": {"resourceId": "com.luna.music:id/cz="}},
        {"action": "input", "params": {"resourceId": "com.luna.music:id/df9", "text": "{{kw}}"}},
        {"action": "assert_element", "params": {"text": "综合"}},
    ]
    db = _FakeDB()
    run, case = _case(steps, strict_replay=True)

    asyncio.run(executor.run_android_lowcode(db, run, case, {"kw": "晴天"}))

    assert run.status == RunStatus.passed
    assert connected == [("emu-1", "com.luna.music")]
    assert [call[0] for call in env["calls"]] == ["start_app"]
    assert [call[0] for call in engine.calls] == ["wait_until", "input", "assert_element"]
    assert engine.calls[1][1]["text"] == "晴天"
    assert db.steps()[1].response_data == {"strict": "wait_until"}
    assert run.result_summary["execution_control"]["strict_package"] == "com.luna.music"


def test_strict_mode_rejects_unsupported_step_without_device_write(env, monkeypatch):
    monkeypatch.setattr(executor, "connect_strict_engine", lambda *_args: _FakeEngine())
    db = _FakeDB()
    run, case = _case([{"action": "long_click", "params": {"x": 1, "y": 2}}], strict_replay=True, app_package="p.q")

    asyncio.run(executor.run_android_lowcode(db, run, case, {}))

    assert run.status == RunStatus.failed and env["calls"] == []
    assert "严格回放不支持步骤类型: long_click" in db.steps()[0].error_message


def test_strict_mode_without_package_or_connection_errors(env, monkeypatch):
    db = _FakeDB()
    run, case = _case([CLICK], strict_replay=True)
    asyncio.run(executor.run_android_lowcode(db, run, case, {}))
    assert run.status == RunStatus.error and "目标应用包名" in run.error_message

    def boom(*_args):
        raise ConnectionError("adb")

    monkeypatch.setattr(executor, "connect_strict_engine", boom)
    db = _FakeDB()
    run, case = _case([CLICK], strict_replay=True, app_package="p.q")
    asyncio.run(executor.run_android_lowcode(db, run, case, {}))
    assert run.status == RunStatus.error and "ConnectionError" in run.error_message
    assert env["released"][-1] == (41, "lease-9")


def test_empty_assertions_no_longer_pass(monkeypatch):
    monkeypatch.setattr(executor, "_uiautomator_dump", lambda *_a, **_k: (True, "<hierarchy/>"))
    assert executor._execute_step_sync("s", "assert_text", {"text": ""})["success"] is False
    assert executor._execute_step_sync("s", "assert_element", {})["success"] is False
    assert executor._execute_step_sync("s", "assert_visual_element", {})["success"] is False
