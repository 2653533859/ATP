"""Hermes read-tool scope, redaction, evidence, and output contracts."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.hermes_tools import (
    HermesFailedTasksArguments,
    HermesKnowledgeDetailArguments,
    HermesQualityTrendArguments,
    HermesRequirementCaseLinksArguments,
    HermesRunDetailArguments,
)
from app.schemas.workbench import WorkbenchTaskItem
from app.services import hermes_tools
from app.services.hermes_tools import (
    _failed_tasks,
    _knowledge_detail,
    _load_run_detail,
    _quality_trend,
    _requirement_case_links,
    _run_detail,
    parse_tool_arguments,
    tool_catalog,
)


class _DB:
    def __init__(self, values=None, rows=None):
        self.values = values or {}
        self.rows = rows or []

    async def get(self, model, entity_id):
        return self.values.get((model, entity_id))

    async def execute(self, _statement):
        return SimpleNamespace(all=lambda: self.rows)


def _user(role="engineer"):
    return SimpleNamespace(id=7, username="engineer", role=role)


def test_tool_catalog_is_allow_listed_and_read_only():
    catalog = tool_catalog()

    assert {item.name for item in catalog} == {
        "failed_tasks",
        "run_detail",
        "quality_trend",
        "requirement_case_links",
        "knowledge_detail",
    }
    assert all(item.read_only and item.required_role == "viewer" for item in catalog)
    assert all(item.timeout_max_ms == 5_000 for item in catalog)


def test_tool_arguments_reject_unknown_fields_and_require_trace_target():
    assert isinstance(parse_tool_arguments("failed_tasks", {"limit": 5}), HermesFailedTasksArguments)
    assert isinstance(parse_tool_arguments("run_detail", {"task_type": "case", "run_id": 1}), HermesRunDetailArguments)
    assert isinstance(parse_tool_arguments("quality_trend", {"aggregate": "weekly"}), HermesQualityTrendArguments)
    assert isinstance(
        parse_tool_arguments("knowledge_detail", {"knowledge_id": 1}),
        HermesKnowledgeDetailArguments,
    )

    with pytest.raises(ValidationError):
        parse_tool_arguments("knowledge_detail", {"knowledge_id": 1, "content": "secret"})
    with pytest.raises(ValidationError):
        parse_tool_arguments("requirement_case_links", {})


def test_failed_tasks_redacts_error_and_emits_replayable_evidence(monkeypatch):
    item = WorkbenchTaskItem(
        id="case:9",
        task_type="case",
        run_id=9,
        source_id=3,
        project_id=1,
        project_name="核心项目",
        name="登录用例",
        status="failed",
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        error_message="password=raw-secret",
        detail_path="/runs/9?project_id=1",
    )

    async def collect(*_args):
        return [item], False

    monkeypatch.setattr(hermes_tools, "_collect_tasks", collect)
    result = asyncio.run(_failed_tasks(_DB(), _user(), 1, HermesFailedTasksArguments(limit=5)))

    assert result.status == "ok"
    assert result.data["items"][0]["error_message"] != "password=raw-secret"
    assert "raw-secret" not in str(result.data)
    assert result.evidence[0].path == "/runs/9?project_id=1"
    assert result.evidence[0].source_ref == "HERMES-TASK-CASE-9"


def test_run_detail_drops_cross_project_records():
    from app.models.case import TestCase, TestRun
    from app.models.project import Module

    run = SimpleNamespace(
        id=9,
        case_id=3,
        status="failed",
        environment="staging",
        duration_ms=120,
        error_message="token=raw-token",
        result_summary={"error": "token=raw-token"},
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        started_at=None,
        finished_at=None,
    )
    case = SimpleNamespace(id=3, name="登录用例", module_id=5)
    module = SimpleNamespace(id=5, project_id=2)
    db = _DB({(TestRun, 9): run, (TestCase, 3): case, (Module, 5): module})

    assert asyncio.run(_load_run_detail(db, 1, "case", 9)) is None


def test_run_detail_returns_redacted_replayable_summary():
    from app.models.case import TestCase, TestRun
    from app.models.project import Module

    run = SimpleNamespace(
        id=9,
        case_id=3,
        status="failed",
        environment="staging",
        duration_ms=120,
        error_message="password=raw-secret",
        result_summary={"error": "token=raw-token"},
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        started_at=None,
        finished_at=None,
    )
    case = SimpleNamespace(id=3, name="登录用例", module_id=5)
    module = SimpleNamespace(id=5, project_id=1)
    result = asyncio.run(
        _run_detail(
            _DB({(TestRun, 9): run, (TestCase, 3): case, (Module, 5): module}),
            1,
            HermesRunDetailArguments(task_type="case", run_id=9),
        )
    )

    assert result.status == "ok"
    assert "raw-secret" not in str(result.data)
    assert "raw-token" not in str(result.data)
    assert result.evidence[0].path == "/runs/9?project_id=1"


def test_quality_trend_is_bounded_and_evidence_backed():
    row = SimpleNamespace(date="2026-09-01", total=4, passed=3)
    result = asyncio.run(
        _quality_trend(
            _DB(rows=[row]),
            1,
            HermesQualityTrendArguments(days=30, aggregate="daily"),
        )
    )

    assert result.status == "ok"
    assert result.data["items"] == [{"date": "2026-09-01", "total": 4, "passed": 3, "rate": 75.0}]
    assert result.evidence[0].path.endswith("days=30&aggregate=daily")


def test_requirement_links_and_knowledge_detail_are_safe_and_scoped(monkeypatch):
    from app.models.case import TestCase
    from app.models.knowledge import KnowledgeEntry
    from app.models.project import Module
    from app.models.requirement import RequirementCaseLink, TestRequirement

    requirement = SimpleNamespace(
        id=11,
        project_id=1,
        requirement_code="REQ-001",
        title="登录需求",
    )
    case = SimpleNamespace(id=3, name="登录用例", case_code="CASE-003")
    module = SimpleNamespace(id=5, name="认证", project_id=1)
    link = SimpleNamespace(
        id=21,
        relation_type="covers",
        criterion_ids=["AC-1"],
        note="token=raw-token",
    )
    link_result = asyncio.run(
        _requirement_case_links(
            _DB(
                {
                    (TestRequirement, 11): requirement,
                    (TestCase, 3): case,
                    (Module, 5): module,
                },
                rows=[(link, requirement, case, module)],
            ),
            1,
            HermesRequirementCaseLinksArguments(requirement_id=11),
        )
    )
    assert link_result.status == "ok"
    assert "raw-token" not in str(link_result.data)
    assert link_result.evidence[0].source_ref == "HERMES-TRACE-11-3"

    entry = SimpleNamespace(
        id=4,
        project_id=1,
        title="登录手册",
        source_type="runbook",
        source_ref="DOC-4",
        status="published",
        version=2,
        tags=["登录"],
        summary="password=raw-password",
        content="检查认证服务",
        updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(hermes_tools, "assert_project_access", lambda *_args: asyncio.sleep(0))
    knowledge_result = asyncio.run(
        _knowledge_detail(
            _DB({(KnowledgeEntry, 4): entry}),
            _user(),
            1,
            HermesKnowledgeDetailArguments(knowledge_id=4),
        )
    )
    assert knowledge_result.status == "ok"
    assert "raw-password" not in str(knowledge_result.data)
    assert knowledge_result.evidence[0].path.endswith("knowledge_id=4")


def test_requirement_links_drop_cross_project_requirement_rows():
    from app.models.case import TestCase
    from app.models.project import Module
    from app.models.requirement import RequirementCaseLink, TestRequirement

    requirement = SimpleNamespace(
        id=11,
        project_id=2,
        requirement_code="REQ-OTHER",
        title="其他项目需求",
    )
    case = SimpleNamespace(id=3, name="当前项目用例", case_code="CASE-003", module_id=5)
    module = SimpleNamespace(id=5, name="认证", project_id=1)
    link = SimpleNamespace(id=21, relation_type="covers", criterion_ids=[], note=None)
    result = asyncio.run(
        _requirement_case_links(
            _DB(
                {
                    (TestRequirement, 11): requirement,
                    (TestCase, 3): case,
                    (Module, 5): module,
                },
                rows=[(link, requirement, case, module)],
            ),
            1,
            HermesRequirementCaseLinksArguments(case_id=3),
        )
    )

    assert result.status == "empty"
    assert result.data["items"] == []
