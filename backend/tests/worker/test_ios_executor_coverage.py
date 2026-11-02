"""ios_executor 覆盖率补齐：协议边界错误分支 + run_ios_case 全流程（全 fake，无真实 Appium）。

仅新建文件，不改动源码与既有测试；所有子进程/网络/设备操作均以 fake 隔离。
"""

import asyncio
import base64
import types

import pytest

from app.models.bootstrap import load_all_models
from app.models.case import RunStatus
from app.services.ios_device_leases import IosDeviceLeaseConflict
from app.worker.executors import ios_executor as ios
from app.worker.executors.ios_executor import AppiumProtocolError, IosAppiumClient, _render_params

load_all_models()


class _Response:
    def __init__(self, status_code, payload=None, *, json_error=None):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class _ScriptedHttp:
    def __init__(self, responder):
        self._responder = responder
        self.requests = []
        self.closed = False

    async def request(self, method, url, json=None):
        self.requests.append((method, url, json))
        return self._responder(method, url, json)

    async def aclose(self):
        self.closed = True


def test_request_rejects_non_json_response():
    http = _ScriptedHttp(lambda m, u, j: _Response(502, json_error=ValueError("bad json")))
    client = IosAppiumClient("http://mac:4723", http_client=http)

    async def run():
        try:
            await client._request("GET", "/status")
        except AppiumProtocolError as exc:
            return str(exc)
        raise AssertionError("expected AppiumProtocolError")

    assert "返回了非 JSON 响应" in asyncio.run(run())


def test_request_raises_when_value_contains_error():
    http = _ScriptedHttp(lambda m, u, j: _Response(200, {"value": {"error": "stale element"}}))
    client = IosAppiumClient("http://mac:4723", http_client=http)

    async def run():
        try:
            await client._request("POST", "/x")
        except AppiumProtocolError as exc:
            return str(exc)
        raise AssertionError("expected AppiumProtocolError")

    assert "stale element" in asyncio.run(run())


def test_start_session_variants_and_invalid_payloads():
    http = _ScriptedHttp(lambda m, u, j: _Response(200, {"value": {"sessionId": "sid-1"}}))
    client = IosAppiumClient("http://mac:4723", http_client=http)

    async def run():
        sid = await client.start_session(
            udid="d", device_name="iPhone", platform_version="18", bundle_id="com.x", app="https://minio/app.ipa"
        )
        payload = http.requests[-1][2]["capabilities"]["alwaysMatch"]
        return sid, payload

    sid, payload = asyncio.run(run())
    assert sid == "sid-1"
    assert payload["appium:app"] == "https://minio/app.ipa"
    assert payload["appium:bundleId"] == "com.x"

    bad = IosAppiumClient(
        "http://mac:4723", http_client=_ScriptedHttp(lambda m, u, j: _Response(200, {"value": "nope"}))
    )

    async def run_bad():
        try:
            await bad.start_session(udid="d", device_name=None, platform_version=None, bundle_id=None, app=None)
        except AppiumProtocolError as exc:
            return str(exc)
        raise AssertionError("expected AppiumProtocolError")

    assert "响应格式无效" in asyncio.run(run_bad())

    missing = IosAppiumClient(
        "http://mac:4723", http_client=_ScriptedHttp(lambda m, u, j: _Response(200, {"value": {"session_id": ""}}))
    )

    async def run_missing():
        try:
            await missing.start_session(udid="d", device_name=None, platform_version=None, bundle_id=None, app=None)
        except AppiumProtocolError as exc:
            return str(exc)
        raise AssertionError("expected AppiumProtocolError")

    assert "缺少 sessionId" in asyncio.run(run_missing())


def test_find_element_and_screenshot_reject_invalid_shapes():
    http = _ScriptedHttp(lambda m, u, j: _Response(200, {"value": 123}))
    client = IosAppiumClient("http://mac:4723", http_client=http)
    client.session_id = "sid"

    async def run():
        errors = []
        try:
            await client.find_element({"value": "btn"})
        except AppiumProtocolError as exc:
            errors.append(str(exc))
        try:
            await client.screenshot()
        except AppiumProtocolError as exc:
            errors.append(str(exc))
        return errors

    errors = asyncio.run(run())
    assert any("元素响应格式无效" in e for e in errors)
    assert any("截图响应格式无效" in e for e in errors)


