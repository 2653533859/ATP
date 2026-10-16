"""生产防击穿自适应毫秒级分级限流与熔断保护大脑 (T3.3)。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class BreakerState(str, Enum):
    """自适应熔断器状态机。"""

    CLOSED_NORMAL = "CLOSED_NORMAL"  # 正常放行 (全速压测)
    THROTTLING_STAGE_1 = "THROTTLING_STAGE_1"  # 一级缓速 (水位 70%~80%, 削减 25% 速率)
    THROTTLING_STAGE_2 = "THROTTLING_STAGE_2"  # 二级急刹 (水位 80%~85%, 削减 60% 速率)
    TRIPPED_HARD_BREAK = "TRIPPED_HARD_BREAK"  # 硬核熔断阻断 (水位 >= 85% 或报错激增, 毫秒掐断压测)
    HALF_OPEN_PROBE = "HALF_OPEN_PROBE"  # 半开试探自愈 (冷却后低速探测)


class BreakerAction(str, Enum):
    """熔断器下发动作。"""

    PASS_FULL_SPEED = "PASS_FULL_SPEED"  # 全速推进
    THROTTLE_DOWN = "THROTTLE_DOWN"  # 降速限流
    ABORT_STRESS_TEST = "ABORT_STRESS_TEST"  # 紧急中止压测并隔离


@dataclass
class BreakerDecisionItem:
    """单次熔断评估裁决结果。"""

    decision_id: str
    breaker_state: BreakerState
    action: BreakerAction
    throttle_ratio_pct: float  # 允许通过的流量比例 (0% ~ 100%)
    trigger_reason: str
    suggested_safe_tps: float  # 推荐安全降速后 TPS 上限

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "breaker_state": self.breaker_state.value,
            "action": self.action.value,
            "throttle_ratio_pct": round(self.throttle_ratio_pct, 1),
            "trigger_reason": self.trigger_reason,
            "suggested_safe_tps": round(self.suggested_safe_tps, 1),
        }


@dataclass
class AvalancheBreakerAuditReport:
    """防雪崩熔断全景审计报告。"""

    report_id: str
    scenario_name: str
    current_watermark_pct: float
    current_p99_latency_ms: float
    current_error_rate_pct: float
    is_circuit_broken: bool
    final_decision: BreakerDecisionItem
    remediation_instructions: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "scenario_name": self.scenario_name,
            "current_watermark_pct": round(self.current_watermark_pct, 1),
            "current_p99_latency_ms": round(self.current_p99_latency_ms, 1),
            "current_error_rate_pct": round(self.current_error_rate_pct, 2),
            "is_circuit_broken": self.is_circuit_broken,
            "final_decision": self.final_decision.to_dict(),
            "remediation_instructions": self.remediation_instructions,
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告仓库与熔断器内部运行时状态
_BREAKER_REPORTS: dict[str, AvalancheBreakerAuditReport] = {}
_CURRENT_GLOBAL_BREAKER_STATE: BreakerState = BreakerState.CLOSED_NORMAL


def clear_avalanche_breaker_store() -> None:
    """清空熔断器报告与状态 (单测专用)。"""
    global _CURRENT_GLOBAL_BREAKER_STATE
    _BREAKER_REPORTS.clear()
    _CURRENT_GLOBAL_BREAKER_STATE = BreakerState.CLOSED_NORMAL


def get_current_breaker_state() -> BreakerState:
    """获取当前全局熔断器状态。"""
    return _CURRENT_GLOBAL_BREAKER_STATE


def reset_circuit_breaker() -> BreakerState:
    """手动强制重置熔断器为正常闭合状态。"""
    global _CURRENT_GLOBAL_BREAKER_STATE
    _CURRENT_GLOBAL_BREAKER_STATE = BreakerState.CLOSED_NORMAL
    return _CURRENT_GLOBAL_BREAKER_STATE


def evaluate_adaptive_circuit_breaker(
    scenario_name: str,
    max_resource_watermark_pct: float,
    p99_latency_ms: float = 120.0,
    error_rate_pct: float = 0.0,
    current_tps: float = 2000.0,
) -> AvalancheBreakerAuditReport:
    """自适应评估基础设施与调用链指标，执行毫秒级分级限流与防雪崩熔断判定。"""
    global _CURRENT_GLOBAL_BREAKER_STATE

    instructions: list[str] = []
    did = f"brk_{uuid.uuid4().hex[:8]}"

    # 1. 触发硬核阻断熔断 (硬指标: 水位 >= 85% 或 错误率 >= 5% 或 P99 >= 3000ms)
    if max_resource_watermark_pct >= 85.0 or error_rate_pct >= 5.0 or p99_latency_ms >= 3000.0:
        _CURRENT_GLOBAL_BREAKER_STATE = BreakerState.TRIPPED_HARD_BREAK
        action = BreakerAction.ABORT_STRESS_TEST
        ratio = 0.0
        safe_tps = 0.0
        reason = (
            f"防雪崩硬核熔断已紧急触发！(下游水位: {max_resource_watermark_pct:.1f}% >= 85% 或 "
            f"错误率: {error_rate_pct:.2f}% >= 5% 或 P99: {p99_latency_ms:.0f}ms >= 3000ms)，"
            f"已向全网压测机广播 ABORT 信号，即刻阻断全部压测流量！"
        )
        instructions.append("立即停止当前全链路压测任务，切勿继续加压。")
        instructions.append("监控生产核心业务指标 (QPS、成功率)，确认未发生级联击穿雪崩。")
        instructions.append("当下游容量水位降至 65% 安全线以下并冷却 30s 后，方可通过 API 重置熔断器。")

    # 2. 触发二级急刹限流 (水位 80%~85%)
    elif max_resource_watermark_pct >= 80.0 or p99_latency_ms >= 1500.0:
        _CURRENT_GLOBAL_BREAKER_STATE = BreakerState.THROTTLING_STAGE_2
        action = BreakerAction.THROTTLE_DOWN
        ratio = 40.0  # 削减 60% 速率
        safe_tps = current_tps * 0.40
        reason = f"触发二级急刹限流：下游水位达到 {max_resource_watermark_pct:.1f}%，压测并发自动阶梯收敛 60%。"
        instructions.append(f"当前压测流量已被自适应限流至 {safe_tps:.0f} TPS (40% 容量)，阻止新批次加压。")

    # 3. 触发一级缓速限流 (水位 70%~80%)
    elif max_resource_watermark_pct >= 70.0 or p99_latency_ms >= 800.0:
        _CURRENT_GLOBAL_BREAKER_STATE = BreakerState.THROTTLING_STAGE_1
        action = BreakerAction.THROTTLE_DOWN
        ratio = 75.0  # 削减 25% 速率
        safe_tps = current_tps * 0.75
        reason = f"触发一级缓速限流：下游水位达到 {max_resource_watermark_pct:.1f}%，轻度降速 25% 观察系统自适应能力。"
        instructions.append(f"压测速率轻度平抑至 {safe_tps:.0f} TPS，密切跟踪 DB 连接池与线程池排队情况。")

    # 4. 正常全速闭合状态
    else:
        _CURRENT_GLOBAL_BREAKER_STATE = BreakerState.CLOSED_NORMAL
        action = BreakerAction.PASS_FULL_SPEED
        ratio = 100.0
        safe_tps = current_tps
        reason = "各项指标均处于安全水位区间 (<70%)，全速放行压测流量。"
        instructions.append("系统健康度良好，允许按照阶梯加压策略平稳提升并发。")

    decision = BreakerDecisionItem(
        decision_id=did,
        breaker_state=_CURRENT_GLOBAL_BREAKER_STATE,
        action=action,
        throttle_ratio_pct=ratio,
        trigger_reason=reason,
        suggested_safe_tps=safe_tps,
    )

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", scenario_name)[:16]
    report_id = f"brk_rpt_{safe_name}_{int(now.timestamp())}"

    report = AvalancheBreakerAuditReport(
        report_id=report_id,
        scenario_name=scenario_name,
        current_watermark_pct=max_resource_watermark_pct,
        current_p99_latency_ms=p99_latency_ms,
        current_error_rate_pct=error_rate_pct,
        is_circuit_broken=(_CURRENT_GLOBAL_BREAKER_STATE == BreakerState.TRIPPED_HARD_BREAK),
        final_decision=decision,
        remediation_instructions=instructions,
        created_at=now,
    )

    _BREAKER_REPORTS[report_id] = report
    return report


def get_avalanche_breaker_report(report_id: str) -> AvalancheBreakerAuditReport | None:
    """按 ID 查询熔断评估报告。"""
    return _BREAKER_REPORTS.get(report_id)


def list_avalanche_breaker_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史熔断报告列表。"""
    reports = list(reversed(list(_BREAKER_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
