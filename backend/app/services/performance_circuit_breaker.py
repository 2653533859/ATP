"""Multi-node HA and Prometheus alert rule integration with circuit breaker protection (P3.3).

Provides:
1. Prometheus alerting rule generation for both generator nodes and target service.
2. Real-time CPU, memory, and network saturation evaluation.
3. Automated circuit breaker tripping and cancellation dispatch to safeguard nodes and target systems.
4. HA multi-node candidate selection with standby failover redundancy.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from app.services.performance_control import request_cancel

logger = logging.getLogger(__name__)

# Default saturation thresholds for safety circuit breaker
DEFAULT_CIRCUIT_BREAKER_RULES: list[dict[str, Any]] = [
    {
        "metric": "generator_cpu_percent",
        "threshold": 90.0,
        "operator": ">=",
        "target_type": "generator",
        "description": "压力机 CPU 饱和度超过 90%，触发自我保护熔断",
    },
    {
        "metric": "generator_memory_percent",
        "threshold": 88.0,
        "operator": ">=",
        "target_type": "generator",
        "description": "压力机内存使用率超过 88%，防 OOM 熔断",
    },
    {
        "metric": "target_cpu_percent",
        "threshold": 95.0,
        "operator": ">=",
        "target_type": "target",
        "description": "目标系统 CPU 饱和度超过 95%，触发业务保护熔断",
    },
    {
        "metric": "target_error_rate",
        "threshold": 0.25,
        "operator": ">=",
        "target_type": "target",
        "description": "目标系统错误率超过 25%，触发业务熔断",
    },
]


def build_prometheus_alert_rules(
    run_id: int,
    custom_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate Prometheus alert rule group YAML-compatible dict for a performance run.

    Configures alerting rules targeting both the runner pods and the target service.
    """
    rules = custom_rules or DEFAULT_CIRCUIT_BREAKER_RULES
    prom_rules: list[dict[str, Any]] = []

    for idx, rule in enumerate(rules):
        metric = str(rule.get("metric") or f"metric_{idx}")
        threshold = rule.get("threshold", 90.0)
        target_type = rule.get("target_type", "generator")
        description = rule.get("description", f"Alert on {metric} >= {threshold}")

        if target_type == "generator":
            if "cpu" in metric:
                expr = f'avg(rate(container_cpu_usage_seconds_total{{atp_run_id="{run_id}"}}[1m])) * 100 >= {threshold}'
            elif "memory" in metric:
                expr = (
                    f'avg(container_memory_working_set_bytes{{atp_run_id="{run_id}"}} / '
                    f'container_spec_memory_limit_bytes{{atp_run_id="{run_id}"}}) * 100 >= {threshold}'
                )
            else:
                expr = f'{metric}{{atp_run_id="{run_id}"}} >= {threshold}'
        else:
            expr = f"{metric} >= {threshold}"

        alert_name = f"ATPPerfRun{run_id}_{metric.replace('_', ' ').title().replace(' ', '')}"
        prom_rules.append(
            {
                "alert": alert_name,
                "expr": expr,
                "for": "10s",
                "labels": {
                    "severity": "critical",
                    "action": "circuit_breaker_trip",
                    "atp_run_id": str(run_id),
                    "target_type": target_type,
                },
                "annotations": {
                    "summary": description,
                    "threshold": str(threshold),
                },
            }
        )

    return {
        "groups": [
            {
                "name": f"atp-performance-run-{run_id}-circuit-breaker",
                "rules": prom_rules,
            }
        ]
    }


def evaluate_circuit_breaker(
    sampled_metrics: dict[str, Any],
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate whether sampled saturation metrics breach circuit breaker thresholds.

    Returns dict with tripped flag, breached rule details, and recommended action.
    """
    active_rules = rules or DEFAULT_CIRCUIT_BREAKER_RULES
    breached: list[dict[str, Any]] = []

    for rule in active_rules:
        metric_name = str(rule.get("metric", ""))
        threshold = float(rule.get("threshold", 0.0))
        op = str(rule.get("operator", ">="))

        if metric_name not in sampled_metrics:
            continue

        raw_val = sampled_metrics[metric_name]
        if not isinstance(raw_val, (int, float)) or isinstance(raw_val, bool):
            continue

        val = float(raw_val)
        is_breach = False
        if op in (">=", "ge") and val >= threshold:
            is_breach = True
        elif op in (">", "gt") and val > threshold:
            is_breach = True
        elif op in ("<=", "le") and val <= threshold:
            is_breach = True
        elif op in ("<", "lt") and val < threshold:
            is_breach = True

        if is_breach:
            breached.append(
                {
                    "metric": metric_name,
                    "current_value": val,
                    "threshold": threshold,
                    "operator": op,
                    "target_type": rule.get("target_type", "unknown"),
                    "description": rule.get("description", ""),
                }
            )

    tripped = len(breached) > 0
    reason = None
    if tripped:
        first = breached[0]
        reason = f"触发熔断保护: {first['description']} (当前值: {first['current_value']}, 阈值: {first['threshold']})"

    return {
        "tripped": tripped,
        "reason": reason,
        "breached_rules": breached,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "action": "abort" if tripped else "none",
    }


def trip_circuit_breaker_if_saturated(
    run_id: int,
    sampled_metrics: dict[str, Any],
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate saturation metrics and immediately signal run cancellation if tripped."""
    evaluation = evaluate_circuit_breaker(sampled_metrics, rules)
    if evaluation.get("tripped"):
        logger.warning(
            "Circuit breaker TRIPPED for performance run %s: %s",
            run_id,
            evaluation.get("reason"),
        )
        try:
            request_cancel(run_id)
        except Exception as exc:
            logger.error("Failed to dispatch cancel request for run %s: %s", run_id, exc)

    return evaluation


def select_ha_performance_nodes(
    candidate_nodes: list[dict[str, Any]],
    required_shards: int,
) -> dict[str, Any]:
    """Select high-availability performance worker nodes with standby failover redundancy.

    Filters active and healthy nodes, allocates primary shards, and tags backup standby nodes.
    """
    if required_shards <= 0:
        return {"primaries": [], "standbys": [], "status": "insufficient_nodes"}

    healthy_nodes = [
        n
        for n in candidate_nodes
        if n.get("status") in ("online", "active", "idle") and not n.get("is_cordoned", False)
    ]

    # Sort nodes by current active workload (ascending)
    healthy_nodes.sort(key=lambda x: int(x.get("active_runs", 0)))

    if len(healthy_nodes) < required_shards:
        return {
            "primaries": healthy_nodes,
            "standbys": [],
            "status": "insufficient_nodes",
            "available_count": len(healthy_nodes),
            "required_count": required_shards,
        }

    primaries = healthy_nodes[:required_shards]
    standbys = healthy_nodes[required_shards:]

    return {
        "primaries": primaries,
        "standbys": standbys,
        "status": "ready",
        "primary_count": len(primaries),
        "standby_count": len(standbys),
    }
