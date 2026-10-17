"""服务降级与熔断恢复时间 RTO/RPO 评估器服务 (T2.1)

量化分布式系统在混沌故障注入下的熔断响应速度、降级接管与自愈恢复耗时:
1. 断路器状态机 (CircuitBreakerState: CLOSED | OPEN | HALF_OPEN);
2. 熔断触发时间 (Trip Time, TT)、降级接管率 (Fallback Rate)、恢复时间目标 (RTO) 与数据丢失点 (RPO) 量化建模;
3. 弹性韧性四级评级模型 (ResilienceGrade: GRADE_A | GRADE_B | GRADE_C | GRADE_D);
4. 综合韧性评估报告与 SLO 合规判定 (ResilienceRTOEvaluation)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class CircuitBreakerState(str, enum.Enum):
    CLOSED = "CLOSED"  # 正常闭合，全量放行
    OPEN = "OPEN"  # 熔断打开，全量切入降级旁路
    HALF_OPEN = "HALF_OPEN"  # 半开探测自愈中


class ResilienceGrade(str, enum.Enum):
    GRADE_A_RESILIENT = "GRADE_A_RESILIENT"  # 卓越韧性: TT < 500ms, RTO < 5s, 降级率 100%
    GRADE_B_ACCEPTABLE = "GRADE_B_ACCEPTABLE"  # 良好可用: TT < 1500ms, RTO < 15s, 降级率 >= 95%
    GRADE_C_DEGRADED = "GRADE_C_DEGRADED"  # 存在延迟与弱点: TT > 1500ms 或 RTO > 30s
    GRADE_D_VULNERABLE = "GRADE_D_VULNERABLE"  # 严重脆弱: 未触发熔断导致雪崩超时


@dataclass
class ResilienceRTOEvaluation:
    evaluation_id: str
    experiment_id: str
    target_service: str
    circuit_breaker_trip_time_ms: float  # 熔断器触发耗时 (毫秒)
    fallback_takeover_rate_pct: float  # 降级旁路接管率 (0.0 ~ 100.0%)
    recovery_time_objective_seconds: float  # 故障恢复时间 RTO (秒)
    recovery_point_objective_seconds: float  # 数据丢失点 RPO (秒)
    resilience_grade: ResilienceGrade
    is_slo_compliant: bool
    observations: List[str] = field(default_factory=list)
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "experiment_id": self.experiment_id,
            "target_service": self.target_service,
            "circuit_breaker_trip_time_ms": round(self.circuit_breaker_trip_time_ms, 1),
            "fallback_takeover_rate_pct": round(self.fallback_takeover_rate_pct, 1),
            "recovery_time_objective_seconds": round(self.recovery_time_objective_seconds, 2),
            "recovery_point_objective_seconds": round(self.recovery_point_objective_seconds, 2),
            "resilience_grade": self.resilience_grade.value,
            "is_slo_compliant": self.is_slo_compliant,
            "observations": self.observations,
            "evaluated_at": self.evaluated_at,
        }


def evaluate_resilience_rto_rpo(
    experiment_id: str,
    target_service: str,
    fault_injected_at: float,
    circuit_tripped_at: Optional[float],
    fault_removed_at: float,
    recovered_to_steady_at: Optional[float],
    total_fault_requests: int = 100,
    fallback_success_requests: int = 100,
    data_loss_window_seconds: float = 0.0,
    slo_max_rto_seconds: float = 10.0,
) -> ResilienceRTOEvaluation:
    """综合计算混沌演练下系统的断路器触发耗时、降级接管率、RTO 与 RPO"""
    eval_id = f"rto_{uuid.uuid4().hex[:10]}"
    observations: List[str] = []

    # 1. 计算熔断触发耗时 (Trip Time)
    if circuit_tripped_at is not None and circuit_tripped_at >= fault_injected_at:
        trip_time_ms = round((circuit_tripped_at - fault_injected_at) * 1000.0, 2)
        observations.append(f"熔断断路器在故障发生后 {round(trip_time_ms, 1)}ms 内成功跃迁为 OPEN")
    else:
        trip_time_ms = 9999.0  # 未触发熔断
        observations.append("警报: 故障注入期间未能触发断路器熔断，下游服务直接暴露在故障中")

    # 2. 计算降级接管率
    takeover_rate = (fallback_success_requests / total_fault_requests * 100.0) if total_fault_requests > 0 else 100.0
    observations.append(f"降级旁路保底响应接管率: {round(takeover_rate, 1)}%")

    # 3. 计算自愈恢复时间 (RTO)
    if recovered_to_steady_at is not None and recovered_to_steady_at >= fault_removed_at:
        rto_seconds = round(recovered_to_steady_at - fault_removed_at, 2)
        observations.append(f"系统自愈收敛回到健康稳态耗时 (RTO): {round(rto_seconds, 2)}s")
    else:
        rto_seconds = 60.0
        observations.append("警报: 故障移除后系统未能按期自动恢复稳态，可能发生服务雪崩或死锁")

    # 4. 判定韧性等级
    rpo_seconds = max(0.0, data_loss_window_seconds)

    if trip_time_ms <= 500.0 and rto_seconds <= 5.0 and takeover_rate >= 99.0 and rpo_seconds == 0.0:
        grade = ResilienceGrade.GRADE_A_RESILIENT
        is_slo = True
        observations.append("评定为 GRADE_A 卓越级韧性: 毫秒级熔断切流，秒级自愈恢复，零数据损失")
    elif trip_time_ms <= 1500.0 and rto_seconds <= slo_max_rto_seconds and takeover_rate >= 90.0:
        grade = ResilienceGrade.GRADE_B_ACCEPTABLE
        is_slo = True
        observations.append("评定为 GRADE_B 良好可用: 符合微服务生产高可用发布准入门槛")
    elif trip_time_ms < 5000.0 and rto_seconds <= 30.0:
        grade = ResilienceGrade.GRADE_C_DEGRADED
        is_slo = False
        observations.append("评定为 GRADE_C 次级韧性: 熔断较慢或自愈收敛耗时较长，未达生产 SLO")
    else:
        grade = ResilienceGrade.GRADE_D_VULNERABLE
        is_slo = False
        observations.append("评定为 GRADE_D 严重脆弱: 系统缺乏有效断路器或自愈能力，面临雪崩风险")

    return ResilienceRTOEvaluation(
        evaluation_id=eval_id,
        experiment_id=experiment_id,
        target_service=target_service,
        circuit_breaker_trip_time_ms=trip_time_ms,
        fallback_takeover_rate_pct=takeover_rate,
        recovery_time_objective_seconds=rto_seconds,
        recovery_point_objective_seconds=rpo_seconds,
        resilience_grade=grade,
        is_slo_compliant=is_slo,
        observations=observations,
    )
