"""Microservice Mesh Chaos Blast Radius Controller and Cascade Impact Guard (T3.2).

Provides:
1. Microservice dependency graph topology modeling (nodes, edges, call chains).
2. Blast radius calculation: tracking direct, cascading, and upstream impacted microservices.
3. Safety boundary constraints (max impacted services, max depth, protected services).
4. Automated emergency abort triggering when blast radius constraints are breached.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any

from app.services.mesh_chaos_orchestrator import (
    get_chaos_experiment,
    set_experiment_status,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_IMPACTED_SERVICES = 3
DEFAULT_MAX_DEPTH = 2
DEFAULT_MAX_ERROR_RATE = 0.15


@dataclass
class BlastRadiusConstraint:
    max_impacted_services: int = DEFAULT_MAX_IMPACTED_SERVICES
    max_depth: int = DEFAULT_MAX_DEPTH
    max_error_rate: float = DEFAULT_MAX_ERROR_RATE
    protected_services: list[str] = field(default_factory=lambda: ["user-auth", "billing-core", "database-primary"])

    def validate(self) -> None:
        if self.max_impacted_services < 1:
            raise ValueError("最大允许影响服务数必须大于等于 1")
        if self.max_depth < 0:
            raise ValueError("最大影响深度不能为负数")
        if not 0.0 <= self.max_error_rate <= 1.0:
            raise ValueError("错误率阈值必须在 0.0 到 1.0 之间")


@dataclass
class BlastRadiusImpactReport:
    injected_service: str
    total_impacted_count: int
    max_depth_reached: int
    direct_services: list[str]
    cascading_services: list[dict[str, Any]]
    breached: bool
    breach_reasons: list[str]
    emergency_aborted: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "injected_service": self.injected_service,
            "total_impacted_count": self.total_impacted_count,
            "max_depth_reached": self.max_depth_reached,
            "direct_services": self.direct_services,
            "cascading_services": self.cascading_services,
            "breached": self.breached,
            "breach_reasons": self.breach_reasons,
            "emergency_aborted": self.emergency_aborted,
            "timestamp": self.timestamp,
        }


class ServiceTopologyGraph:
    """Directed graph representing microservice call dependencies."""

    def __init__(self) -> None:
        # caller -> list of callees (downstream dependencies)
        self.downstream_adj: dict[str, set[str]] = {}
        # callee -> list of callers (upstream dependents)
        self.upstream_adj: dict[str, set[str]] = {}
        self.services: set[str] = set()

    def add_service(self, service_name: str) -> None:
        s_norm = service_name.strip().lower()
        self.services.add(s_norm)
        self.downstream_adj.setdefault(s_norm, set())
        self.upstream_adj.setdefault(s_norm, set())

    def add_dependency(self, caller: str, callee: str) -> None:
        """Add directed dependency: caller -> callee (caller calls callee)."""
        c_norm = caller.strip().lower()
        t_norm = callee.strip().lower()
        self.add_service(c_norm)
        self.add_service(t_norm)
        self.downstream_adj[c_norm].add(t_norm)
        self.upstream_adj[t_norm].add(c_norm)

    def calculate_impact(
        self,
        injected_service: str,
        constraints: BlastRadiusConstraint,
    ) -> BlastRadiusImpactReport:
        """Calculate blast radius impact when injected_service experiences failure."""
        s_injected = injected_service.strip().lower()
        self.add_service(s_injected)

        # BFS traverse upstream (callers affected because callee is broken)
        # When callee breaks, services that call it experience errors/timeouts!
        visited: dict[str, int] = {s_injected: 0}
        queue = deque([(s_injected, 0)])

        max_depth = 0
        cascading_list: list[dict[str, Any]] = []

        while queue:
            curr_svc, depth = queue.popleft()
            max_depth = max(max_depth, depth)

            if depth > 0:
                cascading_list.append(
                    {
                        "service_name": curr_svc,
                        "depth": depth,
                        "impact_type": "upstream_caller_degraded",
                    }
                )

            # Callers of curr_svc are impacted
            for caller in self.upstream_adj.get(curr_svc, set()):
                if caller not in visited:
                    visited[caller] = depth + 1
                    queue.append((caller, depth + 1))

        total_impacted = len(visited)
        direct_services = [s_injected]

        # Check safety boundaries
        breached = False
        breach_reasons: list[str] = []

        if total_impacted > constraints.max_impacted_services:
            breached = True
            breach_reasons.append(
                f"影响微服务总数 ({total_impacted}) 超过允许爆炸半径最大阈值 ({constraints.max_impacted_services})"
            )

        if max_depth > constraints.max_depth:
            breached = True
            breach_reasons.append(f"故障级联传导深度 ({max_depth}) 超过允许最大深度 ({constraints.max_depth})")

        # Check protected services
        lower_protected = {p.lower() for p in constraints.protected_services}
        impacted_protected = [s for s in visited if s in lower_protected]
        if impacted_protected:
            breached = True
            breach_reasons.append(f"故障波及核心受保护微服务名单: {impacted_protected}，触碰安全红线")

        return BlastRadiusImpactReport(
            injected_service=s_injected,
            total_impacted_count=total_impacted,
            max_depth_reached=max_depth,
            direct_services=direct_services,
            cascading_services=cascading_list,
            breached=breached,
            breach_reasons=breach_reasons,
            emergency_aborted=False,
        )


# Global default service mesh topology
_DEFAULT_TOPOLOGY = ServiceTopologyGraph()

# Seed with standard microservice architecture call chains
_DEFAULT_DEPENDENCIES = [
    ("api-gateway", "order-service"),
    ("api-gateway", "user-service"),
    ("api-gateway", "cart-service"),
    ("order-service", "payment-service"),
    ("order-service", "inventory-service"),
    ("payment-service", "bank-gateway"),
    ("cart-service", "inventory-service"),
    ("user-service", "user-auth"),
    ("payment-service", "billing-core"),
]

for _caller, _callee in _DEFAULT_DEPENDENCIES:
    _DEFAULT_TOPOLOGY.add_dependency(_caller, _callee)


def get_default_topology() -> ServiceTopologyGraph:
    return _DEFAULT_TOPOLOGY


def evaluate_blast_radius(
    injected_service: str,
    *,
    constraints: BlastRadiusConstraint | None = None,
    topology: ServiceTopologyGraph | None = None,
) -> BlastRadiusImpactReport:
    """Evaluate prospective or live blast radius impact for a target microservice."""
    topo = topology or _DEFAULT_TOPOLOGY
    cons = constraints or BlastRadiusConstraint()
    cons.validate()
    return topo.calculate_impact(injected_service, cons)


def enforce_blast_radius_safety(
    experiment_id: str,
    injected_service: str,
    *,
    constraints: BlastRadiusConstraint | None = None,
    topology: ServiceTopologyGraph | None = None,
) -> BlastRadiusImpactReport:
    """Evaluate blast radius and automatically trigger emergency abort on the experiment if breached."""
    report = evaluate_blast_radius(injected_service, constraints=constraints, topology=topology)

    if report.breached:
        exp = get_chaos_experiment(experiment_id)
        if exp and exp.status == "active":
            set_experiment_status(experiment_id, "paused")
            report.emergency_aborted = True
            logger.warning(
                "EMERGENCY ABORT: Blast radius breached for experiment %s! Injected service: %s. Reasons: %s",
                experiment_id,
                injected_service,
                report.breach_reasons,
            )

    return report