def test_close_releases_owned_http_client_only():
    fake = _ScriptedHttp(lambda m, u, j: _Response(200, {"value": {}}))
    client = IosAppiumClient("http://mac:4723", http_client=fake)
    asyncio.run(client.close())
    assert fake.closed is False

    client._owns_client = True
    asyncio.run(client.close())
    assert fake.closed is True


def test_safe_publish_swallows_publish_errors(monkeypatch):
    calls = []

    async def _boom(run_id, payload):
        calls.append((run_id, payload))
        raise RuntimeError("redis down")

    monkeypatch.setattr(ios, "publish_run_event", _boom)
    asyncio.run(ios._safe_publish(9, {"type": "x"}))
    assert calls == [(9, {"type": "x"})]


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def test_resolve_project_id_and_artifact_upload(monkeypatch):
    class _DB:
        async def execute(self, _stmt):
            return _ScalarResult(17)

    assert asyncio.run(ios._resolve_project_id(_DB(), types.SimpleNamespace(module_id=3))) == 17
    assert asyncio.run(ios._resolve_project_id(_DB(), types.SimpleNamespace(module_id="not-int"))) is None
    assert asyncio.run(ios._resolve_project_id(_DB(), types.SimpleNamespace())) is None

    uploaded = []
    monkeypatch.setattr(ios, "upload_bytes", lambda name, data, ct: uploaded.append((name, data, ct)))
    monkeypatch.setattr(ios, "presigned_url", lambda name, expires_seconds=None: f"https://minio/{name}")
    assert (
        asyncio.run(ios._upload_artifact(5, "syslog.json", b"log", "application/json"))
        == "https://minio/ios-artifacts/runs/5/syslog.json"
    )
    assert uploaded == [("ios-artifacts/runs/5/syslog.json", b"log", "application/json")]

    def _boom(*_a, **_kw):
        raise RuntimeError("minio down")

    monkeypatch.setattr(ios, "upload_bytes", _boom)
    assert asyncio.run(ios._upload_artifact(5, "x.png", b"x", "image/png")) is None


def test_render_params_passes_through_non_string_values():
    assert _render_params(15, {"A": "1"}) == 15


class _FakeAppiumClient:
    instances: list = []
    step_hook = None
    start_session_hook = None
    screenshot_hook = None
    start_recording_hook = None
    stop_recording_hook = None
    syslog_hook = None
    quit_hook = None
    close_hook = None
    stop_recording_value = None
    syslog_value = "logline"

    def __init__(self, server_url, *, timeout=30.0, http_client=None):
        self.server_url = server_url
        self.timeout = timeout
        self.session_id = None
        self.capabilities = {}
        self.executed = []
        self.session_kwargs = None
        self.quit_called = False
        self.close_called = False
        type(self).instances.append(self)

    async def start_session(self, **kwargs):
        if type(self).start_session_hook is not None:
            type(self).start_session_hook(self)
        self.session_kwargs = kwargs
        self.session_id = "sid"
        self.capabilities = {"platformName": "iOS"}
        return "sid"

    async def execute_step(self, action, params):
        self.executed.append((action, params))
        if type(self).step_hook is not None:
            result = type(self).step_hook(action, params)
            if result is not None:
                return result
        return {"success": True}

    async def screenshot(self):
        if type(self).screenshot_hook is not None:
            return type(self).screenshot_hook()
        return base64.b64encode(b"img").decode()

    async def start_recording(self):
        if type(self).start_recording_hook is not None:
            type(self).start_recording_hook()

    async def stop_recording(self):
        if type(self).stop_recording_hook is not None:
            result = type(self).stop_recording_hook()
            if result is not None:
                return result
        return type(self).stop_recording_value

    async def syslog(self):
        if type(self).syslog_hook is not None:
            value = type(self).syslog_hook()
            if value is not None:
                return value
        return type(self).syslog_value

    async def quit(self):
        if type(self).quit_hook is not None:
            type(self).quit_hook()
        self.quit_called = True

    async def close(self):
        if type(self).close_hook is not None:
            type(self).close_hook()
        self.close_called = True


