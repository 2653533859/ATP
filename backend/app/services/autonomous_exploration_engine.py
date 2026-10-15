"""State-Tree Based Autonomous Exploration and Traversal Engine (Q2.1).

Models UI screens (Web DOM / Mobile Accessibility Trees) into a Finite State
Machine (FSM) graph and guides BFS/DFS exploration with cycle detection and anti-looping.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.services.exploration_circuit_breaker import ExplorationCircuitBreaker

logger = logging.getLogger(__name__)


def compute_element_signature(element: dict[str, Any]) -> str:
    """Compute a deterministic unique signature for an interactive UI element."""
    tag = str(element.get("tag") or element.get("class_name") or "element").strip().lower()
    res_id = str(element.get("id") or element.get("resource_id") or element.get("accessibility_id") or "").strip()
    text = str(element.get("text") or element.get("title") or "").strip()[:64]
    bounds = str(element.get("bounds") or element.get("rect") or "")
    raw = f"{tag}|{res_id}|{text}|{bounds}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def compute_page_state_hash(
    elements: list[dict[str, Any]],
    current_screen_name: str = "",
) -> str:
    """Compute a structural fingerprint representing the current page state."""
    elem_signatures = sorted(compute_element_signature(e) for e in elements if isinstance(e, dict))
    content = f"{current_screen_name}|" + ",".join(elem_signatures)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]


class ExplorationState:
    """Represents a unique UI screen state in the exploration FSM graph."""

    def __init__(self, state_id: str, screen_name: str, elements: list[dict[str, Any]], depth: int = 0):
        self.state_id = state_id
        self.screen_name = screen_name
        self.elements = elements
        self.depth = depth
        self.visited_actions: set[str] = set()

        # Build candidate actions from interactive elements
        self.candidate_actions: list[dict[str, Any]] = []
        for e in elements:
            if not isinstance(e, dict):
                continue
            sig = compute_element_signature(e)
            action_type = "click"
            tag = str(e.get("tag") or e.get("class_name") or "").lower()
            if "edit" in tag or "input" in tag or "text" in tag and e.get("editable"):
                action_type = "input"

            self.candidate_actions.append(
                {
                    "action_signature": sig,
                    "action_type": action_type,
                    "element": e,
                }
            )


class AutonomousExplorationGraph:
    """Graph maintaining states, transitions, and anti-loop exploration traversal."""

    def __init__(self, strategy: str = "bfs", max_depth: int = 6):
        self.strategy = strategy.lower()  # bfs | dfs
        self.max_depth = max_depth
        self.circuit_breaker = ExplorationCircuitBreaker()
        self.states: dict[str, ExplorationState] = {}
        self.transitions: list[dict[str, Any]] = []
        self.current_state_id: str | None = None
        self.last_action: dict[str, Any] | None = None
        self.recent_state_history: list[str] = []

    def update_state(
        self,
        elements: list[dict[str, Any]],
        screen_name: str = "",
    ) -> ExplorationState:
        """Process current screen elements, update graph state, and record transition."""
        state_id = compute_page_state_hash(elements, screen_name)
        curr_depth = 0

        if self.current_state_id and self.current_state_id in self.states:
            prev_state = self.states[self.current_state_id]
            curr_depth = prev_state.depth + 1
            if self.last_action:
                self.transitions.append(
                    {
                        "from_state": self.current_state_id,
                        "to_state": state_id,
                        "action_signature": self.last_action.get("action_signature"),
                        "action_type": self.last_action.get("action_type"),
                    }
                )

        if state_id not in self.states:
            new_state = ExplorationState(state_id, screen_name, elements, depth=curr_depth)
            self.states[state_id] = new_state

        state = self.states[state_id]
        self.current_state_id = state_id

        # Track recent history for loop detection
        self.recent_state_history.append(state_id)
        if len(self.recent_state_history) > 10:
            self.recent_state_history.pop(0)

        # Evaluate circuit breaker invariants
        is_osc = self.detect_oscillation_loop()
        self.circuit_breaker.evaluate_step(
            element_count=len(elements),
            last_action_success=True,
            is_oscillation=is_osc,
            _screen_name=screen_name,
        )

        return state

    def detect_oscillation_loop(self) -> bool:
        """Detect if exploration is stuck in a 2-node or 3-node ping-pong loop."""
        hist = self.recent_state_history
        if len(hist) >= 4:
            # 2-node oscillation: A -> B -> A -> B
            if hist[-1] == hist[-3] and hist[-2] == hist[-4] and hist[-1] != hist[-2]:
                return True
        if len(hist) >= 6:
            # 3-node oscillation: A -> B -> C -> A -> B -> C
            if hist[-1] == hist[-4] and hist[-2] == hist[-5] and hist[-3] == hist[-6]:
                return True
        return False

    def select_next_action(self) -> dict[str, Any] | None:
        """Select the next optimal action to advance exploration."""
        if not self.current_state_id or self.current_state_id not in self.states:
            return None

        curr_state = self.states[self.current_state_id]

        # 0. Check circuit breaker trip condition
        cb_status = self.circuit_breaker.get_status()
        if cb_status.get("tripped"):
            logger.warning("Exploration circuit breaker tripped: %s", cb_status.get("reason"))
            return {
                "action_type": "abort",
                "action_signature": "circuit_breaker_abort",
                "reason": cb_status.get("reason"),
                "category": cb_status.get("category"),
                "element": None,
            }

        # 1. Check anti-loop oscillation
        if self.detect_oscillation_loop():
            logger.info("Oscillation loop detected at state %s, breaking out with Back action", curr_state.state_id)
            action = {"action_type": "back", "action_signature": "anti_loop_back", "element": None}
            self.last_action = action
            return action

        # 2. Check max depth limit
        if curr_state.depth >= self.max_depth:
            logger.info("Reached max exploration depth %s, backtracking", self.max_depth)
            action = {"action_type": "back", "action_signature": "depth_back", "element": None}
            self.last_action = action
            return action

        # 3. Find unvisited action in current state
        unvisited = [a for a in curr_state.candidate_actions if a["action_signature"] not in curr_state.visited_actions]
        if unvisited:
            # Pick first unvisited candidate action
            chosen = unvisited[0]
            curr_state.visited_actions.add(chosen["action_signature"])
            self.last_action = chosen
            return chosen

        # 4. State actions exhausted -> Backtrack
        action = {"action_type": "back", "action_signature": "exhausted_back", "element": None}
        self.last_action = action
        return action

    def get_coverage_metrics(self) -> dict[str, Any]:
        """Return graph exploration summary metrics."""
        total_states = len(self.states)
        total_actions_discovered = sum(len(s.candidate_actions) for s in self.states.values())
        total_actions_visited = sum(len(s.visited_actions) for s in self.states.values())
        coverage_pct = (
            round((total_actions_visited / total_actions_discovered * 100.0), 2) if total_actions_discovered else 100.0
        )

        return {
            "total_states": total_states,
            "total_actions_discovered": total_actions_discovered,
            "total_actions_visited": total_actions_visited,
            "coverage_percent": coverage_pct,
            "total_transitions": len(self.transitions),
            "current_state_id": self.current_state_id,
            "circuit_breaker": self.circuit_breaker.get_status(),
        }
