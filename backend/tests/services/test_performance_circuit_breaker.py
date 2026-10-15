"""Unit tests for P3.3 Multi-node HA and Prometheus alert rule integration with circuit breaker protection.

Tests:
1. build_prometheus_alert_rules: Validates YAML/dict structure of generated Prometheus alerts
2. evaluate_circuit_breaker: Evaluates CPU/Memory/Error saturation against thresholds
3. trip_circuit_breaker_if_saturated: Triggers run cancellation on saturation breach
4. select_ha_performance_nodes: Partitions candidate nodes into active primaries and standby redundancy
"""

from __future__ import annotations

from unittest.mock import patch

from app.services.performance_circuit_breaker import (
    DEFAULT_CIRCUIT_BREAKER_RULES,
    build_prometheus_alert_rules,
    evaluate_circuit_breaker,
    select_ha_performance_nodes,
    trip_circuit_breaker_if_saturated,
)


def test_build_prometheus_alert_rules():
    result = build_prometheus_alert_rules(run_id=42)
    assert "groups" in result
    group = result["groups"][0]
    assert group["name"] == "atp-performance-run-42-circuit-breaker"
    rules = group["rules"]
    assert len(rules) == len(DEFAULT_CIRCUIT_BREAKER_RULES)

    # Validate generator CPU saturation rule
    cpu_rule = next(r for r in rules if "GeneratorCpuPercent" in r["alert"])
    assert 'atp_run_id="42"' in cpu_rule["expr"]
    assert cpu_rule["labels"]["severity"] == "critical"
    assert cpu_rule["labels"]["action"] == "circuit_breaker_trip"
    assert cpu_rule["labels"]["atp_run_id"] == "42"


def test_evaluate_circuit_breaker_normal_within_safe_limits():
    normal_metrics = {
        "generator_cpu_percent": 45.2,
        "generator_memory_percent": 60.1,
        "target_cpu_percent": 55.0,
        "target_error_rate": 0.005,
    }

    eval_result = evaluate_circuit_breaker(normal_metrics)
    assert eval_result["tripped"] is False
    assert eval_result["action"] == "none"
    assert eval_result["breached_rules"] == []
    assert eval_result["reason"] is None


def test_evaluate_circuit_breaker_generator_cpu_saturation():
    saturated_metrics = {
        "generator_cpu_percent": 94.5,  # Exceeds 90% threshold
        "generator_memory_percent": 65.0,
    }

    eval_result = evaluate_circuit_breaker(saturated_metrics)
    assert eval_result["tripped"] is True
    assert eval_result["action"] == "abort"
    assert len(eval_result["breached_rules"]) == 1
    assert eval_result["breached_rules"][0]["metric"] == "generator_cpu_percent"
    assert "压力机 CPU 饱和度" in str(eval_result["reason"])


def test_evaluate_circuit_breaker_target_system_overload():
    overloaded_target = {
        "generator_cpu_percent": 30.0,
        "target_error_rate": 0.35,  # Exceeds 25% threshold
    }

    eval_result = evaluate_circuit_breaker(overloaded_target)
    assert eval_result["tripped"] is True
    assert eval_result["action"] == "abort"
    assert eval_result["breached_rules"][0]["metric"] == "target_error_rate"
    assert "目标系统错误率" in str(eval_result["reason"])


def test_trip_circuit_breaker_if_saturated_dispatches_cancellation():
    saturated_metrics = {"generator_cpu_percent": 96.0}

    with patch("app.services.performance_circuit_breaker.request_cancel") as mock_cancel:
        res = trip_circuit_breaker_if_saturated(run_id=99, sampled_metrics=saturated_metrics)
        assert res["tripped"] is True
        mock_cancel.assert_called_once_with(99)

    safe_metrics = {"generator_cpu_percent": 50.0}
    with patch("app.services.performance_circuit_breaker.request_cancel") as mock_cancel:
        res = trip_circuit_breaker_if_saturated(run_id=99, sampled_metrics=safe_metrics)
        assert res["tripped"] is False
        mock_cancel.assert_not_called()


def test_select_ha_performance_nodes():
    nodes = [
        {"id": 1, "name": "node-1", "status": "online", "active_runs": 2, "is_cordoned": False},
        {"id": 2, "name": "node-2", "status": "online", "active_runs": 0, "is_cordoned": False},
        {"id": 3, "name": "node-3", "status": "offline", "active_runs": 0, "is_cordoned": False},
        {"id": 4, "name": "node-4", "status": "online", "active_runs": 1, "is_cordoned": False},
        {"id": 5, "name": "node-5", "status": "online", "active_runs": 0, "is_cordoned": True},  # Cordoned
    ]

    # Need 2 shards: should pick least loaded node-2 (0 runs) and node-4 (1 run)
    result = select_ha_performance_nodes(nodes, required_shards=2)
    assert result["status"] == "ready"
    assert result["primary_count"] == 2
    assert result["standby_count"] == 1

    primaries = [n["id"] for n in result["primaries"]]
    assert primaries == [2, 4]  # 0 runs, then 1 run

    standbys = [n["id"] for n in result["standbys"]]
    assert standbys == [1]  # 2 runs

    # If requested shards exceed available healthy nodes
    insufficient = select_ha_performance_nodes(nodes, required_shards=5)
    assert insufficient["status"] == "insufficient_nodes"
    assert insufficient["available_count"] == 3
