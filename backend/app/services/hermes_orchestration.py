"""Bounded natural-language routing for Hermes read-only tools."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.schemas.hermes_tools import HermesToolName, HermesToolStatus


HermesOrchestrationStatus = Literal["matched", "no_match", "needs_input", "cancelled"]
HermesPendingToolName = Literal["run_detail", "requirement_case_links", "knowledge_detail"]


@dataclass(frozen=True, slots=True)
class HermesToolPlan:
    tool: HermesToolName
    arguments: dict[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class HermesPendingReadTool:
    """A sanitized, incomplete read-only intent that may be resumed once."""

    tool: HermesPendingToolName
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HermesOrchestrationPlan:
    status: HermesOrchestrationStatus
    plans: tuple[HermesToolPlan, ...] = ()
    clarification: str | None = None
    pending: HermesPendingReadTool | None = None


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
_PLAIN_ID_PATTERN = re.compile(r"\d+")
_RUN_TASK_TYPES = ("case", "suite", "plan", "android", "performance")
_PENDING_CANCELLATIONS = frozenset(
    {
        "取消",
        "取消当前查询",
        "取消查询",
        "算了",
        "不用了",
        "停止查询",
        "cancel",
        "cancel query",
        "cancel current query",
    }
)


def is_pending_cancellation(query: str) -> bool:
    """Recognize only explicit, whole-turn cancellation controls."""

    normalized = " ".join(query.strip().split()).casefold()
    return normalized in _PENDING_CANCELLATIONS


def _numeric_id(query: str) -> int | None:
    match = _ID_PATTERN.search(query) or _TARGET_ID_PATTERN.search(query)
    if match is None:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


def _run_type(query: str) -> str | None:
    for task_type in _RUN_TASK_TYPES:
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


def _plain_numeric_id(query: str) -> int | None:
    normalized = query.strip()
    if not _PLAIN_ID_PATTERN.fullmatch(normalized):
        return None
    value = int(normalized)
    return value if value > 0 else None


def _resume_numeric_id(query: str) -> int | None:
    return _numeric_id(query) or _plain_numeric_id(query)


def _trace_target(
    query: str, default: Literal["requirement", "case"] = "requirement"
) -> Literal["requirement", "case"]:
    if re.search(r"需求|requirement", query, re.IGNORECASE):
        return "requirement"
    if re.search(r"用例|\bcase\b", query, re.IGNORECASE):
        return "case"
    return default


def _run_clarification(arguments: dict[str, Any]) -> str:
    has_run_id = isinstance(arguments.get("run_id"), int) and not isinstance(arguments.get("run_id"), bool)
    has_task_type = arguments.get("task_type") in _RUN_TASK_TYPES
    if has_run_id and not has_task_type:
        return "请提供任务类型（case、suite、plan、android 或 performance），我再读取对应运行详情。"
    if has_task_type and not has_run_id:
        return "请提供运行编号，我再读取对应运行详情。"
    return "请提供运行编号和任务类型（case、suite、plan、android 或 performance）。"


def pending_tool_from_mapping(value: object) -> HermesPendingReadTool | None:
    """Deserialize only the small allow-listed pending state stored in a session."""

    if not isinstance(value, dict):
        return None
    tool = value.get("tool")
    arguments = value.get("arguments")
    source = arguments if isinstance(arguments, dict) else {}
    if tool == "run_detail":
        safe: dict[str, Any] = {}
        task_type = source.get("task_type")
        if isinstance(task_type, str) and task_type in _RUN_TASK_TYPES:
            safe["task_type"] = task_type
        run_id = source.get("run_id")
        if isinstance(run_id, int) and not isinstance(run_id, bool) and run_id > 0:
            safe["run_id"] = run_id
        return HermesPendingReadTool(tool="run_detail", arguments=safe)
    if tool == "requirement_case_links":
        target = source.get("target")
        if target in {"requirement", "case"}:
            return HermesPendingReadTool(tool="requirement_case_links", arguments={"target": target})
        return None
    if tool == "knowledge_detail":
        return HermesPendingReadTool(tool="knowledge_detail")
    return None


def pending_tool_to_mapping(pending: HermesPendingReadTool) -> dict[str, Any]:
    return {"tool": pending.tool, "arguments": dict(pending.arguments)}


def resume_pending_read_tool(query: str, pending: HermesPendingReadTool) -> HermesOrchestrationPlan:
    """Complete exactly one safe pending tool using the current turn only."""

    normalized = " ".join(query.strip().split())
    if pending.tool == "run_detail":
        arguments = dict(pending.arguments)
        run_id = _resume_numeric_id(normalized)
        if run_id is not None:
            arguments["run_id"] = run_id
        task_type = _run_type(normalized)
        if task_type:
            arguments["task_type"] = task_type
        if (
            arguments.get("task_type") in _RUN_TASK_TYPES
            and isinstance(arguments.get("run_id"), int)
            and not isinstance(arguments.get("run_id"), bool)
        ):
            return HermesOrchestrationPlan(
                status="matched",
                plans=(
                    HermesToolPlan(
                        "run_detail",
                        {"task_type": arguments["task_type"], "run_id": arguments["run_id"]},
                        "根据当前会话补全运行编号和任务类型",
                    ),
                ),
            )
        next_pending = HermesPendingReadTool(tool="run_detail", arguments=arguments)
        return HermesOrchestrationPlan(
            status="needs_input",
            clarification=_run_clarification(arguments),
            pending=next_pending,
        )

    run_id = _resume_numeric_id(normalized)
    if run_id is None:
        clarification = "请提供知识条目编号，我再读取脱敏详情。"
        if pending.tool == "requirement_case_links":
            clarification = "请提供需求或用例编号，我再读取对应的追踪关系。"
        return HermesOrchestrationPlan(status="needs_input", clarification=clarification, pending=pending)
    if pending.tool == "requirement_case_links":
        default_target = pending.arguments.get("target")
        target = _trace_target(
            normalized, default_target if default_target in {"requirement", "case"} else "requirement"
        )
        return HermesOrchestrationPlan(
            status="matched",
            plans=(
                HermesToolPlan(
                    "requirement_case_links",
                    {f"{target}_id": run_id},
                    "根据当前会话补全需求或用例编号",
                ),
            ),
        )
    return HermesOrchestrationPlan(
        status="matched",
        plans=(HermesToolPlan("knowledge_detail", {"knowledge_id": run_id}, "根据当前会话补全知识条目编号"),),
    )


def plan_read_tools(query: str) -> HermesOrchestrationPlan:
    """Map a user query to at most two allow-listed read-tool calls.

    The router deliberately uses deterministic keywords and explicit IDs. It never
    invents a target identifier or accepts a user-provided tool name/argument.
    """

    normalized = " ".join(query.strip().split())
    if is_pending_cancellation(normalized):
        return HermesOrchestrationPlan(status="no_match")
    plans: list[HermesToolPlan] = []
    if _FAILURE_PATTERN.search(normalized):
        plans.append(HermesToolPlan("failed_tasks", {"limit": 20}, "识别到失败、异常或任务相关问题"))
    if _QUALITY_PATTERN.search(normalized):
        plans.append(
            HermesToolPlan("quality_trend", {"days": 30, "aggregate": "daily"}, "识别到质量、通过率或趋势相关问题")
        )

    numeric_id = _numeric_id(normalized)
    if _TRACE_PATTERN.search(normalized) and numeric_id is not None:
        target = _trace_target(normalized)
        argument = {f"{target}_id": numeric_id}
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
            status="needs_input",
            clarification="请提供需求或用例编号，我再读取对应的追踪关系。",
            pending=HermesPendingReadTool(
                tool="requirement_case_links", arguments={"target": _trace_target(normalized)}
            ),
        )
    if _KNOWLEDGE_PATTERN.search(normalized) and numeric_id is None:
        return HermesOrchestrationPlan(
            status="needs_input",
            clarification="请提供知识条目编号，我再读取脱敏详情。",
            pending=HermesPendingReadTool(tool="knowledge_detail"),
        )
    if _RUN_PATTERN.search(normalized) and (numeric_id is None or _run_type(normalized) is None):
        arguments: dict[str, Any] = {}
        if numeric_id is not None:
            arguments["run_id"] = numeric_id
        task_type = _run_type(normalized)
        if task_type:
            arguments["task_type"] = task_type
        return HermesOrchestrationPlan(
            status="needs_input",
            clarification=_run_clarification(arguments),
            pending=HermesPendingReadTool(tool="run_detail", arguments=arguments),
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
