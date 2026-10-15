"""Exploration Circuit Breaker and Infinite Loop Protection Service (Q2.3).

Protects autonomous UI exploration from:
1. Blank screen / Black screen (zero interactive elements for consecutive steps)
2. Unrecoverable infinite loop oscillations (trapped in cyclic state transitions)
3. Consecutive action execution failures (accessibility/driver detached)
4. Maximum exploration step boundaries
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MAX_STEPS = 50
DEFAULT_MAX_ZERO_ELEMENTS = 3
DEFAULT_MAX_CONSECUTIVE_FAILURES = 4
DEFAULT_MAX_OSCILLATIONS = 5


class ExplorationCircuitBreaker:
    """Stateful circuit breaker tracking safety invariants during UI exploration."""

    def __init__(
        self,
        *,
        max_steps: int = DEFAULT_MAX_STEPS,
        max_zero_elements: int = DEFAULT_MAX_ZERO_ELEMENTS,
        max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES,
        max_oscillations: int = DEFAULT_MAX_OSCILLATIONS,
    ):
        self.max_steps = max_steps
        self.max_zero_elements = max_zero_elements
        self.max_consecutive_failures = max_consecutive_failures
        self.max_oscillations = max_oscillations

        self.total_steps: int = 0
        self.consecutive_zero_elements: int = 0
        self.consecutive_failures: int = 0
        self.oscillation_cycles: int = 0
        self.is_tripped: bool = False
        self.trip_reason: str | None = None
        self.trip_category: str | None = None

    def evaluate_step(
        self,
        *,
        element_count: int,
        last_action_success: bool = True,
        is_oscillation: bool = False,
        _screen_name: str = "",
    ) -> dict[str, Any]:
        """Evaluate a step's health indicators and trip circuit breaker if safety thresholds are breached."""
        if self.is_tripped:
            return self.get_status()

        self.total_steps += 1

        # 1. Zero-element / black screen tracking
        if element_count == 0:
            self.consecutive_zero_elements += 1
            if self.consecutive_zero_elements >= self.max_zero_elements:
                self.is_tripped = True
                self.trip_category = "black_screen_detected"
                self.trip_reason = (
                    f"连续 {self.consecutive_zero_elements} 步屏幕无任何可交互元素（黑屏/白屏/崩溃），触发熔断保护"
                )
                logger.warning(self.trip_reason)
                return self.get_status()
        else:
            self.consecutive_zero_elements = 0

        # 2. Consecutive action failure tracking
        if not last_action_success:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.max_consecutive_failures:
                self.is_tripped = True
                self.trip_category = "consecutive_action_failures"
                self.trip_reason = (
                    f"连续 {self.consecutive_failures} 次动作执行异常（驱动/Accessibility 脱节），触发熔断保护"
                )
                logger.warning(self.trip_reason)
                return self.get_status()
        else:
            self.consecutive_failures = 0

        # 3. Oscillation tracking
        if is_oscillation:
            self.oscillation_cycles += 1
            if self.oscillation_cycles >= self.max_oscillations:
                self.is_tripped = True
                self.trip_category = "infinite_loop_oscillation"
                self.trip_reason = f"检测到连续 {self.oscillation_cycles} 次状态往复振荡且无法跳出死循环，触发熔断保护"
                logger.warning(self.trip_reason)
                return self.get_status()
        else:
            if self.oscillation_cycles > 0:
                self.oscillation_cycles -= 1

        # 4. Maximum step boundary check
        if self.total_steps >= self.max_steps:
            self.is_tripped = True
            self.trip_category = "max_steps_exceeded"
            self.trip_reason = f"探索步数达到上限 {self.max_steps} 步，正常收敛终止"
            return self.get_status()

        return self.get_status()

    def get_status(self) -> dict[str, Any]:
        """Return the current circuit breaker status payload."""
        return {
            "tripped": self.is_tripped,
            "should_abort": self.is_tripped,
            "category": self.trip_category,
            "reason": self.trip_reason,
            "total_steps": self.total_steps,
            "consecutive_zero_elements": self.consecutive_zero_elements,
            "consecutive_failures": self.consecutive_failures,
            "oscillation_cycles": self.oscillation_cycles,
        }


def compile_exploration_abort_snapshot(
    circuit_breaker_status: dict[str, Any],
    *,
    session_id: str,
    last_screen_name: str,
    total_states_discovered: int = 0,
) -> dict[str, Any]:
    """Compile a structured incident artifact summarizing a tripped exploration session."""
    return {
        "session_id": session_id,
        "incident_type": "exploration_circuit_breaker_abort",
        "category": circuit_breaker_status.get("category"),
        "reason": circuit_breaker_status.get("reason"),
        "last_screen_name": last_screen_name,
        "total_steps_executed": circuit_breaker_status.get("total_steps", 0),
        "total_states_discovered": total_states_discovered,
        "details": circuit_breaker_status,
    }
