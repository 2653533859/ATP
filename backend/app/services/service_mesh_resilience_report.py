"""Whole-Mesh Service-Level High Availability SLA Resilience Report Service (T3.3).

Provides:
1. Microservice availability SLA calculation (99.9% / 99.99%) and degradation magnitude tracking.
2. Cross-service recovery time objective (RTO) and latency percentile aggregation.
3. Comprehensive architectural resilience scoring (0 - 100) and Grade A-F classification.
4. Actionable cloud-native resilience recommendations and fault-tolerance hardening guidelines.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)

DEFAULT_SLA_TARGET_PERCENT = 99.9


@dataclass
class ServiceSlaItem:
    service_name: str
    total_requests: int
    failed_requests: int
    availability_sla_pct: float
    sla_baseline_target: float
    sla_drop_pct: float
    avg_latency_ms: float
    p95_latency_ms: float
    recovery_time_seconds: float
    degradation_status: str  # "healthy" | "minor_degraded" | "severely_degraded" | "outage"

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_name": self.service_name,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "availability_sla_pct": round(self.availability_sla_pct, 3),
            "sla_baseline_target": self.sla_baseline_target,
            "sla_drop_pct": round(self.sla_drop_pct, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "recovery_time_seconds": round(self.recovery_time_seconds, 2),
            "degradation_status": self.degradation_status,
        }


def calculate_service_sla(
    service_name: str,
    total_requests: int,
    failed_requests: int,
    *,
    sla_baseline: float = DEFAULT_SLA_TARGET_PERCENT,
    avg_latency_ms: float = 50.0,
    p95_latency_ms: float = 120.0,
    recovery_time_seconds: float = 3.0,
) -> ServiceSlaItem:
    """Calculate SLA availability percentage, drop magnitude, and degradation severity."""
    if total_requests <= 0:
        actual_sla = 100.0
        sla_drop = 0.0
    else:
        success_count = max(0, total_requests - failed_requests)
        actual_sla = (success_count / total_requests) * 100.0
        sla_drop = max(0.0, sla_baseline - actual_sla)

    # Determine status
    if actual_sla >= sla_baseline:
        status = "healthy"
    elif actual_sla >= 98.0:
        status = "minor_degraded"
    elif actual_sla >= 90.0:
        status = "severely_degraded"
    else:
        status = "outage"

    return ServiceSlaItem(
        service_name=service_name,
        total_requests=total_requests,
        failed_requests=failed_requests,
        availability_sla_pct=actual_sla,
        sla_baseline_target=sla_baseline,
        sla_drop_pct=sla_drop,
        avg_latency_ms=avg_latency_ms,
        p95_latency_ms=p95_latency_ms,
        recovery_time_seconds=recovery_time_seconds,
        degradation_status=status,
    )


def compute_mesh_resilience_score(
    service_items: list[ServiceSlaItem],
    *,
    blast_radius_breached: bool = False,
    emergency_aborted: bool = False,
) -> tuple[float, str, str]:
    """Compute overall mesh architectural resilience score (0-100), grade, and recommendation."""
    if not service_items:
        return 100.0, "A", "服务网格未发生故障扰动，架构运行稳定。"

    # 1. SLA Score (40% weight): average availability
    avg_sla = sum(s.availability_sla_pct for s in service_items) / len(service_items)
    sla_score = min(100.0, max(0.0, (avg_sla - 80.0) * 5.0))  # 100% -> 100, 90% -> 50, <80% -> 0

    # 2. Recovery Speed Score (30% weight): average RTO in seconds
    avg_rto = sum(s.recovery_time_seconds for s in service_items) / len(service_items)
    if avg_rto <= 3.0:
        rto_score = 100.0
    elif avg_rto <= 10.0:
        rto_score = 80.0
    elif avg_rto <= 25.0:
        rto_score = 55.0
    else:
        rto_score = 25.0

    # 3. Blast Radius Containment Score (20% weight)
    if emergency_aborted:
        containment_score = 20.0
    elif blast_radius_breached:
        containment_score = 50.0
    else:
        containment_score = 100.0

    # 4. Error Tolerance Score (10% weight)
    max_drop = max(s.sla_drop_pct for s in service_items)
    err_score = max(0.0, 100.0 - max_drop * 5.0)

    # Weighted sum
    total_score = round(
        0.40 * sla_score + 0.30 * rto_score + 0.20 * containment_score + 0.10 * err_score,
        1,
    )
    total_score = max(0.0, min(100.0, total_score))

    # Grade determination
    if total_score >= 90.0:
        grade = "A"
        tip = "服务网格展现卓越的高可用自愈韧性（Grade A），具备秒级故障隔离与自愈恢复能力。"
    elif total_score >= 80.0:
        grade = "B"
        tip = "服务网格抗压表现良好（Grade B），故障在可控范围内平稳恢复，建议优化边缘服务超时。"
    elif total_score >= 65.0:
        grade = "C"
        tip = "服务网格自愈存在延迟且伴随明显 SLA 震荡（Grade C），建议配置网关断路保护与客户端退避重试。"
    else:
        grade = "D" if total_score >= 50.0 else "F"
        tip = "服务网格抗故障能力脆弱（Grade D/F），存在大面积级联雪崩风险，需紧急加固服务熔断限流架构。"

    return total_score, grade, tip


def compile_mesh_resilience_report(
    experiment_id: str,
    services_data: list[dict[str, Any]],
    *,
    sla_baseline_target: float = DEFAULT_SLA_TARGET_PERCENT,
    blast_radius_breached: bool = False,
    emergency_aborted: bool = False,
) -> dict[str, Any]:
    """Compile comprehensive Whole-Mesh High Availability SLA Resilience Report."""
    service_items: list[ServiceSlaItem] = []

    for s in services_data:
        s_name = str(s.get("service_name", "unknown-service"))
        tot = int(s.get("total_requests", 100))
        failed = int(s.get("failed_requests", 0))
        item = calculate_service_sla(
            s_name,
            tot,
            failed,
            sla_baseline=float(s.get("sla_baseline", sla_baseline_target)),
            avg_latency_ms=float(s.get("avg_latency_ms", 45.0)),
            p95_latency_ms=float(s.get("p95_latency_ms", 120.0)),
            recovery_time_seconds=float(s.get("recovery_time_seconds", 3.0)),
        )
        service_items.append(item)

    score, grade, recommendation = compute_mesh_resilience_score(
        service_items,
        blast_radius_breached=blast_radius_breached,
        emergency_aborted=emergency_aborted,
    )

    report_id = f"rpt_mesh_{experiment_id}_{uuid.uuid4().hex[:8]}"
    lowest_sla_svc = min(service_items, key=lambda x: x.availability_sla_pct, default=None)

    return {
        "report_id": report_id,
        "experiment_id": experiment_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "resilience_score": score,
            "resilience_grade": grade,
            "total_services_evaluated": len(service_items),
            "lowest_sla_service": lowest_sla_svc.service_name if lowest_sla_svc else None,
            "lowest_sla_percent": lowest_sla_svc.availability_sla_pct if lowest_sla_svc else 100.0,
            "blast_radius_breached": blast_radius_breached,
            "emergency_aborted": emergency_aborted,
            "recommendation": recommendation,
        },
        "services": [item.to_dict() for item in service_items],
    }
