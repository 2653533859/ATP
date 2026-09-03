"""Bounded natural-language routing for Hermes read-only tools."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.schemas.hermes_tools import HermesToolName, HermesToolStatus


HermesOrchestrationStatus = Literal["matched", "no_match", "needs_input"]


@dataclass(frozen=True, slots=True)
class HermesToolPlan:
    tool: HermesToolName
    arguments: dict[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class HermesOrchestrationPlan:
    status: HermesOrchestrationStatus
    plans: tuple[HermesToolPlan, ...] = ()
    clarification: str | None = None


@dataclass(frozen=True, slots=True)
class HermesToolOutcome:
    tool: HermesToolName
    status: HermesToolStatus
    data: dict[str, Any]


_MAX_PLANS = 2
_FAILURE_PATTERN = re.compile(r"失败|异常|取消|failed|error|task", re.IGNORECASE)
_QUALITY_PATTERN = re.compile(r"质量|通过率|趋势|指标|质量风险|quality|pass\s*rate|trend", re.IGNORECASE)
_TRACE_PATTERN = re.compile(r"需求.*用例|用例.*需求|需求.*追踪|追踪.*用例|requirement.*case|trace", re.IGNORECASE)
_KNOWLEDGE_PATTERN = re.compile(r"知识|knowledge", re.IGNORECASE)
_RUN_PATTERN = re.compile(r"运行详情|执行详情|run\s*detail|run", re.IGNORECASE)
_ID_PATTERN = re.compile(r"(?:编号|id|#|号)\s*[:：]?\s*(\d+)", re.IGNORECASE)
_TARGET_ID_PATTERN = re.compile(r"(?:需求|用例|知识|knowledge|case|run|运行|执行)[^\d]{0,8}(\d+)", re.IGNORECASE)


def _numeric_id(query: str) -> int | None:
    match = _ID_PATTERN.search(query) or _TARGET_ID_PATTERN.search(query)
    return int(match.group(1)) if match else None


def _run_type(query: str) -> str | None:
    for task_type in ("case", "suite", "plan", "android", "performance"):
        if re.search(rf"\b{task_type}\b", query, re.IGNORECASE):
            return task_type
    labels = {
        "用例": "case",
        "套件": "suite",
        "计划": "plan",
        "安卓": "android",
        "性能": "performance",
    }
    for label, task_type in labels.items():
        if label in query:
            return task_type
    return None


def plan_read_tools(query: str) -> HermesOrchestrationPlan:
    """Map a user query to at most two allow-listed read-tool calls.

    The router deliberately uses deterministic keywords and explicit IDs. It never
    invents a target identifier or accepts a user-provided tool name/argument.
    """

    normalized = " ".join(query.strip().split())
    plans: list[HermesToolPlan] = []
    if _FAILURE_PATTERN.search(normalized):
        plans.append(HermesToolPlan("failed_tasks", {"limit": 20}, "识别到失败、异常或任务相关问题"))
    if _QUALITY_PATTERN.search(normalized):
        plans.append(
            HermesToolPlan("quality_trend", {"days": 30, "aggregate": "daily"}, "识别到质量、通过率或趋势相关问题")
        )

    numeric_id = _numeric_id(normalized)
    if _TRACE_PATTERN.search(normalized) and numeric_id is not None:
        argument = {"requirement_id": numeric_id} if "需求" in normalized else {"case_id": numeric_id}
        plans.append(HermesToolPlan("requirement_case_links", argument, "识别到需求与用例追踪问题，并使用显式编号"))
    elif _KNOWLEDGE_PATTERN.search(normalized) and numeric_id is not None:
        plans.append(
            HermesToolPlan("knowledge_detail", {"knowledge_id": numeric_id}, "识别到知识详情问题，并使用显式编号")
        )
    elif _RUN_PATTERN.search(normalized) and numeric_id is not None:
        task_type = _run_type(normalized)
        if task_type:
            plans.append(
                HermesToolPlan(
                    "run_detail",
                    {"task_type": task_type, "run_id": numeric_id},
                    "识别到运行详情问题，并使用显式编号和任务类型",
                )
            )

    if plans:
        return HermesOrchestrationPlan(status="matched", plans=tuple(plans[:_MAX_PLANS]))
    if _TRACE_PATTERN.search(normalized) and numeric_id is None:
        return HermesOrchestrationPlan(
            status="needs_input", clarification="请提供需求或用例编号，我再读取对应的追踪关系。"
        )
    if _KNOWLEDGE_PATTERN.search(normalized) and numeric_id is None:
        return HermesOrchestrationPlan(status="needs_input", clarification="请提供知识条目编号，我再读取脱敏详情。")
    if _RUN_PATTERN.search(normalized) and (numeric_id is None or _run_type(normalized) is None):
        return HermesOrchestrationPlan(
            status="needs_input",
            clarification="请提供运行编号和任务类型（case、suite、plan、android 或 performance）。",
        )
    return HermesOrchestrationPlan(status="no_match")


def summarize_tool_outcomes(outcomes: list[HermesToolOutcome]) -> str:
    """Create a short, safe answer from already-redacted read-tool results."""

    if not outcomes:
        return "当前问题没有匹配到可执行的只读工具。"
    summaries: list[str] = []
    for outcome in outcomes:
        if outcome.tool == "failed_tasks":
            count = outcome.data.get("count", 0)
            summaries.append(
                f"失败任务工具返回 {count} 条结果。" if outcome.status == "ok" else "失败任务工具暂未返回结果。"
            )
        elif outcome.tool == "quality_trend":
            items = outcome.data.get("items", [])
            latest = items[-1] if isinstance(items, list) and items else None
            if isinstance(latest, dict):
                summaries.append(f"质量趋势返回 {len(items)} 个时间段，最近通过率为 {latest.get('rate', 0)}%。")
            else:
                summaries.append("质量趋势工具暂未返回结果。")
        elif outcome.tool == "requirement_case_links":
            summaries.append(f"需求—用例追踪工具返回 {outcome.data.get('count', 0)} 条关联。")
        elif outcome.tool == "knowledge_detail":
            summaries.append(
                "已读取知识条目的脱敏详情。" if outcome.status == "ok" else "知识条目不存在或当前项目不可见。"
            )
        elif outcome.tool == "run_detail":
            summaries.append(
                "已读取运行记录的脱敏执行摘要。" if outcome.status == "ok" else "运行记录不存在或当前项目不可见。"
            )
    return "已根据你的问题自动读取：" + "".join(summaries)
