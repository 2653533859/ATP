"""Tests for mobile special tasks API."""
import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_engineer=lambda: None,
)

from app.models.bootstrap import load_all_models
from app.models.mobile_special import TaskType, SourceType, DeviceScopeType, RunStatus, TriggerType


class TestTaskModelUsage:
    def test_mobile_special_task_model_importable(self):
        load_all_models()
        from app.models.mobile_special import MobileSpecialTask
        assert MobileSpecialTask is not None

    def test_task_type_enum_values(self):
        assert TaskType.performance.value == "performance"
        assert TaskType.stability.value == "stability"
        assert TaskType.fluency.value == "fluency"

    def test_source_type_enum_values(self):
        assert SourceType.apk_only.value == "apk_only"
        assert SourceType.case.value == "case"
        assert SourceType.suite.value == "suite"
        assert SourceType.monkey.value == "monkey"

    def test_device_scope_type_enum_values(self):
        assert DeviceScopeType.single_device.value == "single_device"
        assert DeviceScopeType.device_group.value == "device_group"
        assert DeviceScopeType.manual_pick.value == "manual_pick"

    def test_run_status_enum_values(self):
        assert RunStatus.pending.value == "pending"
        assert RunStatus.running.value == "running"
        assert RunStatus.completed.value == "completed"
        assert RunStatus.failed.value == "failed"
        assert RunStatus.stopped.value == "stopped"


class TestMobileSpecialTaskSchema:
    def test_task_create_schema_fields(self):
        from app.schemas.mobile_special import MobileSpecialTaskCreate
        from app.models.mobile_special import TaskType, SourceType, DeviceScopeType

        task = MobileSpecialTaskCreate(
            name="Perf Task",
            project_id=1,
            task_type=TaskType.performance,
            source_type=SourceType.apk_only,
            device_scope_type=DeviceScopeType.single_device,
        )
        assert task.name == "Perf Task"
        assert task.project_id == 1
        assert task.schedule_enabled is False

    def test_task_create_with_schedule(self):
        from app.schemas.mobile_special import MobileSpecialTaskCreate
        from app.models.mobile_special import TaskType, SourceType, DeviceScopeType

        task = MobileSpecialTaskCreate(
            name="Scheduled Task",
            project_id=1,
            task_type=TaskType.stability,
            source_type=SourceType.monkey,
            device_scope_type=DeviceScopeType.device_group,
            schedule_enabled=True,
            cron_expression="0 2 * * *",
        )
        assert task.schedule_enabled is True
        assert task.cron_expression == "0 2 * * *"


class TestMobileSpecialRunSchema:
    def test_run_trigger_request(self):
        from app.schemas.mobile_special import RunTriggerRequest

        req = RunTriggerRequest(device_id=5, app_package="com.example.app")
        assert req.device_id == 5
        assert req.app_package == "com.example.app"

    def test_run_trigger_request_optional(self):
        from app.schemas.mobile_special import RunTriggerRequest

        req = RunTriggerRequest()
        assert req.device_id is None
        assert req.app_package is None


class TestMobileSpecialScheduleHelpers:
    def test_calc_next_run_returns_future_datetime(self, monkeypatch):
        from datetime import datetime, timezone
        from app.api.v1 import mobile_special

        class _FakeCroniter:
            def __init__(self, expression, now):
                self.expression = expression
                self.now = now

            def get_next(self, _type):
                return datetime(2026, 4, 1, 2, 0, tzinfo=timezone.utc)

        monkeypatch.setitem(sys.modules, "croniter", types.SimpleNamespace(croniter=_FakeCroniter))

        next_run = mobile_special._calc_next_run("0 2 * * *")
        assert next_run is not None

    def test_refresh_schedule_state_sets_and_clears_next_run_at(self, monkeypatch):
        from datetime import datetime, timezone
        from app.api.v1 import mobile_special
        from app.models.mobile_special import MobileSpecialTask, TaskType, SourceType, DeviceScopeType

        class _FakeCroniter:
            def __init__(self, expression, now):
                self.expression = expression
                self.now = now

            def get_next(self, _type):
                return datetime(2026, 4, 1, 2, 0, tzinfo=timezone.utc)

        monkeypatch.setitem(sys.modules, "croniter", types.SimpleNamespace(croniter=_FakeCroniter))

        task = MobileSpecialTask(
            name="Scheduled Task",
            project_id=1,
            task_type=TaskType.performance,
            source_type=SourceType.apk_only,
            device_scope_type=DeviceScopeType.single_device,
            schedule_enabled=True,
            cron_expression="0 2 * * *",
            config_json={},
            created_by=1,
        )

        mobile_special._refresh_schedule_state(task)
        assert task.next_run_at is not None

        task.schedule_enabled = False
        mobile_special._refresh_schedule_state(task)
        assert task.next_run_at is None
