import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.plan import PlanRunStatus, PlanStatus, ScheduleType, TriggerType
from app.models.suite import SuiteRunStatus, SuiteStatus
from app.schemas.plan import PlanRunOut, PlanRunTrigger, TestPlanCreate, TestPlanOut, WebhookTriggerRequest
from app.schemas.suite import SuiteRunOut, SuiteRunTrigger, TestSuiteCreate, TestSuiteOut


def _now():
    return datetime.now(timezone.utc)


def test_suite_and_plan_create_schema_fields_use_default_factory():
    assert TestSuiteCreate.model_fields["case_ids"].default_factory is list
    assert TestSuiteCreate.model_fields["config"].default_factory is dict
    assert SuiteRunTrigger.model_fields["extra_vars"].default_factory is dict

    assert TestPlanCreate.model_fields["suite_ids"].default_factory is list
    assert PlanRunTrigger.model_fields["extra_vars"].default_factory is dict
    assert WebhookTriggerRequest.model_fields["extra_vars"].default_factory is dict


def test_suite_and_plan_schema_default_containers_are_not_shared():
    suite_a = TestSuiteCreate(name="suite-a", project_id=1)
    suite_b = TestSuiteCreate(name="suite-b", project_id=1)
    suite_a.case_ids.append({"case_id": 1, "sort": 0})
    suite_a.config["mode"] = "smoke"

    plan_a = TestPlanCreate(name="plan-a", project_id=1)
    plan_b = TestPlanCreate(name="plan-b", project_id=1)
    plan_a.suite_ids.append({"suite_id": 2, "sort": 0})

    trigger_a = SuiteRunTrigger()
    trigger_b = SuiteRunTrigger()
    trigger_a.extra_vars["token"] = "a"

    plan_trigger_a = PlanRunTrigger()
    plan_trigger_b = PlanRunTrigger()
    plan_trigger_a.extra_vars["env"] = "daily"

    webhook_a = WebhookTriggerRequest(plan_id=7)
    webhook_b = WebhookTriggerRequest(plan_id=7)
    webhook_a.extra_vars["branch"] = "main"

    assert suite_b.case_ids == []
    assert suite_b.config == {}
    assert plan_b.suite_ids == []
    assert trigger_b.extra_vars == {}
    assert plan_trigger_b.extra_vars == {}
    assert webhook_b.extra_vars == {}


def test_suite_and_plan_out_serialization_shape_stays_compatible():
    suite_payload = TestSuiteOut.model_validate(
        {
            "id": 1,
            "name": "Smoke Suite",
            "description": "smoke path",
            "project_id": 10,
            "status": SuiteStatus.active,
            "creator_id": 7,
            "case_ids": [{"case_id": 11, "sort": 0}],
            "parameterization": {"type": "json", "data": []},
            "config": {"retry": 1},
            "created_at": _now(),
            "updated_at": _now(),
        }
    )
    plan_payload = TestPlanOut.model_validate(
        {
            "id": 2,
            "name": "Nightly Plan",
            "description": "nightly path",
            "project_id": 10,
            "status": PlanStatus.active,
            "creator_id": 8,
            "suite_ids": [{"suite_id": 21, "sort": 0}],
            "schedule_type": ScheduleType.manual,
            "cron_expression": None,
            "webhook_secret": None,
            "is_enabled": True,
            "env_id": None,
            "last_run_at": None,
            "next_run_at": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
    )
    suite_run_payload = SuiteRunOut.model_validate(
        {
            "id": 3,
            "suite_id": 1,
            "triggered_by": 7,
            "status": SuiteRunStatus.pending,
            "environment": None,
            "duration_ms": None,
            "error_message": None,
            "result_summary": {"total": 0},
            "case_run_ids": [],
            "created_at": _now(),
        }
    )
    plan_run_payload = PlanRunOut.model_validate(
        {
            "id": 4,
            "plan_id": 2,
            "triggered_by": None,
            "trigger_type": TriggerType.manual,
            "status": PlanRunStatus.pending,
            "duration_ms": None,
            "error_message": None,
            "suite_run_ids": [],
            "result_summary": {"total": 0},
            "created_at": _now(),
        }
    )

    assert suite_payload.model_dump()["case_ids"] == [{"case_id": 11, "sort": 0}]
    assert plan_payload.model_dump()["suite_ids"] == [{"suite_id": 21, "sort": 0}]
    assert suite_run_payload.model_dump()["case_run_ids"] == []
    assert plan_run_payload.model_dump()["suite_run_ids"] == []
