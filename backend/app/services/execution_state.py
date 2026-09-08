"""Shared execution-state action policy for workbench task domains.

This module describes the states already persisted by each execution domain. It
does not translate or mutate stored values; callers use it to make action
availability and rejection decisions consistently while the domain executors
remain the source of truth for state transitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExecutionDomain = Literal["case", "suite", "plan", "android", "performance"]
ExecutionAction = Literal["retry", "stop"]
ActionRejectionCode = Literal["unknown_status", "unsupported_action", "status_not_allowed"]


@dataclass(frozen=True)
class ExecutionStatePolicy:
    statuses: frozenset[str]
    active: frozenset[str]
    terminal: frozenset[str]
    failed: frozenset[str]
    retryable: frozenset[str]
    stoppable: frozenset[str]


@dataclass(frozen=True)
class ExecutionActionDecision:
    allowed: bool
    rejection_code: ActionRejectionCode | None = None


EXECUTION_STATE_POLICIES: dict[ExecutionDomain, ExecutionStatePolicy] = {
    "case": ExecutionStatePolicy(
        statuses=frozenset({"pending", "running", "passed", "failed", "error", "skipped"}),
        active=frozenset({"pending", "running"}),
        terminal=frozenset({"passed", "failed", "error", "skipped"}),
        failed=frozenset({"failed", "error"}),
        retryable=frozenset({"failed", "error", "skipped"}),
        stoppable=frozenset(),
    ),
    "suite": ExecutionStatePolicy(
        statuses=frozenset({"pending", "running", "passed", "failed", "error"}),
        active=frozenset({"pending", "running"}),
        terminal=frozenset({"passed", "failed", "error"}),
        failed=frozenset({"failed", "error"}),
        retryable=frozenset({"failed", "error"}),
        stoppable=frozenset(),
    ),
    "plan": ExecutionStatePolicy(
        statuses=frozenset({"pending", "running", "passed", "failed", "error"}),
        active=frozenset({"pending", "running"}),
        terminal=frozenset({"passed", "failed", "error"}),
        failed=frozenset({"failed", "error"}),
        retryable=frozenset({"failed", "error"}),
        stoppable=frozenset(),
    ),
    "android": ExecutionStatePolicy(
        statuses=frozenset({"pending", "running", "completed", "failed", "stopped"}),
        active=frozenset({"pending", "running"}),
        terminal=frozenset({"completed", "failed", "stopped"}),
        failed=frozenset({"failed", "stopped"}),
        retryable=frozenset({"failed", "stopped"}),
        stoppable=frozenset({"pending", "running"}),
    ),
    "performance": ExecutionStatePolicy(
        statuses=frozenset({"pending", "running", "cancelling", "success", "failed", "cancelled"}),
        active=frozenset({"pending", "running", "cancelling"}),
        terminal=frozenset({"success", "failed", "cancelled"}),
        failed=frozenset({"failed", "cancelled"}),
        retryable=frozenset({"failed", "cancelled"}),
        stoppable=frozenset({"pending", "running"}),
    ),
}


def execution_policy(domain: ExecutionDomain) -> ExecutionStatePolicy:
    return EXECUTION_STATE_POLICIES[domain]


def decide_execution_action(
    domain: ExecutionDomain,
    status: str,
    action: ExecutionAction,
) -> ExecutionActionDecision:
    policy = execution_policy(domain)
    if status not in policy.statuses:
        return ExecutionActionDecision(allowed=False, rejection_code="unknown_status")

    allowed_statuses = policy.retryable if action == "retry" else policy.stoppable
    if not allowed_statuses:
        return ExecutionActionDecision(allowed=False, rejection_code="unsupported_action")
    if status not in allowed_statuses:
        return ExecutionActionDecision(allowed=False, rejection_code="status_not_allowed")
    return ExecutionActionDecision(allowed=True)


def can_execute_action(domain: ExecutionDomain, status: str, action: ExecutionAction) -> bool:
    return decide_execution_action(domain, status, action).allowed


def execution_action_rejection_detail(
    domain: ExecutionDomain,
    status: str,
    action: ExecutionAction,
    decision: ExecutionActionDecision | None = None,
) -> str:
    resolved = decision or decide_execution_action(domain, status, action)
    action_label = "重试" if action == "retry" else "停止"
    reason = {
        "unknown_status": "状态不受支持",
        "unsupported_action": f"任务类型不支持{action_label}",
        "status_not_allowed": f"当前状态不支持{action_label}",
    }.get(resolved.rejection_code or "", f"当前状态不支持{action_label}")
    return f"{domain} 任务当前状态为 {status}：{reason}"