@pytest.fixture()
def ios_env(monkeypatch):
    _FakeAppiumClient.instances = []
    for name in (
        "step_hook",
        "start_session_hook",
        "screenshot_hook",
        "start_recording_hook",
        "stop_recording_hook",
        "syslog_hook",
        "quit_hook",
        "close_hook",
    ):
        setattr(_FakeAppiumClient, name, None)
    _FakeAppiumClient.stop_recording_value = None
    _FakeAppiumClient.syslog_value = "logline"

    events = types.SimpleNamespace(published=[], releases=[], heartbeats=[])

    class _Lease:
        lease_token = "lease-tok"

    async def _acquire(db, device_id, **_kw):
        return _Lease()

    async def _heartbeat(db, device_id, token):
        events.heartbeats.append((device_id, token))

    async def _release(db, device_id, token):
        events.releases.append((device_id, token))

    async def _publish(run_id, payload):
        events.published.append(payload)

    monkeypatch.setattr(ios, "IosAppiumClient", _FakeAppiumClient)
    monkeypatch.setattr(ios, "acquire_ios_device_lease", _acquire)
    monkeypatch.setattr(ios, "heartbeat_ios_device_lease", _heartbeat)
    monkeypatch.setattr(ios, "release_ios_device_lease", _release)
    monkeypatch.setattr(ios, "publish_run_event", _publish)
    monkeypatch.setattr(ios, "upload_bytes", lambda *a, **kw: None)
    monkeypatch.setattr(ios, "presigned_url", lambda name, expires_seconds=None: f"https://minio/{name}")
    return events


class _IosDB:
    def __init__(self, *, project_id=5, device=None, app=None):
        self.project_id = project_id
        self._models = {ios.IosDevice: device, ios.IosApp: app}
        self.added = []
        self.commits = 0

    async def get(self, model, _pk):
        return self._models.get(model)

    async def execute(self, _stmt):
        return _ScalarResult(self.project_id)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commits += 1


DEVICE = types.SimpleNamespace(
    id=3, udid="udid-1", name="iPhone 15", platform_version="18.0", appium_server_url="http://mac:4723"
)
APP = types.SimpleNamespace(id=9, object_name="ios/apps/demo.ipa", bundle_id="com.demo.app", project_id=5)


def _env(steps, *, config=None, device=None, app=None, run_id=41):
    run = types.SimpleNamespace(
        id=run_id, status=RunStatus.running, error_message=None, duration_ms=None, result_summary=None, triggered_by=1
    )
    case = types.SimpleNamespace(id=7, module_id=22, config={"steps": steps, **(config or {})})
    return _IosDB(device=device, app=app), run, case


def test_run_ios_case_requires_configured_steps(ios_env):
    db, run, case = _env([])
    asyncio.run(ios.run_ios_case(db, run, case, {}))
    assert run.status == RunStatus.error
    assert "未配置任何步骤" in run.error_message

    db2, run2, case2 = _env({"not": "a-list"})
    asyncio.run(ios.run_ios_case(db2, run2, case2, {}))
    assert run2.status == RunStatus.error
    assert "未配置任何步骤" in run2.error_message


def test_run_ios_case_rejects_foreign_app_and_missing_target(ios_env):
    foreign_app = types.SimpleNamespace(id=9, object_name="ios/x.ipa", bundle_id="com.x", project_id=99)
    db, run, case = _env([{"action": "click"}], config={"ios_app_id": 9}, app=foreign_app)
    asyncio.run(ios.run_ios_case(db, run, case, {}))
    assert run.status == RunStatus.error
    assert "IPA 资产不属于当前项目" in run.error_message

    db, run, case = _env([{"action": "click"}])
    asyncio.run(ios.run_ios_case(db, run, case, {}))
    assert run.status == RunStatus.error
    assert "未配置 iOS UDID 或 Appium 地址" in run.error_message


def _patch_wda(monkeypatch, *, recovered, crash_types=(RuntimeError,)):
    monkeypatch.setattr(ios, "is_wda_session_crash", lambda exc: isinstance(exc, crash_types))

    async def _recover(server_url, capabilities):
        return recovered

    monkeypatch.setattr(ios, "recover_wda_session", _recover)


def test_run_ios_case_lease_conflict_marks_failed(ios_env, monkeypatch):
    async def _conflict(*_a, **_kw):
        raise IosDeviceLeaseConflict("busy")

    monkeypatch.setattr(ios, "acquire_ios_device_lease", _conflict)
    db, run, case = _env([{"action": "click"}], config={"ios_device_id": 3}, device=DEVICE)
    asyncio.run(ios.run_ios_case(db, run, case, {}))
    assert run.status == RunStatus.failed
    assert "iOS 设备租约冲突: busy" in run.error_message


