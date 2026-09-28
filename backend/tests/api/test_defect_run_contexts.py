"""Defect evidence keeps each run domain bounded and project scoped."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import defects
from app.models.bootstrap import load_all_models


load_all_models()


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def scalar_one(self):
        return self.rows[0] if self.rows else None

    def scalar_one_or_none(self):
        return self.rows[0] if self.rows else None


class _DB:
    def __init__(self, objects, results=()):
        self.objects = objects
        self.results = list(results)

    async def get(self, model, _id):
        return self.objects.get(model)

    async def execute(self, _query):
        return _Result(self.results.pop(0) if self.results else [])


@pytest.mark.parametrize("run_type", ["case", "suite", "plan", "android", "performance"])
def test_run_contexts_keep_domain_evidence_and_redact_credentials(run_type):
    run = SimpleNamespace(
        status="failed",
        case_id=3,
        suite_id=3,
        plan_id=3,
        task_id=3,
        performance_test_id=3,
        project_id=1,
        environment="dev",
        trace_id="trace-1",
        error_message="token=secret",
        case_run_ids=[4],
        suite_run_ids=[5],
        summary_json={"error": "password=secret", "trace_id": "trace-1"},
        device_serial="emulator-1",
        app_package="com.example",
        raw_result_object_name="results/report.json",
    )
    source = SimpleNamespace(
        id=3,
        name="登录",
        project_id=1,
        module_id=5,
        source_type="case",
        source_id=3,
    )
    objects = {
        "case": {defects.TestRun: run, defects.TestCase: source, defects.Module: source},
        "suite": {defects.SuiteRun: run, defects.TestSuite: source},
        "plan": {defects.PlanRun: run, defects.TestPlan: source},
        "android": {defects.MobileSpecialRun: run, defects.MobileSpecialTask: source},
        "performance": {defects.PerformanceRun: run, defects.PerformanceTest: source},
    }[run_type]
    step = SimpleNamespace(
        step_index=1,
        name="请求",
        status="failed",
        error_message="api_key=secret",
        screenshot_url="https://example.test/shot.png?X-Amz-Signature=private",
    )
    artifact = SimpleNamespace(artifact_type="video", file_name="capture.mp4", file_path="video/ref", id=1)
    incident = SimpleNamespace(
        incident_type="crash", title="崩溃", detail="cookie=private", event_time=datetime.now(timezone.utc)
    )
    results = {
        "case": [[step]],
        "android": [[artifact], [incident]],
    }.get(run_type, [])

    context = asyncio.run(defects._resolve_run_context(_DB(objects, results), run_type, 7))

    assert context.project_id == 1
    assert context.status == "failed"
    assert "secret" not in str(context.evidence)
    assert "private" not in str(context.evidence)
    if run_type == "case":
        assert context.evidence["steps"][0]["screenshot_ref"] == "https://example.test/shot.png"
    if run_type == "android":
        assert context.evidence["artifact_refs"][0]["file_ref"] == "video/ref"


def test_unknown_or_missing_run_cannot_be_used_as_defect_evidence():
    with pytest.raises(HTTPException) as unsupported:
        asyncio.run(defects._resolve_run_context(_DB({}), "unknown", 7))
    assert unsupported.value.status_code == 422

    for run_type in ("case", "suite", "plan", "android", "performance"):
        with pytest.raises(HTTPException) as missing:
            asyncio.run(defects._resolve_run_context(_DB({}), run_type, 7))
        assert missing.value.status_code == 404


def test_defect_list_filters_run_and_project_without_leaking_other_records(monkeypatch):
    async def access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(defects, "assert_project_access", access)
    db = _DB({}, [[1], []])

    result = asyncio.run(
        defects.list_defects(
            project_id=1,
            case_id=2,
            run_type="case",
            run_id=3,
            status_filter="open",
            priority="P1",
            severity="major",
            page=1,
            page_size=10,
            db=db,
            user=SimpleNamespace(id=7, role="engineer"),
        )
    )

    assert result.total == 1 and result.items == []
    with pytest.raises(HTTPException) as mismatch:
        asyncio.run(
            defects.list_defects(
                project_id=None,
                case_id=None,
                run_type="case",
                run_id=None,
                status_filter=None,
                priority=None,
                severity=None,
                page=1,
                page_size=10,
                db=_DB({}),
                user=SimpleNamespace(id=7, role="engineer"),
            )
        )
    assert mismatch.value.status_code == 422


def test_defect_assignee_and_case_must_be_active_members_of_same_project():
    user = SimpleNamespace(id=7, role="engineer")
    case = SimpleNamespace(module_id=4)
    wrong_module = SimpleNamespace(project_id=2)
    db = _DB({defects.User: SimpleNamespace(is_active=False), defects.TestCase: case, defects.Module: wrong_module})

    with pytest.raises(HTTPException) as inactive:
        asyncio.run(defects._ensure_assignee(db, 1, 8, user))
    with pytest.raises(HTTPException) as wrong_project:
        asyncio.run(defects._ensure_case_project(db, 1, 9))

    assert inactive.value.status_code == 400
    assert wrong_project.value.status_code == 400
