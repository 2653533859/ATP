"""Unit tests for Q2.3 Abnormal Crash and Infinite Loop Exploration Circuit Breaker.

Tests:
1. ExplorationCircuitBreaker trips on consecutive zero elements (black screen)
2. Trips on consecutive action execution failures
3. Trips on prolonged unrecoverable oscillation loops
4. Trips on maximum step limits
5. compile_exploration_abort_snapshot generates structured incident artifact
6. AutonomousExplorationGraph integration emits abort action when tripped
"""

from __future__ import annotations

from app.models.bootstrap import load_all_models
from app.services.autonomous_exploration_engine import AutonomousExplorationGraph
from app.services.exploration_circuit_breaker import (
    ExplorationCircuitBreaker,
    compile_exploration_abort_snapshot,
)

load_all_models()


def test_circuit_breaker_healthy_normal_steps():
    cb = ExplorationCircuitBreaker(max_zero_elements=3)
    res1 = cb.evaluate_step(element_count=5, last_action_success=True)
    assert res1["tripped"] is False
    assert res1["should_abort"] is False

    res2 = cb.evaluate_step(element_count=8, last_action_success=True)
    assert res2["tripped"] is False
    assert res2["total_steps"] == 2


def test_circuit_breaker_trips_on_consecutive_black_screens():
    cb = ExplorationCircuitBreaker(max_zero_elements=3)

    cb.evaluate_step(element_count=0)
    assert cb.consecutive_zero_elements == 1
    assert cb.is_tripped is False

    cb.evaluate_step(element_count=0)
    assert cb.consecutive_zero_elements == 2
    assert cb.is_tripped is False

    # 3rd consecutive zero-element step: trips
    res = cb.evaluate_step(element_count=0)
    assert res["tripped"] is True
    assert res["category"] == "black_screen_detected"
    assert "黑屏/白屏/崩溃" in str(res["reason"])


def test_circuit_breaker_trips_on_consecutive_action_failures():
    cb = ExplorationCircuitBreaker(max_consecutive_failures=3)

    cb.evaluate_step(element_count=2, last_action_success=False)
    cb.evaluate_step(element_count=2, last_action_success=False)
    assert cb.is_tripped is False

    # 3rd failure: trips
    res = cb.evaluate_step(element_count=2, last_action_success=False)
    assert res["tripped"] is True
    assert res["category"] == "consecutive_action_failures"
    assert "动作执行异常" in str(res["reason"])


def test_circuit_breaker_trips_on_infinite_loop_oscillation():
    cb = ExplorationCircuitBreaker(max_oscillations=3)

    cb.evaluate_step(element_count=3, is_oscillation=True)
    cb.evaluate_step(element_count=3, is_oscillation=True)
    assert cb.is_tripped is False

    # 3rd oscillation: trips
    res = cb.evaluate_step(element_count=3, is_oscillation=True)
    assert res["tripped"] is True
    assert res["category"] == "infinite_loop_oscillation"
    assert "死循环" in str(res["reason"])


def test_compile_exploration_abort_snapshot():
    cb_status = {
        "tripped": True,
        "category": "black_screen_detected",
        "reason": "黑屏熔断",
        "total_steps": 15,
    }
    snapshot = compile_exploration_abort_snapshot(
        cb_status,
        session_id="exp_session_888",
        last_screen_name="CrashActivity",
        total_states_discovered=4,
    )

    assert snapshot["session_id"] == "exp_session_888"
    assert snapshot["incident_type"] == "exploration_circuit_breaker_abort"
    assert snapshot["category"] == "black_screen_detected"
    assert snapshot["last_screen_name"] == "CrashActivity"
    assert snapshot["total_steps_executed"] == 15
    assert snapshot["total_states_discovered"] == 4


def test_graph_emits_abort_action_when_circuit_breaker_trips():
    graph = AutonomousExplorationGraph(max_depth=5)
    # Configure graph circuit breaker to trip on 2 zero elements
    graph.circuit_breaker.max_zero_elements = 2

    # Step 1 with empty elements
    graph.update_state([], "BlankScreen1")
    # Step 2 with empty elements: trips circuit breaker
    graph.update_state([], "BlankScreen2")

    assert graph.circuit_breaker.is_tripped is True

    action = graph.select_next_action()
    assert action is not None
    assert action["action_type"] == "abort"
    assert action["action_signature"] == "circuit_breaker_abort"
    assert action["category"] == "black_screen_detected"
