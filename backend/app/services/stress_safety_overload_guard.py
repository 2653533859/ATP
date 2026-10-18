"""生产击穿毫秒级熔断与过载紧急泄压看门狗服务 (T2.2)

筑牢生产全链路影子压测绝对安全防线，严防压测流量击穿真实生产服务:
1. 生产多维击穿红线策略定义 (StressOverloadPolicy: CPU、错误率、P99延时、队列深度);
2. 生产实时运行态健康快照采集 (ProductionHealthSnapshot);
3. 毫秒级自动断路切流泄压 (execute_stress_circuit_break: 联动规则引擎瞬间清零压测并发并切断流量);
4. 四态看门狗裁决审计输出 (StressOverloadGuardVerdict: NORMAL_STRESS_SAFE | TRIGGERED_CIRCUIT_BREAK)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.stress_traffic_isolation_engine import get_global_stress_manager


class OverloadGuardAction(str, enum.Enum):
    NORMAL_STRESS_SAFE = "NORMAL_STRESS_SAFE"  # 生产指标平稳，处于安全承载区
    WARNING_LOAD_HIGH = "WARNING_LOAD_HIGH"  # 指标逼近红线，保持警戒
    TRIGGERED_CIRCUIT_BREAK = "TRIGGERED_CIRCUIT_BREAK"  # 触碰红线击穿！毫秒级自动熔断切流泄压
    RELIEF_COMPLETED = "RELIEF_COMPLETED"  # 泄压完成，压测流量已彻底清零切断


@dataclass
class StressOverloadPolicy:
    max_error_rate_pct: float = 1.0  # 生产服务错误率红线 (默认 1.0%)
    max_cpu_utilization_pct: float = 85.0  # 生产 Pod CPU 占用红线 (默认 85%)
    max_p99_latency_ms: float = 500.0  # 生产 P99 响应耗时上限 (默认 500ms)
    max_queue_depth: int = 1000  # 线程池或请求排队上限 (默认 1000)
    auto_circuit_break_enabled: bool = True  # 是否开启毫秒级自动断路切流


@dataclass
class ProductionHealthSnapshot:
    target_service: str
    measured_tps: float
    measured_error_rate_pct: float
    measured_p99_latency_ms: float
    measured_cpu_pct: float
    measured_queue_depth: int = 50
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StressOverloadGuardVerdict:
    guard_verdict_id: str
    target_service: str
    is_tripped: bool  # 是否触发了熔断拦截
    action: OverloadGuardAction
    tripped_reasons: List[str]
    disabled_rules_count: int
    health_snapshot: ProductionHealthSnapshot
    policy_thresholds: Dict[str, Any]
    verdict_message: str
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "guard_verdict_id": self.guard_verdict_id,
            "target_service": self.target_service,
            "is_tripped": self.is_tripped,
            "action": self.action.value,
            "tripped_reasons": self.tripped_reasons,
            "disabled_rules_count": self.disabled_rules_count,
            "health_snapshot": self.health_snapshot.to_dict(),
            "policy_thresholds": self.policy_thresholds,
            "verdict_message": self.verdict_message,
            "checked_at": self.checked_at,
        }


def execute_stress_circuit_break(target_service: str, reason: str = "") -> int:
    """联动压测引擎瞬间切断目标服务的所有压测规则，实现秒级泄压"""
    _ = reason
    mgr = get_global_stress_manager()
    disabled_count = 0
    for r in mgr.list_rules(target_service=target_service):
        if r.is_enabled:
            r.is_enabled = False
            disabled_count += 1
    return disabled_count


def evaluate_stress_overload_guard(
    snapshot: ProductionHealthSnapshot,
    policy: Optional[StressOverloadPolicy] = None,
) -> StressOverloadGuardVerdict:
    """生产防击穿安全看门狗实时审查引擎"""
    verdict_id = f"st_grd_{uuid.uuid4().hex[:10]}"
    pol = policy or StressOverloadPolicy()

    tripped: List[str] = []

    # 1. 检查请求错误率红线
    if snapshot.measured_error_rate_pct > pol.max_error_rate_pct:
        tripped.append(f"错误率 {snapshot.measured_error_rate_pct:.2f}% 突破安全红线 ({pol.max_error_rate_pct:.2f}%)")

    # 2. 检查 CPU 使用率红线
    if snapshot.measured_cpu_pct > pol.max_cpu_utilization_pct:
        tripped.append(
            f"CPU 使用率 {snapshot.measured_cpu_pct:.1f}% 突破生产安全红线 ({pol.max_cpu_utilization_pct:.1f}%)"
        )

    # 3. 检查 P99 响应延迟红线
    if snapshot.measured_p99_latency_ms > pol.max_p99_latency_ms:
        tripped.append(
            f"P99 延迟 {snapshot.measured_p99_latency_ms:.1f}ms 超过保护上限 ({pol.max_p99_latency_ms:.1f}ms)"
        )

    # 4. 检查队列排队深度红线
    if snapshot.measured_queue_depth > pol.max_queue_depth:
        tripped.append(f"排队队列深度 {snapshot.measured_queue_depth} 超过阈值 ({pol.max_queue_depth})")

    is_tripped = len(tripped) > 0
    disabled_count = 0

    if is_tripped:
        if pol.auto_circuit_break_enabled:
            disabled_count = execute_stress_circuit_break(
                target_service=snapshot.target_service,
                reason="; ".join(tripped),
            )
            action = OverloadGuardAction.TRIGGERED_CIRCUIT_BREAK
            msg = f"生产保护触发紧急熔断！已瞬间切断压测流量 (切断 {disabled_count} 条规则): {'; '.join(tripped)}"
        else:
            action = OverloadGuardAction.WARNING_LOAD_HIGH
            msg = f"指标已超标但未开启自动断路: {'; '.join(tripped)}"
    else:
        # 指标平稳，检查是否处于高水位预警区间 (如 CPU > 75%)
        if snapshot.measured_cpu_pct > 75.0 or snapshot.measured_error_rate_pct > 0.5:
            action = OverloadGuardAction.WARNING_LOAD_HIGH
            msg = "指标处于高负载警戒区间，保持施压观察"
        else:
            action = OverloadGuardAction.NORMAL_STRESS_SAFE
            msg = "生产指标平稳，处于安全发压承载区"

    return StressOverloadGuardVerdict(
        guard_verdict_id=verdict_id,
        target_service=snapshot.target_service,
        is_tripped=is_tripped,
        action=action,
        tripped_reasons=tripped,
        disabled_rules_count=disabled_count,
        health_snapshot=snapshot,
        policy_thresholds=asdict(pol),
        verdict_message=msg,
    )
