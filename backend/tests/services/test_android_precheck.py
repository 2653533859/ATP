"""Unit tests for M2 Android device-level pre-execution precheck."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.models.bootstrap import load_all_models
from app.models.apk import Apk
from app.models.case import CaseType, TestCase, TestRun, RunStatus
from app.models.device import Device, DeviceLease, DeviceStatus
from app.models.environment import Environment, EnvVariable
from app.models.ios import IosDevice, IosDeviceStatus
from app.schemas.android_precheck import PrecheckScope, PrecheckStatus
from app.services.android_precheck import precheck_android_execution

load_all_models()


class _MockResult:
    def __init__(self, item: Any):
        self._item = item

    def scalar_one_or_none(self):
        return self._item

    def scalars(self):
        return self

    def all(self):
        return self._item if isinstance(self._item, list) else ([self._item] if self._item else [])


class _FakePrecheckDB:
    def __init__(
        self,
        *,
        devices: list[Device] | None = None,
        ios_devices: list[IosDevice] | None = None,
        leases: list[DeviceLease] | None = None,
        apks: list[Apk] | None = None,
        environments: list[Environment] | None = None,
        env_vars: list[EnvVariable] | None = None,
    ):
        self.devices = {d.serial: d for d in (devices or [])}
        self.devices_by_id = {d.id: d for d in (devices or [])}
        self.ios_devices = {d.udid: d for d in (ios_devices or [])}
        self.leases = {l.device_id: l for l in (leases or [])}
        self.apks = {a.id: a for a in (apks or [])}
        self.environments = {e.id: e for e in (environments or [])}
        self.env_vars = env_vars or []

    async def execute(self, statement: Any):
        sql = str(statement).lower()
        params: dict[str, Any] = {}
        if hasattr(statement, "compile"):
            try:
                params = statement.compile().params or {}
            except Exception:
                params = {}

        if "from devices" in sql:
            for v in params.values():
                if v in self.devices:
                    return _MockResult(self.devices[v])
            for serial, dev in self.devices.items():
                if serial.lower() in sql:
                    return _MockResult(dev)
            return _MockResult(None)

        if "from ios_devices" in sql:
            for v in params.values():
                if v in self.ios_devices:
                    return _MockResult(self.ios_devices[v])
            for udid, dev in self.ios_devices.items():
                if udid.lower() in sql:
                    return _MockResult(dev)
            return _MockResult(None)

        if "from device_leases" in sql:
            for v in params.values():
                if v in self.leases:
                    return _MockResult(self.leases[v])
            for dev_id, lease in self.leases.items():
                if str(dev_id) in sql:
                    return _MockResult(lease)
            return _MockResult(None)

        if "from apks" in sql:
            for v in params.values():
                if v in self.apks:
                    return _MockResult(self.apks[v])
            for apk_id, apk in self.apks.items():
                if str(apk_id) in sql:
                    return _MockResult(apk)
            return _MockResult(None)

        if "from env_variables" in sql:
            return _MockResult(self.env_vars)

        return _MockResult(None)

    async def get(self, model: Any, ident: Any):
        if model is Device:
            return self.devices_by_id.get(ident)
        if model is Apk:
            return self.apks.get(ident)
        if model is Environment:
            return self.environments.get(ident)
        return None

    def add(self, obj: Any):
        pass

    async def commit(self):
        pass

    async def refresh(self, obj: Any):
        pass


@pytest.mark.asyncio
async def test_precheck_missing_device_serial():
    db = _FakePrecheckDB()
    res = await precheck_android_execution(
        db,
        steps=[{"action": "click", "params": {"text": "登录"}}],
        check_adb_environment=False,
    )
    assert not res.ok
    assert any(i.code == "MISSING_DEVICE_SERIAL" and i.status == PrecheckStatus.FAIL for i in res.items)


@pytest.mark.asyncio
async def test_precheck_device_not_found():
    db = _FakePrecheckDB()
    res = await precheck_android_execution(
        db,
        device_serial="device-not-registered",
        steps=[{"action": "click", "params": {"text": "登录"}}],
        check_adb_environment=False,
    )
    assert not res.ok
    assert any(i.code == "DEVICE_NOT_FOUND" and i.status == PrecheckStatus.FAIL for i in res.items)


@pytest.mark.asyncio
async def test_precheck_unsupported_platform_ios():
    ios_dev = IosDevice(id=1, udid="ios-udid-123", name="iPhone 15", status=IosDeviceStatus.online)
    db = _FakePrecheckDB(ios_devices=[ios_dev])

    res = await precheck_android_execution(
        db,
        device_serial="ios-udid-123",
        steps=[{"action": "click", "params": {"text": "登录"}}],
        check_adb_environment=False,
    )
    assert not res.ok
    assert any(i.code == "UNSUPPORTED_PLATFORM" and i.status == PrecheckStatus.FAIL for i in res.items)


@pytest.mark.asyncio
async def test_precheck_device_offline():
    dev = Device(id=1, serial="android-offline-1", status=DeviceStatus.offline)
    db = _FakePrecheckDB(devices=[dev])

    res = await precheck_android_execution(
        db,
        device_serial="android-offline-1",
        steps=[{"action": "click", "params": {"text": "登录"}}],
        check_adb_environment=False,
    )
    assert not res.ok
    assert any(i.code == "DEVICE_OFFLINE" and i.status == PrecheckStatus.FAIL for i in res.items)


@pytest.mark.asyncio
async def test_precheck_device_lease_conflict():
    dev = Device(id=1, serial="android-busy-1", status=DeviceStatus.busy)
    now = datetime.now(timezone.utc)
    lease = DeviceLease(
        id=1,
        device_id=1,
        lease_token="other-token-123",
        owner_id=99,
        owner_label="case-run:888",
        acquired_at=now,
        heartbeat_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    db = _FakePrecheckDB(devices=[dev], leases=[lease])

    # 1. 冲突检查
    res = await precheck_android_execution(
        db,
        device_serial="android-busy-1",
        steps=[{"action": "click", "params": {"text": "登录"}}],
        check_adb_environment=False,
    )
    assert not res.ok
    assert any(i.code == "DEVICE_LEASE_CONFLICT" and i.status == PrecheckStatus.FAIL for i in res.items)

    # 2. 持有租约自身调用应放行
    res_mine = await precheck_android_execution(
        db,
        device_serial="android-busy-1",
        steps=[{"action": "click", "params": {"text": "登录"}}],
        ignore_lease_token="other-token-123",
        check_adb_environment=False,
    )
    assert not any(i.code == "DEVICE_LEASE_CONFLICT" for i in res_mine.items)


@pytest.mark.asyncio
async def test_precheck_apk_and_app_package():
    dev = Device(id=1, serial="android-online-1", status=DeviceStatus.online)
    apk = Apk(
        id=10,
        project_id=1,
        filename="app.apk",
        package_name="com.example.app",
        object_name="apks/1/app.apk",
        uploaded_by=1,
    )
    db = _FakePrecheckDB(devices=[dev], apks=[apk])

    # 1. APK 不存在
    res_no_apk = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        config={"apk_id": 999},
        steps=[{"action": "start_app"}],
        check_adb_environment=False,
    )
    assert any(i.code == "APK_NOT_FOUND" and i.status == PrecheckStatus.FAIL for i in res_no_apk.items)

    # 2. APK 所属项目不匹配
    res_mismatch = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        config={"apk_id": 10},
        project_id=2,  # apk.project_id is 1
        steps=[{"action": "start_app"}],
        check_adb_environment=False,
    )
    assert any(i.code == "APK_PROJECT_MISMATCH" and i.status == PrecheckStatus.FAIL for i in res_mismatch.items)

    # 3. 缺少包名且无 APK
    res_no_pkg = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        steps=[{"action": "start_app"}],
        check_adb_environment=False,
    )
    assert any(i.code == "MISSING_PACKAGE" and i.status == PrecheckStatus.FAIL for i in res_no_pkg.items)


@pytest.mark.asyncio
async def test_precheck_step_locators_and_actions():
    dev = Device(id=1, serial="android-online-1", status=DeviceStatus.online)
    db = _FakePrecheckDB(devices=[dev])

    # 1. 空步骤
    res_empty = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        steps=[],
        check_adb_environment=False,
    )
    assert not res_empty.ok
    assert any(i.code == "EMPTY_STEPS" for i in res_empty.items)

    # 2. 不支持的操作
    res_unsupported = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        steps=[{"action": "fly_to_moon", "params": {}}],
        check_adb_environment=False,
    )
    assert any(i.code == "UNSUPPORTED_ACTION" and i.step_index == 1 for i in res_unsupported.items)

    # 3. 点击缺少定位
    res_click_no_loc = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        steps=[{"action": "click", "params": {}}],
        check_adb_environment=False,
    )
    assert any(i.code == "MISSING_LOCATOR" and i.step_index == 1 for i in res_click_no_loc.items)

    # 4. 滑动缺少参数或方向错误
    res_swipe_bad = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        steps=[{"action": "swipe", "params": {"direction": "forward"}}],
        check_adb_environment=False,
    )
    assert any(i.code == "INVALID_SWIPE_DIRECTION" and i.step_index == 1 for i in res_swipe_bad.items)

    # 5. 输入缺少内容
    res_input_empty = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        steps=[{"action": "input", "params": {}}],
        check_adb_environment=False,
    )
    assert any(i.code == "MISSING_INPUT_CONTENT" and i.step_index == 1 for i in res_input_empty.items)

    # 6. 按键缺少 key
    res_key_empty = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        steps=[{"action": "press_key", "params": {}}],
        check_adb_environment=False,
    )
    assert any(i.code == "MISSING_KEY" and i.step_index == 1 for i in res_key_empty.items)

    # 7. 文本断言缺少 text
    res_assert_text = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        steps=[{"action": "assert_text", "params": {}}],
        check_adb_environment=False,
    )
    assert any(i.code == "MISSING_ASSERT_TEXT" and i.step_index == 1 for i in res_assert_text.items)

    # 8. 元素断言缺少 resourceId
    res_assert_el = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        steps=[{"action": "assert_element", "params": {}}],
        check_adb_environment=False,
    )
    assert any(i.code == "MISSING_ASSERT_ELEMENT" and i.step_index == 1 for i in res_assert_el.items)


@pytest.mark.asyncio
async def test_precheck_variables_warning():
    dev = Device(id=1, serial="android-online-1", status=DeviceStatus.online)
    db = _FakePrecheckDB(devices=[dev])

    # 1. 包含未定义变量
    res = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        steps=[
            {"action": "input", "params": {"text": "Hello {{USER_NAME}}"}},
            {"action": "click", "params": {"text": "{{LOGIN_BTN}}"}},
        ],
        extra_vars={"USER_NAME": "admin"},
        check_adb_environment=False,
    )
    # USER_NAME 已声明，LOGIN_BTN 未声明
    warnings = [i for i in res.items if i.code == "UNDEFINED_VARIABLE"]
    assert len(warnings) == 1
    assert warnings[0].step_index == 2
    assert "LOGIN_BTN" in warnings[0].message


@pytest.mark.asyncio
async def test_precheck_happy_path():
    dev = Device(id=1, serial="android-online-1", status=DeviceStatus.online)
    db = _FakePrecheckDB(devices=[dev])

    res = await precheck_android_execution(
        db,
        device_serial="android-online-1",
        config={"app_package": "com.example.app"},
        steps=[
            {"action": "start_app", "params": {"package": "com.example.app"}},
            {"action": "input", "params": {"text": "test_user", "resourceId": "com.example.app:id/username"}},
            {"action": "click", "params": {"x": 500, "y": 1000}},
            {"action": "wait", "params": {"ms": 1000}},
            {"action": "assert_text", "params": {"text": "Welcome"}},
        ],
        check_adb_environment=False,
    )
    assert res.ok is True
    assert res.summary.total_steps == 5
    assert res.summary.passed_steps == 5
    assert res.summary.failed_steps == 0
    assert res.summary.has_blocking_issue is False


@pytest.mark.asyncio
async def test_precheck_rejects_other_project_environment_and_step_package_fallback():
    dev = Device(id=1, serial="android-online-1", status=DeviceStatus.online)
    env = Environment(id=7, name="other", project_id=99)
    db = _FakePrecheckDB(devices=[dev], environments=[env])
    res = await precheck_android_execution(
        db,
        device_serial=dev.serial,
        config={"app_package": "com.example.app"},
        steps=[{"action": "start_app", "params": {}}, {"action": "wait", "params": {"ms": 1}}],
        env_id=env.id,
        project_id=1,
        check_adb_environment=False,
    )
    assert {item.code for item in res.items if item.status == PrecheckStatus.FAIL} >= {
        "INVALID_ENVIRONMENT",
        "MISSING_PACKAGE",
    }


@pytest.mark.asyncio
async def test_precheck_reports_unavailable_adb_without_silent_pass():
    dev = Device(id=1, serial="android-online-1", status=DeviceStatus.online)
    db = _FakePrecheckDB(devices=[dev])
    with patch("app.services.android_precheck._check_adb_environment_state", return_value=(False, "ADB_UNAVAILABLE")):
        advisory = await precheck_android_execution(db, device_serial=dev.serial, steps=[{"action": "wait"}])
        strict = await precheck_android_execution(
            db, device_serial=dev.serial, steps=[{"action": "wait"}], strict_adb_environment=True
        )
    assert advisory.ok and any(
        item.code == "ADB_UNAVAILABLE" and item.status == PrecheckStatus.WARNING for item in advisory.items
    )
    assert not strict.ok and any(
        item.code == "ADB_UNAVAILABLE" and item.status == PrecheckStatus.FAIL for item in strict.items
    )


@pytest.mark.asyncio
async def test_android_lowcode_executor_recheck_blocked():
    from app.worker.executors.android_lowcode_executor import run_android_lowcode

    dev = Device(id=1, serial="android-1", status=DeviceStatus.online)
    run = TestRun(id=101, case_id=1, triggered_by=1, status=RunStatus.running)
    # 用例步骤缺少定位参数
    case = TestCase(
        id=1,
        name="测试用例",
        case_type=CaseType.android,
        config={
            "device_serial": "android-1",
            "steps": [
                {"action": "click", "params": {}},  # 缺少定位参数，预检必失败
            ],
        },
    )

    fake_db = AsyncMock()
    fake_db.execute = AsyncMock()
    # Mock device query
    dev_res = _MockResult(dev)
    lease_res = _MockResult(None)

    def side_effect(stmt):
        sql = str(stmt).lower()
        if "from devices" in sql:
            return dev_res
        if "from device_leases" in sql:
            return lease_res
        return _MockResult(None)

    fake_db.execute.side_effect = side_effect

    mock_lease = DeviceLease(
        id=1,
        device_id=1,
        lease_token="test-token",
        owner_id=1,
        owner_label="case-run:101",
        acquired_at=datetime.now(timezone.utc),
        heartbeat_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    with (
        patch(
            "app.worker.executors.android_lowcode_executor.acquire_device_lease",
            new=AsyncMock(return_value=mock_lease),
        ) as mock_acquire,
        patch(
            "app.worker.executors.android_lowcode_executor.release_device_lease",
            new=AsyncMock(),
        ) as mock_release,
        patch(
            "app.worker.executors.android_lowcode_executor._safe_publish",
            new=AsyncMock(),
        ),
        patch(
            "app.services.android_precheck._check_adb_environment_state",
            return_value=(True, None),
        ),
        patch(
            "app.worker.executors.android_lowcode_executor._run_android_lowcode_steps",
            new=AsyncMock(),
        ) as mock_run_steps,
    ):
        await run_android_lowcode(fake_db, run, case, {})

        assert mock_acquire.called
        assert mock_release.called
        # 步骤被阻断，未进入执行
        assert not mock_run_steps.called
        assert run.status == RunStatus.error
        assert "执行前预检失败" in run.error_message
        assert "MISSING_LOCATOR" in run.error_message


@pytest.mark.asyncio
async def test_api_precheck_case_route():
    from app.api.v1.cases.runs import precheck_case
    from app.schemas.android_precheck import CasePrecheckIn
    from app.models.project import Module
    from app.models.user import User, UserRole

    user = User(id=1, username="tester", role=UserRole.tester)
    module = Module(id=1, project_id=10, name="核心模块")
    case = TestCase(
        id=5,
        module_id=1,
        name="测试用例",
        case_type=CaseType.android,
        config={"device_serial": "android-online-1", "steps": [{"action": "click", "params": {"text": "确定"}}]},
    )
    dev = Device(id=1, serial="android-online-1", status=DeviceStatus.online)
    db = _FakePrecheckDB(devices=[dev])

    async def fake_get(model, ident):
        if model is TestCase:
            return case if ident == 5 else None
        if model is Module:
            return module if ident == 1 else None
        return await db.get(model, ident)

    db.get = fake_get

    with patch("app.api.v1.cases.runs.assert_project_access", new=AsyncMock()):
        res = await precheck_case(5, CasePrecheckIn(), db, user)
        assert res.ok is True
        assert res.summary.total_steps == 1


def test_draft_precheck_route_precedes_dynamic_case_route():
    from app.api.v1.cases.runs import router

    paths = [route.path for route in router.routes]
    assert paths.index("/cases/android/precheck") < paths.index("/cases/{case_id}/precheck")


@pytest.mark.asyncio
async def test_api_precheck_android_draft_route():
    from app.api.v1.cases.runs import precheck_android_draft
    from app.schemas.android_precheck import AndroidDraftPrecheckIn
    from app.models.user import User, UserRole

    user = User(id=1, username="tester", role=UserRole.tester)
    dev = Device(id=1, serial="android-online-1", status=DeviceStatus.online)
    db = _FakePrecheckDB(devices=[dev])

    payload = AndroidDraftPrecheckIn(
        project_id=10,
        device_serial="android-online-1",
        steps=[{"action": "click", "params": {"x": 100, "y": 200}}],
    )

    with patch("app.api.v1.cases.runs.assert_project_access", new=AsyncMock()):
        res = await precheck_android_draft(payload, db, user)
        assert res.ok is True
        assert res.summary.passed_steps == 1
        assert res.summary.failed_steps == 0
