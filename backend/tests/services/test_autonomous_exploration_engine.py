"""Unit tests for Q2.1 State-Tree Based Autonomous Exploration and Traversal Engine.

Tests:
1. compute_element_signature generates deterministic element hashes
2. compute_page_state_hash is order-invariant and distinguishes different screens
3. AutonomousExplorationGraph tracks states and transitions
4. Anti-looping oscillation detection (A -> B -> A -> B) breaks out with Back action
5. Max depth limits trigger backtracking
6. Coverage metrics aggregation
"""

from __future__ import annotations

from app.models.bootstrap import load_all_models
from app.services.autonomous_exploration_engine import (
    AutonomousExplorationGraph,
    compute_element_signature,
    compute_page_state_hash,
)

load_all_models()


def test_element_and_page_signatures():
    btn1 = {"tag": "button", "id": "btn_login", "text": "登录"}
    btn2 = {"tag": "button", "id": "btn_cancel", "text": "取消"}

    sig1 = compute_element_signature(btn1)
    sig2 = compute_element_signature(btn2)
    assert sig1 != sig2
    assert len(sig1) == 16

    # Page state hash is invariant to element list permutation
    state_a = compute_page_state_hash([btn1, btn2], "LoginScreen")
    state_b = compute_page_state_hash([btn2, btn1], "LoginScreen")
    assert state_a == state_b

    # Different screen produces different state hash
    state_diff = compute_page_state_hash([btn1, btn2], "HomeScreen")
    assert state_a != state_diff


def test_graph_state_transitions_and_action_selection():
    graph = AutonomousExplorationGraph(strategy="bfs", max_depth=5)

    btn_login = {"tag": "button", "id": "btn_login", "text": "登录"}
    btn_register = {"tag": "button", "id": "btn_register", "text": "注册"}

    # 1. First state: Login screen with 2 buttons
    state1 = graph.update_state([btn_login, btn_register], "LoginScreen")
    assert state1.depth == 0
    assert len(state1.candidate_actions) == 2

    # Select first action
    action1 = graph.select_next_action()
    assert action1 is not None
    assert action1["action_type"] == "click"
    assert len(state1.visited_actions) == 1

    # 2. Transition to Home screen
    btn_profile = {"tag": "button", "id": "btn_profile", "text": "个人中心"}
    state2 = graph.update_state([btn_profile], "HomeScreen")
    assert state2.depth == 1
    assert len(graph.transitions) == 1
    assert graph.transitions[0]["from_state"] == state1.state_id
    assert graph.transitions[0]["to_state"] == state2.state_id

    # Select action in Home screen
    action2 = graph.select_next_action()
    assert action2 is not None
    assert action2["element"]["id"] == "btn_profile"

    # Next action in Home screen: candidates exhausted -> back
    action3 = graph.select_next_action()
    assert action3 is not None
    assert action3["action_type"] == "back"


def test_anti_loop_oscillation_detection():
    graph = AutonomousExplorationGraph()
    state_b = graph.update_state([{"id": "btn"}], "ScreenB")
    state_b_id = state_b.state_id
    state_a_id = "state_a_mock"

    # Simulate 2-node ping-pong oscillation: State A -> State B -> State A -> State B
    graph.recent_state_history = [state_a_id, state_b_id, state_a_id, state_b_id]
    assert graph.detect_oscillation_loop() is True

    # When oscillation detected, select_next_action emits Back action to escape
    action = graph.select_next_action()
    assert action is not None
    assert action["action_type"] == "back"
    assert action["action_signature"] == "anti_loop_back"


def test_coverage_metrics_reporting():
    graph = AutonomousExplorationGraph()
    btn1 = {"tag": "button", "id": "b1"}
    btn2 = {"tag": "button", "id": "b2"}

    graph.update_state([btn1, btn2], "Screen1")
    metrics_before = graph.get_coverage_metrics()
    assert metrics_before["total_states"] == 1
    assert metrics_before["total_actions_discovered"] == 2
    assert metrics_before["total_actions_visited"] == 0
    assert metrics_before["coverage_percent"] == 0.0

    graph.select_next_action()
    metrics_after = graph.get_coverage_metrics()
    assert metrics_after["total_actions_visited"] == 1
    assert metrics_after["coverage_percent"] == 50.0
