"""Validation and policy helpers for multi-step API scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ApiScenarioError(ValueError):
    """Raised when API scenario orchestration metadata is invalid."""


@dataclass(frozen=True)
class ApiScenarioPolicy:
    failure_strategy: str = "continue"
    context_scope: str = "scenario"
    session_lifecycle: str = "isolated"


def build_api_scenario_policy(config: dict[str, Any]) -> ApiScenarioPolicy:
    failure_strategy = str(config.get("failure_strategy", "continue")).strip().lower()
    context_scope = str(config.get("context_scope", "scenario")).strip().lower()
    raw_session_lifecycle = config.get("session_lifecycle")
    session_lifecycle = (
        str(
            raw_session_lifecycle
            if raw_session_lifecycle is not None
            else "reuse"
            if config.get("reuse_api_session")
            else "isolated"
        )
        .strip()
        .lower()
    )
    if session_lifecycle == "isolated" and config.get("reuse_api_session"):
        session_lifecycle = "reuse"
    if failure_strategy not in {"continue", "stop", "skip_dependents"}:
        raise ApiScenarioError("failure_strategy 必须是 continue、stop 或 skip_dependents")
    if context_scope not in {"scenario", "step"}:
        raise ApiScenarioError("context_scope 必须是 scenario 或 step")
    if session_lifecycle not in {"isolated", "reuse"}:
        raise ApiScenarioError("session_lifecycle 必须是 isolated 或 reuse")
    return ApiScenarioPolicy(failure_strategy, context_scope, session_lifecycle)


def step_dependencies(step: object, index: int) -> list[int]:
    if not isinstance(step, dict):
        raise ApiScenarioError(f"第 {index + 1} 个 API 步骤必须是对象")
    raw = step.get("depends_on", [])
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise ApiScenarioError(f"第 {index + 1} 个 API 步骤的 depends_on 必须是数组")
    result: list[int] = []
    for value in raw:
        try:
            dependency = int(value)
        except (TypeError, ValueError) as exc:
            raise ApiScenarioError(f"第 {index + 1} 个 API 步骤依赖编号无效") from exc
        if dependency < 0 or dependency >= index:
            raise ApiScenarioError(f"第 {index + 1} 个 API 步骤只能依赖更早的步骤")
        if dependency not in result:
            result.append(dependency)
    return result
