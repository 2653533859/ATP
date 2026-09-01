"""Permission-scoped, read-only data tools for Hermes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from pydantic import BaseModel
from sqlalchemy import Date, case as sql_case, cast as sql_cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access
from app.api.v1.workbench import _FAILED_STATUSES, _collect_tasks
from app.models.case import RunStatus, TestCase, TestRun
from app.models.knowledge import KnowledgeEntry
from app.models.mobile_special import MobileSpecialRun, MobileSpecialTask
from app.models.performance import PerformanceRun, PerformanceTest
from app.models.plan import PlanRun, TestPlan
from app.models.project import Module, Project
from app.models.requirement import RequirementCaseLink, TestRequirement
from app.models.suite import SuiteRun, TestSuite
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole
from app.schemas.hermes_tools import (
    HermesFailedTasksArguments,
    HermesKnowledgeDetailArguments,
    HermesQualityTrendArguments,
    HermesRequirementCaseLinksArguments,
    HermesRunDetailArguments,
    HermesToolDescriptor,
    HermesToolEvidence,
    HermesToolName,
    HermesToolStatus,
)
from app.services.ai_governance import redact_llm_text
from app.services.knowledge import redact_knowledge_tags, redact_knowledge_text


HERMES_TOOL_TIMEOUT_MAX_MS = 5_000
_TOOL_ARGUMENT_MODELS: dict[HermesToolName, type[BaseModel]] = {
    "failed_tasks": HermesFailedTasksArguments,
    "run_detail": HermesRunDetailArguments,
    "quality_trend": HermesQualityTrendArguments,
    "requirement_case_links": HermesRequirementCaseLinksArguments,
    "knowledge_detail": HermesKnowledgeDetailArguments,
}
_TOOL_DESCRIPTIONS: dict[HermesToolName, str] = {
    "failed_tasks": "查询当前项目最近的失败、异常或取消任务。",
    "run_detail": "读取当前项目指定运行的脱敏执行摘要。",
    "quality_trend": "读取当前项目已完成用例运行的通过率趋势。",
    "requirement_case_links": "读取当前项目需求与用例的追踪关联。",
    "knowledge_detail": "读取当前项目或已发布全局知识条目的脱敏详情。",
}


@dataclass(frozen=True, slots=True)
class HermesToolExecution:
    status: HermesToolStatus
    data: dict[str, Any]
    evidence: list[HermesToolEvidence]
    message: str | None = None


def parse_tool_arguments(tool: HermesToolName, arguments: dict[str, Any]) -> BaseModel:
    """Validate one allow-listed tool's arguments and reject unknown fields."""

    return _TOOL_ARGUMENT_MODELS[tool].model_validate(arguments)


def tool_catalog() -> list[HermesToolDescriptor]:
    return [
        HermesToolDescriptor(
            name=tool,
            description=_TOOL_DESCRIPTIONS[tool],
            timeout_max_ms=HERMES_TOOL_TIMEOUT_MAX_MS,
            arguments_schema=_TOOL_ARGUMENT_MODELS[tool].model_json_schema(),
        )
        for tool in _TOOL_ARGUMENT_MODELS
    ]


def _value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _safe_text(value: Any, limit: int = 1_000) -> str:
    return redact_knowledge_text(None if value is None else str(value), limit=limit) or ""