def test_run_ios_case_executes_steps_uploads_artifacts_and_breaks(ios_env):
    shot = base64.b64encode(b"shot").decode()

    def _step_hook(action, params):
        if action == "screenshot":
            return {"success": True, "screenshot_base64": shot}
        if action == "assert_text":
            return {"success": False, "detail": "missing"}
        return {"success": True}

    _FakeAppiumClient.step_hook = _step_hook
    _FakeAppiumClient.stop_recording_value = base64.b64encode(b"vid").decode()

    steps = [
        {"action": "click", "name": "点击", "params": {"value": "{{TAP}}"}},
        {"action": "screenshot", "params": {}},
        {"action": "assert_text", "params": {"text": "OK"}},
        {"action": "back"},
    ]
    db, run, case = _env(
        steps, config={"ios_device_id": 3, "ios_app_id": 9, "record_video": True}, device=DEVICE, app=APP
    )
    asyncio.run(ios.run_ios_case(db, run, case, {"TAP": "TAPV"}))

    client = _FakeAppiumClient.instances[-1]
    assert [action for action, _params in client.executed] == ["click", "screenshot", "assert_text"]
    assert client.executed[0][1]["value"] == "TAPV"
    assert client.session_kwargs["udid"] == "udid-1"
    assert client.session_kwargs["device_name"] == "iPhone 15"
    assert client.session_kwargs["platform_version"] == "18.0"
    assert client.session_kwargs["bundle_id"] == "com.demo.app"
    assert client.session_kwargs["app"] == "https://minio/ios/apps/demo.ipa"

    artifacts = run.result_summary["ios_artifacts"]
    assert artifacts["screen_recording"] == "https://minio/ios-artifacts/runs/41/screen-recording.mp4"
    assert artifacts["syslog"] == "https://minio/ios-artifacts/runs/41/syslog.json"
    assert run.result_summary["udid"] == "udid-1"
    assert run.status == RunStatus.failed
    assert len(db.added) == 3
    assert db.added[1].screenshot_url == "https://minio/ios-artifacts/runs/41/step_1.png"
    assert "iOS 断言失败" in db.added[2].error_message
    assert ios_env.heartbeats == [(3, "lease-tok")] * 3
    assert ios_env.releases == [(3, "lease-tok")]
    assert client.quit_called and client.close_called
    assert any(event.get("type") == "completed" for event in ios_env.published)


def test_run_ios_case_recovers_wda_session_and_retries(ios_env, monkeypatch):
    state = {"first": True}

    def _step_hook(action, params):
        if state["first"]:
            state["first"] = False
            raise RuntimeError("wda session crash")
        return {"success": True}

    _FakeAppiumClient.step_hook = _step_hook
    _patch_wda(monkeypatch, recovered={"recovered": True, "session_id": "new-sid"})
    db, run, case = _env([{"action": "click"}], config={"ios_device_id": 3}, device=DEVICE)
    asyncio.run(ios.run_ios_case(db, run, case, {}))

    client = _FakeAppiumClient.instances[-1]
    assert client.session_id == "new-sid"
    assert len(client.executed) == 2
    assert run.status == RunStatus.passed
    assert db.added[0].status == RunStatus.passed


def test_run_ios_case_wda_retry_failure_records_error(ios_env, monkeypatch):
    state = {"first": True}

    def _step_hook(action, params):
        if state["first"]:
            state["first"] = False
            raise RuntimeError("wda session crash")
        raise ValueError("retry died")

    _FakeAppiumClient.step_hook = _step_hook
    _patch_wda(monkeypatch, recovered={"recovered": True, "session_id": "new-sid"})
    db, run, case = _env([{"action": "click"}], config={"ios_device_id": 3}, device=DEVICE)
    asyncio.run(ios.run_ios_case(db, run, case, {}))
    assert db.added[0].status == RunStatus.failed
    assert "WDA 会话自愈后重试失败: retry died" in db.added[0].error_message


