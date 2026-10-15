"""Unit tests for T3.2 Microservice Chaos Blast Radius Controller and Cascade Impact Guard.

Tests:
1. ServiceTopologyGraph constructs caller-callee directed dependency chains
2. BlastRadiusConstraint validates boundary parameters
3. evaluate_blast_radius verifies safe contained impact within thresholds
4. evaluate_blast_radius detects breach on max services, max depth, and protected services
5. enforce_blast_radius_safety automatically triggers emergency abort and pauses active experiment
"""

from __future__ import annotations

import pytest

from app.services.blast_radius_controller import (
    BlastRadiusConstraint,
    ServiceTopologyGraph,
    enforce_blast_radius_safety,
    evaluate_blast_radius,
)
from app.services.mesh_chaos_orchestrator import (
    create_chaos_experiment,
    get_chaos_experiment,
)


def test_service_topology_graph_construction():
    topo = ServiceTopologyGraph()
    topo.add_dependency("gateway", "order-service")
    topo.add_dependency("order-service", "pay-service")

    assert "gateway" in topo.services
    assert "pay-service" in topo.services
    assert "pay-service" in topo.downstream_adj["order-service"]
    assert "order-service" in topo.upstream_adj["pay-service"]


def test_blast_radius_constraint_validation():
    with pytest.raises(ValueError, match="最大允许影响服务数"):
        c = BlastRadiusConstraint(max_impacted_services=0)
        c.validate()

    with pytest.raises(ValueError, match="错误率阈值"):
        c = BlastRadiusConstraint(max_error_rate=1.5)
        c.validate()


def test_evaluate_blast_radius_contained_safe():
    topo = ServiceTopologyGraph()
    topo.add_dependency("order-service", "inventory-service")

    # Injected into inventory-service: only order-service and inventory-service are affected (depth 1, count 2)
    constraints = BlastRadiusConstraint(
        max_impacted_services=3,
        max_depth=2,
        protected_services=["user-auth"],
    )

    report = evaluate_blast_radius("inventory-service", constraints=constraints, topology=topo)
    assert report.breached is False
    assert report.total_impacted_count == 2
    assert report.max_depth_reached == 1
    assert "inventory-service" in report.direct_services
    assert any(c["service_name"] == "order-service" for c in report.cascading_services)
    assert len(report.breach_reasons) == 0


def test_evaluate_blast_radius_breach_detection():
    topo = ServiceTopologyGraph()
    # Call chain: gateway -> order-service -> payment-service -> bank-gateway -> billing-core
    topo.add_dependency("gateway", "order-service")
    topo.add_dependency("order-service", "payment-service")
    topo.add_dependency("payment-service", "bank-gateway")
    topo.add_dependency("payment-service", "billing-core")

    # 1. Breach: max depth exceeded
    c_depth = BlastRadiusConstraint(max_impacted_services=10, max_depth=1)
    rep_depth = evaluate_blast_radius("bank-gateway", constraints=c_depth, topology=topo)
    assert rep_depth.breached is True
    assert any("故障级联传导深度" in r for r in rep_depth.breach_reasons)

    # 2. Breach: protected service impacted
    c_prot = BlastRadiusConstraint(
        max_impacted_services=10,
        max_depth=10,
        protected_services=["payment-service"],
    )
    rep_prot = evaluate_blast_radius("bank-gateway", constraints=c_prot, topology=topo)
    assert rep_prot.breached is True
    assert any("核心受保护微服务" in r for r in rep_prot.breach_reasons)


def test_enforce_blast_radius_safety_emergency_abort():
    # Setup active experiment
    exp = create_chaos_experiment(
        name="核心支付故障注入演练",
        experiment_id="exp_abort_test_01",
        rules_data=[
            {
                "service_name": "billing-core",
                "route_pattern": r"/bill/.*",
                "action": "service_down_503",
            }
        ],
    )
    assert exp.status == "active"

    # Enforce with strict constraint (protected service includes billing-core)
    constraints = BlastRadiusConstraint(
        max_impacted_services=5,
        max_depth=5,
        protected_services=["billing-core"],
    )

    report = enforce_blast_radius_safety(
        "exp_abort_test_01",
        "billing-core",
        constraints=constraints,
    )

    assert report.breached is True
    assert report.emergency_aborted is True

    # Verify experiment was automatically paused
    updated_exp = get_chaos_experiment("exp_abort_test_01")
    assert updated_exp is not None
    assert updated_exp.status == "paused"