def _safe_json(value: Any, limit: int = 4_000) -> str:
    try:
        serialized = json.dumps(value or {}, ensure_ascii=False, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        serialized = str(value)
    return redact_llm_text(serialized, limit=limit).strip()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _evidence(
    *,
    evidence_id: str,
    source_ref: str,
    title: str,
    excerpt: str,
    path: str,
) -> HermesToolEvidence:
    return HermesToolEvidence(
        evidence_id=evidence_id,
        source_ref=source_ref,
        title=_safe_text(title, 256),
        excerpt=_safe_text(excerpt, 800),
        path=path,
    )


async def _failed_tasks(
    db: AsyncSession,
    user: User,
    project_id: int,
    arguments: HermesFailedTasksArguments,
) -> HermesToolExecution:
    items, has_more = await _collect_tasks(
        db,
        user,
        project_id,
        _FAILED_STATUSES,
        arguments.task_type,
        arguments.limit,
    )
    data_items: list[dict[str, Any]] = []
    evidence: list[HermesToolEvidence] = []
    for item in items:
        error_message = _safe_text(item.error_message, 800) or "未提供错误摘要"
        path = item.detail_path
        data_items.append(
            {
                "id": item.id,
                "task_type": item.task_type,
                "run_id": item.run_id,
                "source_id": item.source_id,
                "name": _safe_text(item.name, 256),
                "status": item.status,
                "error_message": error_message,
                "created_at": _iso(item.created_at),
                "path": path,
            }
        )
        evidence.append(
            _evidence(
                evidence_id=f"failed-task:{item.task_type}:{item.run_id}",
                source_ref=f"HERMES-TASK-{item.task_type.upper()}-{item.run_id}",
                title=item.name,
                excerpt=error_message,
                path=path,
            )
        )
    return HermesToolExecution(
        status="ok" if data_items else "empty",
        data={"items": data_items, "count": len(data_items), "has_more": has_more},
        evidence=evidence,
        message=None if data_items else "当前项目没有失败或异常任务",
    )


async def _load_run_detail(
    db: AsyncSession,
    project_id: int,
    task_type: str,
    run_id: int,
) -> dict[str, Any] | None:
    run: Any
    name: str
    actual_project_id: int | None
    path: str
    summary: Any
    if task_type == "case":
        run = await db.get(TestRun, run_id)
        case = await db.get(TestCase, run.case_id) if run else None
        module = await db.get(Module, case.module_id) if case else None
        if not run or not case or not module:
            return None
        name, actual_project_id = case.name, module.project_id
        path = f"/runs/{run_id}?project_id={actual_project_id}"
        summary = run.result_summary
    elif task_type == "suite":
        run = await db.get(SuiteRun, run_id)
        suite = await db.get(TestSuite, run.suite_id) if run else None
        if not run or not suite:
            return None
        name, actual_project_id = suite.name, suite.project_id
        path = f"/suites?project_id={actual_project_id}&run_id={run_id}"
        summary = run.result_summary
    elif task_type == "plan":
        run = await db.get(PlanRun, run_id)
        plan = await db.get(TestPlan, run.plan_id) if run else None
        if not run or not plan:
            return None
        name, actual_project_id = plan.name, plan.project_id
        path = f"/plans?project_id={actual_project_id}&run_id={run_id}"
        summary = run.result_summary
    elif task_type == "android":
        run = await db.get(MobileSpecialRun, run_id)
        task = await db.get(MobileSpecialTask, run.task_id) if run else None
        if not run or not task:
            return None
        name, actual_project_id = task.name, task.project_id
        path = f"/mobile-special/reports/{run_id}?project_id={actual_project_id}"
        summary = run.summary_json
    else:
        run = await db.get(PerformanceRun, run_id)
        performance_test = await db.get(PerformanceTest, run.performance_test_id) if run else None
        if not run or not performance_test:
            return None
        name, actual_project_id = performance_test.name, run.project_id
        path = f"/system/performance?project_id={actual_project_id}&run_id={run_id}"
        summary = run.summary

    if actual_project_id != project_id:
        return None
    return {
        "task_type": task_type,
        "run_id": run_id,
        "name": _safe_text(name, 256),
        "project_id": project_id,
        "status": _value(run.status),
        "environment": _safe_text(getattr(run, "environment", None), 128) or None,
        "duration_ms": getattr(run, "duration_ms", None),
        "error_message": _safe_text(getattr(run, "error_message", None), 1_000) or None,
        "result_summary": _safe_json(summary),
        "created_at": _iso(getattr(run, "created_at", None)),
        "started_at": _iso(getattr(run, "started_at", None)),
        "finished_at": _iso(getattr(run, "finished_at", None)),
        "path": path,
    }


async def _run_detail(
    db: AsyncSession,
    project_id: int,
    arguments: HermesRunDetailArguments,
) -> HermesToolExecution:
    item = await _load_run_detail(db, project_id, arguments.task_type, arguments.run_id)
    if item is None:
        return HermesToolExecution(status="not_found", data={}, evidence=[], message="运行记录不存在或不属于当前项目")
    evidence = [
        _evidence(
            evidence_id=f"run:{arguments.task_type}:{arguments.run_id}",
            source_ref=f"HERMES-RUN-{arguments.task_type.upper()}-{arguments.run_id}",
            title=item["name"],
            excerpt=item["error_message"] or f"运行状态：{item['status']}",
            path=item["path"],
        )
    ]
    return HermesToolExecution(status="ok", data=item, evidence=evidence)


async def _quality_trend(
    db: AsyncSession,
    project_id: int,
    arguments: HermesQualityTrendArguments,
) -> HermesToolExecution:
    since = datetime.now(timezone.utc) - timedelta(days=arguments.days)
    date_column = (
        func.date_trunc("week", TestRun.created_at)
        if arguments.aggregate == "weekly"
        else sql_cast(TestRun.created_at, Date)
    ).label("date")
    statement = (
        select(
            date_column,
            func.count(TestRun.id).label("total"),
            func.sum(sql_case((TestRun.status == RunStatus.passed, 1), else_=0)).label("passed"),
        )
        .join(TestCase, TestRun.case_id == TestCase.id)
        .join(Module, TestCase.module_id == Module.id)
        .where(
            Module.project_id == project_id,
            TestRun.created_at >= since,
            TestRun.status.in_([RunStatus.passed, RunStatus.failed, RunStatus.error]),
        )
        .group_by(date_column)
        .order_by(date_column)
    )
    rows = (await db.execute(statement)).all()
    items = [
        {
            "date": str(row.date)[:10],
            "total": int(row.total or 0),
            "passed": int(row.passed or 0),
            "rate": round((row.passed or 0) / row.total * 100, 1) if row.total else 0.0,
        }
        for row in rows
    ]
    path = f"/statistics/pass-rate-trend?project_id={project_id}&days={arguments.days}&aggregate={arguments.aggregate}"
    evidence = (
        [
            _evidence(
                evidence_id=f"quality-trend:{arguments.days}:{arguments.aggregate}",
                source_ref=f"HERMES-QUALITY-{arguments.aggregate.upper()}-{arguments.days}",
                title="项目通过率趋势",
                excerpt=f"返回 {len(items)} 个时间段的已完成运行通过率",
                path=path,
            )
        ]
        if items
        else []
    )
    return HermesToolExecution(
        status="ok" if items else "empty",
        data={"days": arguments.days, "aggregate": arguments.aggregate, "items": items},
        evidence=evidence,
        message=None if items else "当前时间范围没有已完成的用例运行",
    )


async def _requirement_case_links(
    db: AsyncSession,
    project_id: int,
    arguments: HermesRequirementCaseLinksArguments,
) -> HermesToolExecution:
    if arguments.requirement_id is not None:
        requirement = await db.get(TestRequirement, arguments.requirement_id)
        if requirement is None or requirement.project_id != project_id:
            return HermesToolExecution(status="not_found", data={}, evidence=[], message="需求不存在或不属于当前项目")
    if arguments.case_id is not None:
        case = await db.get(TestCase, arguments.case_id)
        module = await db.get(Module, case.module_id) if case else None
        if case is None or module is None or module.project_id != project_id:
            return HermesToolExecution(status="not_found", data={}, evidence=[], message="用例不存在或不属于当前项目")

    statement = (
        select(RequirementCaseLink, TestRequirement, TestCase, Module)
        .join(TestRequirement, RequirementCaseLink.requirement_id == TestRequirement.id)
        .join(TestCase, RequirementCaseLink.case_id == TestCase.id)
        .join(Module, TestCase.module_id == Module.id)
        .where(Module.project_id == project_id, TestRequirement.project_id == project_id)
    )
    if arguments.requirement_id is not None:
        statement = statement.where(RequirementCaseLink.requirement_id == arguments.requirement_id)
    if arguments.case_id is not None:
        statement = statement.where(RequirementCaseLink.case_id == arguments.case_id)
    rows = (await db.execute(statement.order_by(RequirementCaseLink.id).limit(arguments.limit + 1))).all()
    has_more = len(rows) > arguments.limit
    rows = rows[: arguments.limit]
    items: list[dict[str, Any]] = []
    evidence: list[HermesToolEvidence] = []
    for link, requirement, case, module in rows:
        if (
            link is None
            or requirement is None
            or requirement.project_id != project_id
            or case is None
            or module is None
            or module.project_id != project_id
        ):
            continue
        item = {
            "link_id": link.id,
            "requirement_id": requirement.id,
            "requirement_code": _safe_text(requirement.requirement_code, 64) or None,
            "requirement_title": _safe_text(requirement.title, 256),
            "case_id": case.id,
            "case_code": _safe_text(case.case_code, 64),
            "case_name": _safe_text(case.name, 256),
            "module_id": module.id,
            "module_name": _safe_text(module.name, 256),
            "relation_type": _value(link.relation_type),
            "criterion_ids": [_safe_text(value, 64) for value in (link.criterion_ids or [])][:50],
            "note": _safe_text(link.note, 800) or None,
        }
        items.append(item)
        evidence.append(
            _evidence(
                evidence_id=f"trace:{requirement.id}:{case.id}",
                source_ref=f"HERMES-TRACE-{requirement.id}-{case.id}",
                title=f"{item['requirement_title']} → {item['case_name']}",
                excerpt=f"关联关系：{item['relation_type']}",
                path=f"/requirements?project_id={project_id}&requirement_id={requirement.id}",
            )
        )
    return HermesToolExecution(
        status="ok" if items else "empty",
        data={"items": items, "count": len(items), "has_more": has_more},
        evidence=evidence,
        message=None if items else "当前筛选条件没有需求—用例关联",
    )


def _is_admin(user: User) -> bool:
    role = getattr(user, "role", None)
    return role in {UserRole.admin, UserRole.admin.value}


async def _knowledge_detail(
    db: AsyncSession,
    user: User,
    project_id: int,
    arguments: HermesKnowledgeDetailArguments,
) -> HermesToolExecution:
    entry = await db.get(KnowledgeEntry, arguments.knowledge_id)
    if entry is None:
        return HermesToolExecution(status="not_found", data={}, evidence=[], message="知识条目不存在")
    if entry.project_id is not None and entry.project_id != project_id:
        return HermesToolExecution(status="not_found", data={}, evidence=[], message="知识条目不存在或不属于当前项目")
    if entry.project_id is None and entry.status != "published" and not _is_admin(user):
        return HermesToolExecution(status="not_found", data={}, evidence=[], message="知识条目不存在")
    if entry.project_id is not None:
        await assert_project_access(db, user, entry.project_id, ProjectRole.viewer)
    data = {
        "knowledge_id": entry.id,
        "project_id": entry.project_id,
        "title": _safe_text(entry.title, 256),
        "source_type": _safe_text(entry.source_type, 64),
        "source_ref": _safe_text(entry.source_ref, 512) or None,
        "status": _safe_text(entry.status, 32),
        "version": entry.version or 1,
        "tags": redact_knowledge_tags(entry.tags or []),
        "summary": _safe_text(entry.summary, 2_000) or None,
        "content": _safe_text(entry.content, 8_000),
        "updated_at": _iso(entry.updated_at),
    }
    path = f"/knowledge?project_id={project_id}&knowledge_id={entry.id}"
    evidence = [
        _evidence(
            evidence_id=f"knowledge:{entry.id}",
            source_ref=f"HERMES-KNOWLEDGE-{entry.id}",
            title=entry.title,
            excerpt=entry.summary or entry.content,
            path=path,
        )
    ]
    return HermesToolExecution(status="ok", data=data, evidence=evidence)


async def execute_read_tool(
    db: AsyncSession,
    user: User,
    project_id: int,
    tool: HermesToolName,
    arguments: BaseModel,
) -> HermesToolExecution:
    """Execute only the explicitly allow-listed read tools."""

    if tool == "failed_tasks":
        return await _failed_tasks(db, user, project_id, cast(HermesFailedTasksArguments, arguments))
    if tool == "run_detail":
        return await _run_detail(db, project_id, cast(HermesRunDetailArguments, arguments))
    if tool == "quality_trend":
        return await _quality_trend(db, project_id, cast(HermesQualityTrendArguments, arguments))
    if tool == "requirement_case_links":
        return await _requirement_case_links(db, project_id, cast(HermesRequirementCaseLinksArguments, arguments))
    return await _knowledge_detail(db, user, project_id, cast(HermesKnowledgeDetailArguments, arguments))