def test_run_ios_case_wda_recovery_failure_records_error(ios_env, monkeypatch):
    def _step_hook(action, params):
        raise RuntimeError("wda session crash")

    _FakeAppiumClient.step_hook = _step_hook
    _patch_wda(monkeypatch, recovered={"recovered": False, "error": "server gone"})
    db, run, case = _env([{"action": "click"}], config={"ios_device_id": 3}, device=DEVICE)
    asyncio.run(ios.run_ios_case(db, run, case, {}))
    assert db.added[0].status == RunStatus.failed
    assert "WDA 会话崩溃且自愈失败: server gone" in db.added[0].error_message


def test_run_ios_case_plain_step_failure_records_error(ios_env, monkeypatch):
    def _step_hook(action, params):
        raise ValueError("plain crash")

    _FakeAppiumClient.step_hook = _step_hook
    monkeypatch.setattr(ios, "is_wda_session_crash", lambda exc: False)
    db, run, case = _env([{"action": "click"}], config={"ios_device_id": 3}, device=DEVICE)
    asyncio.run(ios.run_ios_case(db, run, case, {}))
    assert db.added[0].status == RunStatus.failed
    assert db.added[0].error_message == "plain crash"
    assert ios_env.heartbeats == [(3, "lease-tok")]


def test_run_ios_case_outer_failure_marks_error_and_closes_client(ios_env):
    def _start_hook(_client):
        raise RuntimeError("appium unreachable")

    def _quit_hook():
        raise RuntimeError("quit failed")

    def _close_hook():
        raise RuntimeError("close failed")

    _FakeAppiumClient.start_session_hook = _start_hook
    _FakeAppiumClient.quit_hook = _quit_hook
    _FakeAppiumClient.close_hook = _close_hook
    db, run, case = _env([{"action": "click"}], config={"ios_device_id": 3}, device=DEVICE)
    asyncio.run(ios.run_ios_case(db, run, case, {}))
    assert run.status == RunStatus.error
    assert "appium unreachable" in run.error_message
    assert ios_env.releases == [(3, "lease-tok")]
    assert ios_env.published[-1]["status"] == "error"


def test_run_ios_case_tolerates_lease_release_failure(ios_env, monkeypatch):
    async def _release_boom(*_a, **_kw):
        raise RuntimeError("release down")

    monkeypatch.setattr(ios, "release_ios_device_lease", _release_boom)
    db, run, case = _env([{"action": "click"}], config={"ios_device_id": 3}, device=DEVICE)
    asyncio.run(ios.run_ios_case(db, run, case, {}))
    assert run.status == RunStatus.passed


