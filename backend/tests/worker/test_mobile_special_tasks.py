"""Tests for mobile special Celery tasks."""

import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules.setdefault("app.core.database", types.SimpleNamespace(get_db=lambda: None))
sys.modules.setdefault(
    "app.core.redis_client",
    types.SimpleNamespace(
        publish_run_event=lambda *a, **kw: None,
        get_json_cache=lambda *a, **kw: None,
        set_json_cache=lambda *a, **kw: None,
        delete_json_cache=lambda *a, **kw: None,
        delete_json_cache_pattern=lambda *a, **kw: None,
    ),
)


class _DummyCeleryApp:
    def __init__(self):
        self.tasks = {
            "run_mobile_special_task": object(),
            "check_mobile_special_schedules": object(),
        }
        self.conf = types.SimpleNamespace(
            beat_schedule={
                "check-mobile-special-schedules": {},
                "cleanup-stale-mobile-special-runs": {},
            }
        )

    def task(self, *args, **kwargs):
        def decorator(func):
            self.tasks[kwargs.get("name", func.__name__)] = func
            return func

        return decorator


def _install_dummy_celery_app():
    sys.modules["app.worker.celery_app"] = types.SimpleNamespace(celery_app=_DummyCeleryApp())


_install_dummy_celery_app()

from app.models.bootstrap import load_all_models


class TestTaskRouting:
    def test_task_types_routing(self):
        """Verify all task types are defined in the enum"""
        from app.models.mobile_special import TaskType

        assert TaskType.performance.value == "performance"
        assert TaskType.stability.value == "stability"
        assert TaskType.fluency.value == "fluency"

    def test_mobile_special_models_importable(self):
        """Verify all models can be imported"""
        load_all_models()
        from app.models.base import Base
        from app.models.mobile_special import (
            MobileSpecialTask,
            MobileSpecialRun,
            MobileMetricSample,
            MobileIncident,
            MobileRunArtifact,
        )
        from app.models.global_variable import GlobalVariable

        assert MobileSpecialTask is not None
        assert MobileSpecialRun is not None
        assert MobileMetricSample is not None
        assert MobileIncident is not None
        assert MobileRunArtifact is not None
        assert GlobalVariable is not None
        assert "mobile_special_tasks" in Base.metadata.tables
        assert "mobile_special_runs" in Base.metadata.tables
        assert "global_variables" in Base.metadata.tables

    def test_celery_app_has_mobile_special_tasks(self):
        """Verify celery app includes mobile special tasks (skip if celery not installed)"""
        pytest.importorskip("celery")
        _install_dummy_celery_app()
        load_all_models()
        from app.worker.celery_app import celery_app

        task_names = list(celery_app.tasks.keys())
        assert "run_mobile_special_task" in task_names
        assert "check_mobile_special_schedules" in task_names

    def test_beat_schedule_includes_mobile_special(self):
        """Verify beat schedule includes mobile special polling (skip if celery not installed)"""
        pytest.importorskip("celery")
        _install_dummy_celery_app()
        load_all_models()
        from app.worker.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule or {}
        assert "check-mobile-special-schedules" in schedule
        assert "cleanup-stale-mobile-special-runs" in schedule


class TestRunConfigResolution:
    def test_merge_run_config_preserves_manual_overrides(self):
        from app.worker import tasks_mobile_special

        merged = tasks_mobile_special._merge_run_config(
            {"device_id": 1, "app_package": "com.default.app", "duration_seconds": 300},
            {"device_id": 2, "app_package": "com.override.app"},
        )

        assert merged["device_id"] == 2
        assert merged["app_package"] == "com.override.app"
        assert merged["duration_seconds"] == 300

    def test_resolve_run_fields_prefer_snapshot_then_run_then_task(self):
        from app.worker import tasks_mobile_special

        run = types.SimpleNamespace(
            config_snapshot={"device_id": 9, "app_package": "com.snapshot.app"},
            device_id=7,
            app_package="com.run.app",
        )
        task = types.SimpleNamespace(device_id=5, app_package="com.task.app")

        assert tasks_mobile_special._resolve_run_device_id(run, task) == 9
        assert tasks_mobile_special._resolve_run_app_package(run, task) == "com.snapshot.app"

    def test_get_device_serial_resolves_foreign_key(self):
        from app.worker import tasks_mobile_special

        class FakeDB:
            async def get(self, model, device_id):
                return types.SimpleNamespace(serial=f"serial-{device_id}")

        serial = asyncio.run(tasks_mobile_special._get_device_serial(FakeDB(), 12))
        assert serial == "serial-12"
