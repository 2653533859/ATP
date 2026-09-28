"""Retry and stop actions dispatch only after domain and role checks."""

import asyncio
import importlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import workbench
from app.models.user import UserRole
from app.schemas.workbench import WorkbenchTaskRef


class _DB:
    def __init__(self, values):
        self.values = values

    async def get(self, model, _id):
        return self.values.get(model.__name__)


@pytest.mark.parametrize(
    ("task_type", "run_model", "source_model", "source_id_field", "module_name", "trigger_name"),
    [
        ("suite", "SuiteRun", "TestSuite", "suite_id", "app.api.v1.suites", "trigger_suite_run"),
        ("plan", "PlanRun", "TestPlan", "plan_id", "app.api.v1.plans", "trigger_plan_run"),
        (
            "performance",
            "PerformanceRun",
            "PerformanceTest",
            "performance_test_id",
            "app.api.v1.performance",
            "trigger_performance_run",
        ),
    ],
)
def test_retry_dispatches_failed_run_from_its_original_project(
    monkeypatch, task_type, run_model, source_model, source_id_field, module_name, trigger_name
):
    source = SimpleNamespace(
        status="failed",
        environment_id=None,
        performance_node_id=None,
        options_snapshot={},
        **{source_id_field: 3},
    )
    db = _DB({run_model: source, source_model: SimpleNamespace(project_id=1)})
    dispatched = []
    access_roles = []

    async def allow(_db, _user, project_id, role):
        access_roles.append((project_id, role))

    async def trigger(source_id, _body, _db, _user):
        dispatched.append(source_id)
        return SimpleNamespace(id=44, status="pending")

    monkeypatch.setattr(workbench, "assert_project_access", allow)
    monkeypatch.setattr(importlib.import_module(module_name), trigger_name, trigger)

    result = asyncio.run(
        workbench._retry_task(
            WorkbenchTaskRef(task_type=task_type, run_id=9), db, SimpleNamespace(id=7, role=UserRole.engineer)
        )
    )

    assert dispatched == [3]
    assert access_roles == [(1, workbench.ProjectRole.editor)]
    assert result.new_run_id == 44 and result.action == "retry"


@pytest.mark.parametrize("task_type", ["case", "suite", "plan", "android", "performance"])
def test_retry_missing_run_does_not_dispatch(task_type):
    with pytest.raises(HTTPException) as missing:
        asyncio.run(
            workbench._retry_task(
                WorkbenchTaskRef(task_type=task_type, run_id=9),
                _DB({}),
                SimpleNamespace(id=7, role=UserRole.engineer),
            )
        )
    assert missing.value.status_code == 404


@pytest.mark.parametrize(
    "task_type,module_name,method",
    [
        ("android", "app.api.v1.mobile_special", "stop_run"),
        ("performance", "app.api.v1.performance", "stop_performance_run"),
    ],
)
def test_stop_special_task_requires_engineer_and_returns_terminal_status(monkeypatch, task_type, module_name, method):
    seen = []

    async def stop(run_id, _db, _user):
        seen.append(run_id)
        return SimpleNamespace(status="cancelled")

    monkeypatch.setattr(importlib.import_module(module_name), method, stop)
    ref = WorkbenchTaskRef(task_type=task_type, run_id=9)
    with pytest.raises(HTTPException) as denied:
        asyncio.run(workbench._stop_task(ref, _DB({}), SimpleNamespace(role=UserRole.tester)))
    assert denied.value.status_code == 403

    result = asyncio.run(workbench._stop_task(ref, _DB({}), SimpleNamespace(role=UserRole.engineer)))
    assert seen == [9]
    assert result.action == "stop" and result.status == "cancelled"
