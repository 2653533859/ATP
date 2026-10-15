"""Unit tests for T3.3 Whole-Mesh Service-Level High Availability SLA Resilience Report.

Tests:
1. calculate_service_sla computes availability percentage, drop magnitude, and degradation status
2. compute_mesh_resilience_score weighs SLA, RTO recovery speed, blast containment, and errors
3. compile_mesh_resilience_report aggregates multi-microservice SLAs and identifies weakest link
4. compile_mesh_resilience_report penalizes breached or emergency-aborted experiments
"""

from __future__ import annotations

from app.services.service_mesh_resilience_report import (
    calculate_service_sla,
    compile_mesh_resilience_report,
    compute_mesh_resilience_score,
)


def test_calculate_service_sla():
    # 1. Healthy service (0 failures out of 1000)
    sla_healthy = calculate_service_sla(
        "auth-service",
        total_requests=1000,
        failed_requests=0,
        sla_baseline=99.9,
    )
    assert sla_healthy.availability_sla_pct == 100.0
    assert sla_healthy.sla_drop_pct == 0.0
    assert sla_healthy.degradation_status == "healthy"

    # 2. Minor degraded service (15 failures out of 1000 -> 98.5% SLA, drop = 1.4%)
    sla_minor = calculate_service_sla(
        "order-service",
        total_requests=1000,
        failed_requests=15,
        sla_baseline=99.9,
    )
    assert sla_minor.availability_sla_pct == 98.5
    assert abs(sla_minor.sla_drop_pct - 1.4) < 1e-4
    assert sla_minor.degradation_status == "minor_degraded"

    # 3. Outage service (150 failures out of 1000 -> 85.0% SLA)
    sla_outage = calculate_service_sla(
        "payment-gateway",
        total_requests=1000,
        failed_requests=150,
        sla_baseline=99.9,
    )
    assert sla_outage.availability_sla_pct == 85.0
    assert sla_outage.degradation_status == "outage"


def test_compute_mesh_resilience_score_weights():
    # 1. High resilience mesh: high SLA, fast recovery (2s), blast radius safe
    s1 = calculate_service_sla("svc1", 1000, 1, recovery_time_seconds=2.0)
    s2 = calculate_service_sla("svc2", 1000, 2, recovery_time_seconds=2.5)

    score_high, grade_high, tip_high = compute_mesh_resilience_score(
        [s1, s2],
        blast_radius_breached=False,
        emergency_aborted=False,
    )
    assert score_high >= 90.0
    assert grade_high == "A"
    assert "高可用自愈韧性" in tip_high

    # 2. Breached mesh: blast radius breached and emergency aborted
    score_low, grade_low, _ = compute_mesh_resilience_score(
        [s1, s2],
        blast_radius_breached=True,
        emergency_aborted=True,
    )
    assert score_low < score_high
    assert score_low < 85.0
    assert grade_low in {"B", "C", "D", "F"}


def test_compile_mesh_resilience_report():
    services_sample = [
        {
            "service_name": "gateway",
            "total_requests": 2000,
            "failed_requests": 5,
            "recovery_time_seconds": 1.5,
            "avg_latency_ms": 30.0,
            "p95_latency_ms": 75.0,
        },
        {
            "service_name": "order-service",
            "total_requests": 1500,
            "failed_requests": 10,
            "recovery_time_seconds": 3.0,
            "avg_latency_ms": 45.0,
            "p95_latency_ms": 110.0,
        },
        {
            "service_name": "payment-gateway",
            "total_requests": 1200,
            "failed_requests": 80,  # Weakest link (80 failures)
            "recovery_time_seconds": 8.0,
            "avg_latency_ms": 120.0,
            "p95_latency_ms": 350.0,
        },
    ]

    report = compile_mesh_resilience_report(
        experiment_id="exp_mesh_q3_3",
        services_data=services_sample,
        sla_baseline_target=99.9,
        blast_radius_breached=False,
        emergency_aborted=False,
    )

    summary = report["summary"]
    assert report["experiment_id"] == "exp_mesh_q3_3"
    assert summary["total_services_evaluated"] == 3
    assert summary["lowest_sla_service"] == "payment-gateway"
    assert summary["lowest_sla_percent"] < 95.0
    assert summary["resilience_grade"] in {"B", "C"}
    assert len(report["services"]) == 3
    assert report["services"][2]["service_name"] == "payment-gateway"
