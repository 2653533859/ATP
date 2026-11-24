"""Unified Hermes project-aware streaming chat and action proposal helpers."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import CaseStatus, CaseType, RunStatus, TestCase, TestRun
from app.models.defect import Defect
from app.models.environment import EnvVariable, Environment
from app.models.plan import TestPlan
from app.models.project import Module, Project
from app.models.requirement import RequirementCaseLink, TestRequirement
from app.models.suite import TestSuite
from app.models.user import User
from app.schemas.hermes_tools import (
    HermesFailedTasksArguments,
    HermesQualityTrendArguments,
    HermesRunDetailArguments,
)
from app.services.ai_governance import redact_llm_text
from app.services.hermes_tools import execute_read_tool

logger = logging.getLogger(__name__)

_ACTION_START_TAG = "[[ACTION_PROPOSAL]]"
_ACTION_END_TAG = "[[/ACTION_PROPOSAL]]"

ChatActionType = Literal[
    "run_case",
    "run_suite",
    "create_case",
    "update_case",
    "create_defect",
    "update_defect",
    "create_knowledge",
]
_ALLOWED_ACTIONS: set[str] = {
    "run_case",
    "run_suite",
    "create_case",
    "update_case",
    "create_defect",
    "update_defect",
    "create_knowledge",
}

_FAILURE_RE = re.compile(r"(失败|报错|异常|挂了|通过率|质量|趋势|任务|运行|run|fail|error|quality)", re.IGNORECASE)
_CASE_RE = re.compile(r"(用例|脚本|场景|case|列表|有哪些|查找|搜索|运行|执行|修改|更新|修复)", re.IGNORECASE)
_SUITE_PLAN_RE = re.compile(r"(套件|计划|回归|定时|调度|suite|plan)", re.IGNORECASE)
_REQ_RE = re.compile(r"(需求|覆盖率|遗漏|追溯|requirement|coverage)", re.IGNORECASE)
_DEFECT_RE = re.compile(r"(缺陷|bug|问题单|defect|issue)", re.IGNORECASE)
_ENV_RE = re.compile(r"(环境|域名|地址|url|变量|env|variable)", re.IGNORECASE)
_SECRET_KEY_RE = re.compile(r"(pass|secret|token|key|pwd|auth)", re.IGNORECASE)
_RUN_ID_RE = re.compile(r"(?:运行|执行|run)\s*[#＃:]?\s*(\d+)", re.IGNORECASE)
_CASE_ID_RE = re.compile(r"(?:用例|case)\s*[#＃:]?\s*(\d+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ChatToolEvent:
    tool: str
    label: str
    summary: str


async def _fetch_project_overview(db: AsyncSession, project_id: int) -> dict[str, Any]:
    project = await db.get(Project, project_id)
    if not project:
        return {}

    modules_res = await db.execute(
        select(Module.id, Module.name).where(Module.project_id == project_id).order_by(Module.id.asc()).limit(20)
    )
    modules = [{"id": row.id, "name": row.name} for row in modules_res.all()]

    envs_res = await db.execute(
        select(Environment.id, Environment.name)
        .where(Environment.project_id == project_id)
        .order_by(Environment.id.asc())
        .limit(20)
    )
    environments = [{"id": row.id, "name": row.name} for row in envs_res.all()]

    case_counts_res = await db.execute(
        select(TestCase.case_type, func.count(TestCase.id))
        .join(Module, TestCase.module_id == Module.id)
        .where(Module.project_id == project_id)
        .group_by(TestCase.case_type)
    )
    case_breakdown = {str(getattr(row[0], "value", row[0])): int(row[1]) for row in case_counts_res.all()}

    recent_runs_res = await db.execute(
        select(TestRun.id, TestRun.status, TestCase.name)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .join(Module, TestCase.module_id == Module.id)
        .where(Module.project_id == project_id)
        .order_by(TestRun.id.desc())
        .limit(10)
    )
    recent_runs = [
        {"run_id": row.id, "status": str(getattr(row.status, "value", row.status)), "case_name": row.name}
        for row in recent_runs_res.all()
    ]

    return {
        "project": {"id": project.id, "name": project.name, "description": project.description or ""},
        "modules": modules,
        "environments": environments,
        "case_total": sum(case_breakdown.values()),
        "case_breakdown": case_breakdown,
        "recent_runs": recent_runs,
    }


async def _fetch_project_cases(db: AsyncSession, project_id: int, limit: int = 20) -> list[dict[str, Any]]:
    res = await db.execute(
        select(TestCase.id, TestCase.name, TestCase.case_type, TestCase.status, Module.name.label("module_name"))
        .join(Module, TestCase.module_id == Module.id)
        .where(Module.project_id == project_id)
        .order_by(TestCase.id.desc())
        .limit(limit)
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "case_type": str(getattr(row.case_type, "value", row.case_type)),
            "status": str(getattr(row.status, "value", row.status)),
            "module_name": row.module_name,
        }
        for row in res.all()
    ]


async def _fetch_case_detail(db: AsyncSession, project_id: int, case_id: int) -> dict[str, Any] | None:
    res = await db.execute(
        select(TestCase, Module.name.label("module_name"))
        .join(Module, TestCase.module_id == Module.id)
        .where(TestCase.id == case_id, Module.project_id == project_id)
    )
    row = res.first()
    if not row:
        return None
    case: TestCase = row[0]
    return {
        "id": case.id,
        "name": case.name,
        "case_type": str(getattr(case.case_type, "value", case.case_type)),
        "status": str(getattr(case.status, "value", case.status)),
        "module_name": row[1],
        "description": case.description or "",
        "config": case.config or {},
    }


async def _fetch_suites_and_plans(db: AsyncSession, project_id: int) -> dict[str, Any]:
    suites_res = await db.execute(
        select(TestSuite.id, TestSuite.name, TestSuite.description)
        .where(TestSuite.project_id == project_id)
        .order_by(TestSuite.id.desc())
        .limit(15)
    )
    plans_res = await db.execute(
        select(TestPlan.id, TestPlan.name, TestPlan.cron_expression, TestPlan.is_enabled)
        .where(TestPlan.project_id == project_id)
        .order_by(TestPlan.id.desc())
        .limit(15)
    )
    return {
        "suites": [{"id": r.id, "name": r.name, "description": r.description or ""} for r in suites_res.all()],
        "plans": [
            {"id": r.id, "name": r.name, "cron_expression": r.cron_expression or "", "is_enabled": bool(r.is_enabled)}
            for r in plans_res.all()
        ],
    }


async def _fetch_requirements(db: AsyncSession, project_id: int) -> list[dict[str, Any]]:
    req_res = await db.execute(
        select(
            TestRequirement.id,
            TestRequirement.requirement_code,
            TestRequirement.title,
            TestRequirement.status,
            TestRequirement.priority,
            func.count(RequirementCaseLink.id).label("linked_cases"),
        )
        .outerjoin(RequirementCaseLink, RequirementCaseLink.requirement_id == TestRequirement.id)
        .where(TestRequirement.project_id == project_id)
        .group_by(TestRequirement.id)
        .order_by(TestRequirement.id.desc())
        .limit(20)
    )
    return [
        {
            "id": r.id,
            "code": r.requirement_code or "",
            "title": r.title,
            "status": r.status,
            "priority": r.priority,
            "linked_cases": int(r.linked_cases),
        }
        for r in req_res.all()
    ]


async def _fetch_defects(db: AsyncSession, project_id: int) -> list[dict[str, Any]]:
    res = await db.execute(
        select(Defect.id, Defect.title, Defect.status, Defect.priority, Defect.case_id)
        .where(Defect.project_id == project_id)
        .order_by(Defect.id.desc())
        .limit(15)
    )
    return [
        {"id": r.id, "title": r.title, "status": r.status, "priority": r.priority, "case_id": r.case_id}
        for r in res.all()
    ]


async def _fetch_env_configs(db: AsyncSession, project_id: int) -> list[dict[str, Any]]:
    env_res = await db.execute(
        select(Environment).where(Environment.project_id == project_id).order_by(Environment.id.asc()).limit(10)
    )
    envs = env_res.scalars().all()
    output: list[dict[str, Any]] = []
    for env in envs:
        var_res = await db.execute(
            select(EnvVariable).where(EnvVariable.env_id == env.id).order_by(EnvVariable.id.asc()).limit(25)
        )
        vars_list = []
        for var in var_res.scalars().all():
            masked = bool(var.is_secret) or bool(_SECRET_KEY_RE.search(var.key or ""))
            vars_list.append({"key": var.key, "value": "***" if masked else (var.value or "")[:120]})
        output.append({"id": env.id, "name": env.name, "description": env.description or "", "variables": vars_list})
    return output


async def gather_project_context_for_chat(
    db: AsyncSession,
    user: User,
    project_id: int,
    query: str,
) -> tuple[str, list[ChatToolEvent]]:
    """Collect real, permission-checked project data relevant to the user's message."""
    events: list[ChatToolEvent] = []
    sections: list[str] = []

    overview = await _fetch_project_overview(db, project_id)
    if overview:
        events.append(
            ChatToolEvent(
                tool="project_overview",
                label="项目概览",
                summary=f"用例 {overview.get('case_total', 0)} 条 · 环境 {len(overview.get('environments', []))} 个",
            )
        )
        sections.append(f"[项目概览]\n{redact_llm_text(json.dumps(overview, ensure_ascii=False), limit=2400)}")

    if _CASE_RE.search(query) or _CASE_ID_RE.search(query):
        cases = await _fetch_project_cases(db, project_id, limit=20)
        events.append(ChatToolEvent(tool="list_cases", label="项目用例", summary=f"共 {len(cases)} 条"))
        sections.append(
            f"[项目用例列表(最近20条)]\n{redact_llm_text(json.dumps(cases, ensure_ascii=False), limit=2400)}"
        )

    case_match = _CASE_ID_RE.search(query)
    if case_match:
        cid = int(case_match.group(1))
        detail = await _fetch_case_detail(db, project_id, cid)
        if detail:
            events.append(ChatToolEvent(tool="case_detail", label=f"用例 #{cid}", summary=detail["name"]))
            sections.append(
                f"[用例 #{cid} 详情]\n{redact_llm_text(json.dumps(detail, ensure_ascii=False), limit=2400)}"
            )

    if _SUITE_PLAN_RE.search(query):
        sp = await _fetch_suites_and_plans(db, project_id)
        s_cnt = len(sp.get("suites") or [])
        p_cnt = len(sp.get("plans") or [])
        events.append(ChatToolEvent(tool="suites_plans", label="套件与计划", summary=f"套件 {s_cnt} · 计划 {p_cnt}"))
        sections.append(f"[测试套件与计划]\n{redact_llm_text(json.dumps(sp, ensure_ascii=False), limit=2000)}")

    if _REQ_RE.search(query):
        reqs = await _fetch_requirements(db, project_id)
        events.append(ChatToolEvent(tool="requirements", label="需求覆盖", summary=f"{len(reqs)} 条"))
        sections.append(f"[需求与用例关联数]\n{redact_llm_text(json.dumps(reqs, ensure_ascii=False), limit=2000)}")

    if _DEFECT_RE.search(query):
        defects = await _fetch_defects(db, project_id)
        events.append(ChatToolEvent(tool="defects", label="项目缺陷", summary=f"{len(defects)} 条"))
        sections.append(f"[项目近期缺陷]\n{redact_llm_text(json.dumps(defects, ensure_ascii=False), limit=1800)}")

    if _ENV_RE.search(query):
        envs = await _fetch_env_configs(db, project_id)
        events.append(ChatToolEvent(tool="env_configs", label="环境配置", summary=f"{len(envs)} 套"))
        sections.append(f"[环境与非敏感变量]\n{redact_llm_text(json.dumps(envs, ensure_ascii=False), limit=1800)}")

    if _FAILURE_RE.search(query):
        try:
            failed = await execute_read_tool(
                db,
                user,
                project_id,
                "failed_tasks",
                HermesFailedTasksArguments(limit=8),
            )
            items = (failed.data or {}).get("items") or []
            events.append(ChatToolEvent(tool="failed_tasks", label="失败任务", summary=f"{len(items)} 条"))
            sections.append(
                f"[最近失败任务]\n{redact_llm_text(json.dumps(failed.data, ensure_ascii=False), limit=2400)}"
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("failed_tasks context skipped: %s", exc)

        try:
            trend = await execute_read_tool(
                db,
                user,
                project_id,
                "quality_trend",
                HermesQualityTrendArguments(days=30, aggregate="daily"),
            )
            events.append(ChatToolEvent(tool="quality_trend", label="质量趋势", summary="近30天"))
            sections.append(f"[质量趋势]\n{redact_llm_text(json.dumps(trend.data, ensure_ascii=False), limit=1200)}")
        except Exception as exc:  # noqa: BLE001
            logger.debug("quality_trend context skipped: %s", exc)

    run_match = _RUN_ID_RE.search(query)
    if run_match:
        run_id = int(run_match.group(1))
        try:
            run_detail = await execute_read_tool(
                db,
                user,
                project_id,
                "run_detail",
                HermesRunDetailArguments(task_type="case", run_id=run_id),
            )
            events.append(ChatToolEvent(tool="run_detail", label=f"运行 #{run_id}", summary="已读取"))
            sections.append(
                f"[运行 #{run_id} 详情]\n{redact_llm_text(json.dumps(run_detail.data, ensure_ascii=False), limit=2000)}"
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("run_detail context skipped: %s", exc)

    return "\n\n".join(sections), events


def build_agent_system_prompt(has_project: bool) -> str:
    base = (
        "你是 ATP 测试平台的智能助手 Hermes，擅长测试策略、用例设计、接口/UI 自动化排障与软件工程问答。"
        "请用简洁清晰的 Markdown 回复。"
    )
    if not has_project:
        return base
    return (
        base
        + "\n当前对话已关联项目，下方提供了该项目的真实数据快照，请严格基于真实数据回答，不要编造不存在的用例 ID、运行 ID 或数据。\n"
        "当且仅当用户明确要求你对项目执行某项操作（如运行用例、创建用例、创建缺陷、沉淀知识）时，"
        "在回复最后追加一个待用户确认的 JSON 操作块（格式必须严格如下，且不要放进代码块里）：\n"
        f"{_ACTION_START_TAG}"
        '{"action":"run_case|run_suite|create_case|update_case|create_defect|update_defect|create_knowledge","title":"简短操作标题","summary":"关键参数说明","params":{...}}'
        f"{_ACTION_END_TAG}\n"
        "各操作 params 规范：\n"
        '- run_case: {"case_id": 用例ID整数, "env_id": 可选环境ID或null}\n'
        '- run_suite: {"suite_id": 套件ID整数, "env_id": 可选环境ID或null}\n'
        '- create_case: {"name": "用例名称", "case_type": "web|api|android", "module_id": 可选模块ID, "description": "简短说明", "steps": [...]}\n'
        '- update_case: {"case_id": 用例ID整数, "name": 可选新名称, "description": 可选说明, "steps": 可选完整步骤列表}\n'
        '- create_defect: {"title": "缺陷标题", "description": "复现与根因说明", "priority": "P1|P2|P3", "case_id": 可选用例ID}\n'
        '- update_defect: {"defect_id": 缺陷ID整数, "status": "open|in_progress|resolved|closed", "resolution": 可选处理说明}\n'
        '- create_knowledge: {"title": "知识标题", "content": "Markdown正文", "category": "troubleshooting"}\n'
        "如果用户只是询问、分析或闲聊，不要输出 [[ACTION_PROPOSAL]] 块。"
    )


def parse_action_proposal(raw_json: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw_json.strip())
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    action = str(data.get("action") or "").strip()
    if action not in _ALLOWED_ACTIONS:
        return None
    params = data.get("params") if isinstance(data.get("params"), dict) else {}
    return {
        "action": action,
        "title": str(data.get("title") or action)[:120],
        "summary": str(data.get("summary") or "")[:300],
        "params": params,
    }


def split_stream_action_tag(buffer: str) -> tuple[str, str, bool]:
    """Return (emit_text, remaining_buffer, inside_action_tag)."""
    idx = buffer.find(_ACTION_START_TAG)
    if idx != -1:
        return buffer[:idx], buffer[idx:], True
    # Keep trailing partial prefix if buffer ends with a prefix of _ACTION_START_TAG
    max_keep = len(_ACTION_START_TAG) - 1
    for size in range(min(max_keep, len(buffer)), 0, -1):
        if _ACTION_START_TAG.startswith(buffer[-size:]):
            return buffer[:-size], buffer[-size:], False
    return buffer, "", False


def extract_completed_proposal(buffer: str) -> dict[str, Any] | None:
    if _ACTION_START_TAG not in buffer:
        return None
    start = buffer.find(_ACTION_START_TAG) + len(_ACTION_START_TAG)
    end = buffer.find(_ACTION_END_TAG, start)
    raw = buffer[start:end] if end != -1 else buffer[start:]
    return parse_action_proposal(raw)


def normalize_case_type(raw: Any) -> CaseType:
    val = str(raw or "web").strip().lower()
    if val in {"api", "web", "android", "ios"}:
        return CaseType(val)
    return CaseType.web


def default_case_status() -> CaseStatus:
    return CaseStatus.draft


def default_run_status() -> RunStatus:
    return RunStatus.pending