def test_run_ios_case_tolerates_unsupported_recording_and_syslog(ios_env):
    def _start_hook():
        raise AppiumProtocolError("unsupported")

    def _stop_hook():
        raise AppiumProtocolError("unsupported")

    def _syslog_hook():
        raise AppiumProtocolError("unsupported")

    _FakeAppiumClient.start_recording_hook = _start_hook
    _FakeAppiumClient.stop_recording_hook = _stop_hook
    _FakeAppiumClient.syslog_hook = _syslog_hook
    db, run, case = _env([{"action": "click"}], config={"ios_device_id": 3, "record_video": True}, device=DEVICE)
    asyncio.run(ios.run_ios_case(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert run.result_summary["ios_artifacts"] == {}


def _appium_routes():
    return {
        ("POST", "/session/sid-1/element"): {"value": {"element-6066-11e4-a52e-4f735466cecf": "el1"}},
        ("POST", "/session/sid-1/element/el1/click"): {"value": None},
        ("POST", "/session/sid-1/element/el1/clear"): {"value": None},
        ("POST", "/session/sid-1/element/el1/value"): {"value": None},
        ("GET", "/session/sid-1/source"): {"value": '<hierarchy><node text="OK" /></hierarchy>'},
        ("GET", "/session/sid-1/screenshot"): {"value": "UE5H"},
        ("POST", "/session/sid-1/back"): {"value": None},
        ("POST", "/session/sid-1/appium/device/activate_app"): {"value": None},
        ("POST", "/session/sid-1/appium/device/terminate_app"): {"value": None},
        ("POST", "/session/sid-1/actions"): {"value": None},
        ("POST", "/session/sid-1/appium/start_recording_screen"): {"value": None},
        ("POST", "/session/sid-1/appium/stop_recording_screen"): {"value": "VkQ="},
        ("POST", "/session/sid-1/log"): {"value": {"entries": []}},
        ("DELETE", "/session/sid-1"): {"value": None},
    }


def test_execute_step_covers_all_actions():
    routes = _appium_routes()

    def responder(method, url, body):
        key = (method, url.replace("http://mac:4723", ""))
        assert key in routes, f"unexpected {key}"
        return _Response(200, routes[key])

    http = _ScriptedHttp(responder)
    client = IosAppiumClient("http://mac:4723", http_client=http)
    client.session_id = "sid-1"

    async def run():
        results = []
        results.append(await client.execute_step("click", {"value": "btn"}))
        results.append(await client.execute_step("input", {"value": "btn", "text": "hi", "clear": True}))
        results.append(await client.execute_step("input", {"value": "btn", "text": "hi", "clear": False}))
        results.append(await client.execute_step("assert_element", {"value": "btn"}))
        results.append(await client.execute_step("assert_text", {"text": "OK"}))
        results.append(await client.execute_step("assert_text", {"text": "NOPE"}))
        results.append(await client.execute_step("wait", {"seconds": 0}))
        results.append(await client.execute_step("screenshot", {}))
        results.append(await client.execute_step("back", {}))
        results.append(await client.execute_step("start_app", {"bundle_id": "com.demo"}))
        results.append(await client.execute_step("stop_app", {"bundle_id": "com.demo"}))
        results.append(await client.execute_step("get_source", {}))
        results.append(await client.execute_step("tap", {"x": 5, "y": 6}))
        results.append(await client.execute_step("swipe", {"x": 1, "y": 2, "to_x": 3, "to_y": 4, "duration_ms": 50}))
        return results

    results = asyncio.run(run())
    assert results[0] == {"success": True, "element_id": "el1"}
    assert results[1]["success"] is True and results[1]["element_id"] == "el1"
    assert results[2]["success"] is True and results[2]["element_id"] == "el1"
    assert results[3] == {"success": True, "element_id": "el1"}
    assert results[4]["success"] is True and results[4]["source_contains"] is True
    assert results[5] == {"success": False, "expected": "NOPE", "source_contains": False}
    assert results[6] == {"success": True, "wait_seconds": 0.0}
    assert results[7] == {"success": True, "screenshot_base64": "UE5H"}
    assert results[8] == {"success": True}
    assert results[9] == {"success": True, "bundle_id": "com.demo"}
    assert results[10] == {"success": True, "bundle_id": "com.demo"}
    assert results[11]["source"].startswith("<hierarchy>")
    assert results[12] == {"success": True}
    assert results[13] == {"success": True}

    clear_calls = [r for r in http.requests if r[1].endswith("/element/el1/clear")]
    assert len(clear_calls) == 1
    value_calls = [r for r in http.requests if r[1].endswith("/element/el1/value")]
    assert len(value_calls) == 2 and value_calls[-1][2]["value"] == ["h", "i"]
    actions_bodies = [r[2]["actions"][0] for r in http.requests if r[1].endswith("/actions")]
    assert actions_bodies[0]["parameters"]["pointerType"] == "touch"
    swipe_moves = [a for a in actions_bodies[1]["actions"] if a["type"] == "pointerMove"]
    assert swipe_moves[-1]["x"] == 3 and swipe_moves[-1]["y"] == 4 and swipe_moves[-1]["duration"] == 100


def test_appium_client_lifecycle_and_recording_edges():
    routes = _appium_routes()

    def responder(method, url, body):
        key = (method, url.replace("http://mac:4723", ""))
        assert key in routes, f"unexpected {key}"
        return _Response(200, routes[key])

    client = IosAppiumClient("http://mac:4723", http_client=_ScriptedHttp(responder))
    client.session_id = "sid-1"

    async def run():
        out = {}
        out["recording_start"] = await client.start_recording()
        out["recording_stop"] = await client.stop_recording()
        out["syslog"] = await client.syslog()
        out["wait"] = await client.execute_step("wait", {"timeout": 0})
        out["xpath"] = await client.find_element({"strategy": "xpath", "value": "//XCUIElementTypeButton"})
        await client.quit()
        out["session_id"] = client.session_id
        return out

    out = asyncio.run(run())
    assert out["recording_start"] is None
    assert out["recording_stop"] == "VkQ="
    assert isinstance(out["syslog"], str) and '"entries"' in out["syslog"]
    assert out["wait"] == {"success": True, "wait_seconds": 0.0}
    assert out["xpath"] == "el1"
    assert out["session_id"] is None

    http = client.http
    using_values = [r[2]["using"] for r in http.requests if isinstance(r[2], dict) and "using" in r[2]]
    assert using_values == ["xpath"]
    assert len([r for r in http.requests if r[0] == "DELETE"]) == 1


def test_appium_client_quit_without_session_and_failed_delete():
    http = _ScriptedHttp(lambda m, u, j: _Response(500, {"value": "boom"}))
    client = IosAppiumClient("http://mac:4723", http_client=http)
    asyncio.run(client.quit())
    assert http.requests == []

    client.session_id = "sid-9"

    async def run():
        try:
            await client.quit()
        except AppiumProtocolError as exc:
            return str(exc)
        raise AssertionError("expected AppiumProtocolError")

    assert "boom" in asyncio.run(run())
    assert client.session_id is None
    assert http.requests == [("DELETE", "http://mac:4723/session/sid-9", None)]


def test_appium_client_invalid_payloads_raise_protocol_error():
    def responder(method, url, body):
        if url.endswith("/screenshot"):
            return _Response(200, {"value": {"oops": 1}})
        return _Response(200, {"value": "not-a-dict"})

    client = IosAppiumClient("http://mac:4723", http_client=_ScriptedHttp(responder))

    async def run():
        errors = []
        client.session_id = "sid-1"
        for coro in (
            client.find_element({"value": ""}),
            client.find_element({"strategy": "id", "value": "v"}),
            client.screenshot(),
            client.execute_step("teleport", {}),
        ):
            try:
                await coro
            except AppiumProtocolError as exc:
                errors.append(str(exc))
        return errors

    errors = asyncio.run(run())
    assert len(errors) == 4
    assert "缺少 value" in errors[0]
    assert "元素响应格式无效" in errors[1]
    assert "截图响应格式无效" in errors[2]
    assert "未知 iOS 操作类型" in errors[3]


def test_session_path_and_render_params_edge_cases():
    client = IosAppiumClient("http://mac:4723", http_client=_ScriptedHttp(lambda m, u, j: _Response(200, {})))
    try:
        client._session_path()
    except AppiumProtocolError as exc:
        assert "Appium 会话尚未建立" in str(exc)
    else:
        raise AssertionError("expected AppiumProtocolError")

    async def run():
        try:
            await client.find_element({"value": "x"})
        except AppiumProtocolError as exc:
            return str(exc)
        raise AssertionError("expected AppiumProtocolError")

    assert "尚未建立" in asyncio.run(run())
    assert _render_params(["a", {"b": "{{K}}"}, 3], {"K": "v"}) == ["a", {"b": "v"}, 3]


def test_run_ios_case_without_device_skips_lease_and_optional_artifacts(ios_env):
    _FakeAppiumClient.stop_recording_value = ""
    _FakeAppiumClient.syslog_value = ""
    db, run, case = _env(
        [{"action": "click"}],
        config={
            "udid": "udid-cfg",
            "appium_server_url": "http://mac:4723",
            "record_video": True,
            "capture_screenshot": False,
        },
    )
    asyncio.run(ios.run_ios_case(db, run, case, {}))
    client = _FakeAppiumClient.instances[-1]
    assert client.session_kwargs["udid"] == "udid-cfg"
    assert run.status == RunStatus.passed
    assert "screen_recording" not in run.result_summary["ios_artifacts"]
    assert "syslog" not in run.result_summary["ios_artifacts"]
    assert ios_env.heartbeats == [] and ios_env.releases == []


def test_run_ios_case_wda_retry_returns_failed_result(ios_env, monkeypatch):
    state = {"first": True}

    def _step_hook(action, params):
        if state["first"]:
            state["first"] = False
            raise RuntimeError("wda session crash")
        return {"success": False, "detail": "still broken"}

    _FakeAppiumClient.step_hook = _step_hook
    _patch_wda(monkeypatch, recovered={"recovered": True, "session_id": "new-sid"})
    db, run, case = _env([{"action": "click"}], config={"ios_device_id": 3}, device=DEVICE)
    asyncio.run(ios.run_ios_case(db, run, case, {}))
    assert db.added[0].status == RunStatus.failed
    assert "iOS 断言失败" in db.added[0].error_message
    assert run.status == RunStatus.failed
