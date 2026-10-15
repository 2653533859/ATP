"""Microservice Mesh and API Gateway Chaos Fault Orchestration Engine (T3.1).

Provides:
1. Multi-protocol microservice route matching (service_name, path regex, headers, methods).
2. Traffic sampling and user percentage throttling (e.g. inject into 20% of requests).
3. 4 Enterprise chaos actions: service_down_503, circuit_breaker_trip, latency_jitter, corrupt_payload.
4. Experiment lifecycle control (schedule, activate, pause, complete) and real-time execution statistics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import random
import re
from typing import Any
import uuid

logger = logging.getLogger(__name__)

SUPPORTED_CHAOS_ACTIONS = {
    "service_down_503",  # HTTP 503/502/504 Service Unavailable
    "circuit_breaker_trip",  # TCP Connection Reset / Immediate Break
    "latency_jitter",  # Dynamic latency delay with jitter
    "corrupt_payload",  # Malformed payload injection
}


@dataclass
class ChaosRule:
    rule_id: str
    service_name: str
    route_pattern: str
    action: str  # from SUPPORTED_CHAOS_ACTIONS
    traffic_ratio: float = 1.0  # 0.0 ~ 1.0
    methods: list[str] = field(default_factory=lambda: ["*"])
    header_matchers: dict[str, str] = field(default_factory=dict)
    action_params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def matches(
        self,
        *,
        service_name: str,
        path: str,
        method: str,
        headers: dict[str, str],
    ) -> bool:
        if not self.enabled:
            return False
        # 1. Service name
        if self.service_name != "*" and self.service_name.lower() != service_name.lower():
            return False
        # 2. Method
        if "*" not in self.methods and method.upper() not in [m.upper() for m in self.methods]:
            return False
        # 3. Path Regex
        try:
            if not re.search(self.route_pattern, path, re.IGNORECASE):
                return False
        except re.error:
            if self.route_pattern not in path:
                return False
        # 4. Header matchers
        lower_headers = {k.lower(): str(v) for k, v in headers.items()}
        for hk, hv in self.header_matchers.items():
            if lower_headers.get(hk.lower()) != str(hv):
                return False
        return True


@dataclass
class ChaosDecision:
    inject: bool
    action: str  # "pass" if not injected
    latency_ms: float = 0.0
    status_code: int = 200
    response_body: Any = None
    rule_id: str | None = None
    experiment_id: str | None = None
    reason: str = "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "inject": self.inject,
            "action": self.action,
            "latency_ms": round(self.latency_ms, 2),
            "status_code": self.status_code,
            "response_body": self.response_body,
            "rule_id": self.rule_id,
            "experiment_id": self.experiment_id,
            "reason": self.reason,
        }


@dataclass
class ChaosExperiment:
    experiment_id: str
    name: str
    description: str
    rules: list[ChaosRule]
    status: str = "active"  # "active" | "paused" | "completed"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_evaluated: int = 0
    total_injected: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "total_evaluated": self.total_evaluated,
            "total_injected": self.total_injected,
            "injected_ratio_pct": (
                round((self.total_injected / self.total_evaluated * 100.0), 2) if self.total_evaluated else 0.0
            ),
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "service_name": r.service_name,
                    "route_pattern": r.route_pattern,
                    "action": r.action,
                    "traffic_ratio": r.traffic_ratio,
                    "methods": r.methods,
                    "header_matchers": r.header_matchers,
                    "action_params": r.action_params,
                    "enabled": r.enabled,
                }
                for r in self.rules
            ],
        }


# Active experiments registry
_EXPERIMENTS: dict[str, ChaosExperiment] = {}


def create_chaos_experiment(
    name: str,
    rules_data: list[dict[str, Any]],
    *,
    description: str = "",
    experiment_id: str | None = None,
) -> ChaosExperiment:
    """Create and validate a new mesh chaos experiment."""
    if not name or not name.strip():
        raise ValueError("实验名称不能为空")
    if not rules_data:
        raise ValueError("混沌实验必须至少包含一条故障规则")

    eid = experiment_id or f"exp_chaos_{uuid.uuid4().hex[:10]}"
    parsed_rules: list[ChaosRule] = []

    for idx, r in enumerate(rules_data, start=1):
        action = str(r.get("action", "")).lower()
        if action not in SUPPORTED_CHAOS_ACTIONS:
            raise ValueError(
                f"第 {idx} 条规则故障动作 '{action}' 不受支持，支持动作: {sorted(SUPPORTED_CHAOS_ACTIONS)}"
            )

        ratio = float(r.get("traffic_ratio", 1.0))
        if not 0.0 <= ratio <= 1.0:
            raise ValueError(f"第 {idx} 条规则流量采样比例必须在 0.0 到 1.0 之间")

        rid = r.get("rule_id") or f"rule_{eid}_{idx}"
        rule = ChaosRule(
            rule_id=rid,
            service_name=r.get("service_name", "*"),
            route_pattern=r.get("route_pattern", ".*"),
            action=action,
            traffic_ratio=ratio,
            methods=r.get("methods", ["*"]),
            header_matchers=r.get("header_matchers", {}),
            action_params=r.get("action_params", {}),
            enabled=bool(r.get("enabled", True)),
        )
        parsed_rules.append(rule)

    exp = ChaosExperiment(
        experiment_id=eid,
        name=name,
        description=description,
        rules=parsed_rules,
        status="active",
    )
    _EXPERIMENTS[eid] = exp
    return exp


def get_chaos_experiment(experiment_id: str) -> ChaosExperiment | None:
    return _EXPERIMENTS.get(experiment_id)


def list_chaos_experiments() -> list[dict[str, Any]]:
    return [e.to_dict() for e in _EXPERIMENTS.values()]


def set_experiment_status(experiment_id: str, status: str) -> bool:
    if status not in {"active", "paused", "completed"}:
        raise ValueError(f"不支持的实验状态: '{status}'")
    exp = _EXPERIMENTS.get(experiment_id)
    if not exp:
        return False
    exp.status = status
    return True


def evaluate_mesh_request(
    *,
    service_name: str,
    path: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    seed: float | None = None,
) -> ChaosDecision:
    """Evaluate an incoming microservice request against all active mesh chaos experiments."""
    req_headers = headers or {}
    sample_roll = seed if seed is not None else random.random()

    # Iterate over active experiments
    for exp in _EXPERIMENTS.values():
        if exp.status != "active":
            continue

        exp.total_evaluated += 1

        for rule in exp.rules:
            if rule.matches(service_name=service_name, path=path, method=method, headers=req_headers):
                # Check sampling ratio
                if sample_roll <= rule.traffic_ratio:
                    exp.total_injected += 1
                    return _build_chaos_decision(rule, exp.experiment_id)

    return ChaosDecision(inject=False, action="pass", reason="no_matching_active_rule")


def _build_chaos_decision(rule: ChaosRule, experiment_id: str) -> ChaosDecision:
    """Construct concrete failure payload based on matched rule action."""
    action = rule.action
    params = rule.action_params

    if action == "service_down_503":
        status_code = int(params.get("status_code", 503))
        body = params.get("error_body") or {
            "error": "ServiceUnavailable",
            "message": f"微服务 '{rule.service_name}' 正在执行混沌演练故障模拟",
            "experiment_id": experiment_id,
        }
        return ChaosDecision(
            inject=True,
            action=action,
            status_code=status_code,
            response_body=body,
            rule_id=rule.rule_id,
            experiment_id=experiment_id,
            reason=f"触发 503 宕机故障注入 (Rule: {rule.rule_id})",
        )

    elif action == "circuit_breaker_trip":
        return ChaosDecision(
            inject=True,
            action=action,
            status_code=504,
            response_body={"error": "CircuitBreakerTrip", "message": "ECONNRESET: 连接被网关熔断保护重置"},
            rule_id=rule.rule_id,
            experiment_id=experiment_id,
            reason=f"触发连接熔断重置 (Rule: {rule.rule_id})",
        )

    elif action == "latency_jitter":
        base_delay = float(params.get("base_latency_ms", 1500.0))
        jitter = float(params.get("jitter_ms", 300.0))
        actual_delay = base_delay + (random.random() * jitter)
        return ChaosDecision(
            inject=True,
            action=action,
            latency_ms=actual_delay,
            status_code=200,
            rule_id=rule.rule_id,
            experiment_id=experiment_id,
            reason=f"触发延迟抖动注入 (+{actual_delay:.1f}ms)",
        )

    elif action == "corrupt_payload":
        return ChaosDecision(
            inject=True,
            action=action,
            status_code=200,
            response_body="<malformed_json_corrupted_stream>",
            rule_id=rule.rule_id,
            experiment_id=experiment_id,
            reason="触发损坏畸形报文注入",
        )

    return ChaosDecision(inject=False, action="pass")
