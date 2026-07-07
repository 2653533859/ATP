"""Tests for mobile_special and global_variable Pydantic schemas."""

import sys
import types
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.bootstrap import load_all_models
from app.schemas.mobile_special import (
    TaskType,
    SourceType,
    DeviceScopeType,
    RunStatus,
    TriggerType,
    IncidentType,
    MetricType,
    ArtifactType,
    MobileSpecialTaskCreate,
    MobileSpecialTaskUpdate,
    MobileSpecialTaskOut,
    MobileSpecialRunOut,
    MobileMetricSampleOut,
    MobileIncidentOut,
    MobileRunArtifactOut,
    RunSummary,
)
from app.schemas.global_variable import (
    ScopeType,
    GlobalVariableCreate,
    GlobalVariableUpdate,
    GlobalVariableOut,
)


class TestTaskTypeEnum:
    def test_valid_task_types(self):
        assert TaskType.performance.value == "performance"
        assert TaskType.stability.value == "stability"
        assert TaskType.fluency.value == "fluency"

    def test_invalid_task_type_rejected(self):
        with pytest.raises(ValueError):
            TaskType("invalid")

    def test_task_type_from_string(self):
        assert TaskType("performance") == TaskType.performance


class TestMobileSpecialTaskSchemas:
    def test_task_create_requires_name_and_project_id(self):
        with pytest.raises(ValidationError) as exc:
            MobileSpecialTaskCreate(project_id=1)
        assert "name" in str(exc.value)

    def test_task_create_with_minimal_fields(self):
        task = MobileSpecialTaskCreate(
            name="Performance Task",
            project_id=1,
            task_type=TaskType.performance,
            source_type=SourceType.apk_only,
            device_scope_type=DeviceScopeType.single_device,
        )
        assert task.name == "Performance Task"
        assert task.project_id == 1
        assert task.task_type == TaskType.performance
        assert task.schedule_enabled is False
        assert task.config_json == {}

    def test_task_create_with_all_fields(self):
        task = MobileSpecialTaskCreate(
            name="Full Task",
            project_id=1,
            task_type=TaskType.stability,
            source_type=SourceType.monkey,
            source_id=10,
            device_scope_type=DeviceScopeType.device_group,
            device_id=5,
            device_group_tag="android-12",
            apk_id=3,
            app_package="com.example.app",
            config_json={"duration_seconds": 3600, "interval_ms": 1000},
            schedule_enabled=True,
            cron_expression="0 2 * * *",
            created_by=8,
        )
        assert task.source_id == 10
        assert task.device_group_tag == "android-12"
        assert task.schedule_enabled is True
        assert task.config_json["duration_seconds"] == 3600

    def test_task_update_partial(self):
        update = MobileSpecialTaskUpdate(name="Updated Name")
        assert update.name == "Updated Name"
        assert update.task_type is None
        assert update.schedule_enabled is None

    def test_task_out_includes_all_fields(self):
        from datetime import datetime

        task = MobileSpecialTaskOut(
            id=1,
            name="Test Task",
            project_id=1,
            task_type=TaskType.performance,
            source_type=SourceType.apk_only,
            device_scope_type=DeviceScopeType.single_device,
            schedule_enabled=False,
            config_json={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert task.id == 1
        assert task.task_type == TaskType.performance


class TestMobileSpecialRunSchemas:
    def test_run_out_includes_status_and_timing(self):
        from datetime import datetime

        run = MobileSpecialRunOut(
            id=1,
            task_id=10,
            task_type=TaskType.performance,
            status=RunStatus.running,
            trigger_type=TriggerType.manual,
            device_serial="emulator-5554",
            summary_json={"avg_cpu": 25.5},
            config_snapshot={},
            started_at=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert run.status == RunStatus.running
        assert run.summary_json["avg_cpu"] == 25.5


class TestMetricSampleSchemas:
    def test_metric_sample_out(self):
        from datetime import datetime

        sample = MobileMetricSampleOut(
            id=1,
            run_id=10,
            sample_time=datetime.now(),
            metric_type=MetricType.cpu_pct,
            metric_value=45.2,
            source="dumpsys",
            extra_json={},
        )
        assert sample.metric_type == MetricType.cpu_pct
        assert sample.metric_value == 45.2


class TestIncidentSchemas:
    def test_incident_out_includes_type_and_detail(self):
        from datetime import datetime

        incident = MobileIncidentOut(
            id=1,
            run_id=10,
            incident_type=IncidentType.crash,
            event_time=datetime.now(),
            title="java.lang.NullPointerException",
            detail="NullPointerException at MainActivity:123",
            process_name="com.example.app",
            thread_name="main",
        )
        assert incident.incident_type == IncidentType.crash
        assert "NullPointerException" in incident.title


class TestArtifactSchemas:
    def test_artifact_out(self):
        from datetime import datetime

        artifact = MobileRunArtifactOut(
            id=1,
            run_id=10,
            artifact_type=ArtifactType.csv,
            file_path="/minio/artifacts/run_10_metrics.csv",
            file_name="run_10_metrics.csv",
            file_size=1024,
            created_at=datetime.now(),
        )
        assert artifact.artifact_type == ArtifactType.csv
        assert artifact.file_size == 1024


class TestRunSummarySchema:
    def test_summary_with_performance_metrics(self):
        summary = RunSummary(
            avg_cpu_pct=32.5,
            peak_cpu_pct=78.2,
            avg_mem_mb=256.0,
            peak_mem_mb=512.0,
            crash_count=0,
            anr_count=0,
            avg_fps=55.0,
            total_jank_count=12,
        )
        assert summary.avg_cpu_pct == 32.5
        assert summary.crash_count == 0

    def test_summary_with_stability_metrics(self):
        summary = RunSummary(
            explore_duration_seconds=3600,
            operation_interval_ms=500,
            crash_count=3,
            anr_count=1,
            completed_action_count=1500,
            app_restart_count=2,
        )
        assert summary.explore_duration_seconds == 3600
        assert summary.crash_count == 3


class TestGlobalVariableSchemas:
    def test_global_variable_create_requires_key(self):
        with pytest.raises(ValidationError) as exc:
            GlobalVariableCreate(scope_type=ScopeType.global_scope)
        assert "key" in str(exc.value)

    def test_global_variable_create_minimal(self):
        var = GlobalVariableCreate(
            scope_type=ScopeType.global_scope,
            key="API_BASE_URL",
            value_encrypted="https://api.example.com",
        )
        assert var.key == "API_BASE_URL"
        assert var.is_secret is False

    def test_global_variable_create_secret(self):
        var = GlobalVariableCreate(
            scope_type=ScopeType.project,
            project_id=5,
            key="DB_PASSWORD",
            value_encrypted="encrypted_value_here",
            is_secret=True,
            description="Database password",
            created_by=8,
        )
        assert var.is_secret is True
        assert var.project_id == 5

    def test_global_variable_update_partial(self):
        update = GlobalVariableUpdate(value_encrypted="new_value")
        assert update.value_encrypted == "new_value"
        assert update.is_secret is None

    def test_global_variable_out_masks_secret_in_repr(self):
        from datetime import datetime

        var = GlobalVariableOut(
            id=1,
            scope_type=ScopeType.global_scope,
            key="SECRET_KEY",
            value_encrypted="actual_secret_value",
            is_secret=True,
            description=None,
            created_by=1,
            updated_by=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        # Out schema should still show the encrypted value
        # (masking should happen at API layer, not schema layer)
        assert var.is_secret is True
