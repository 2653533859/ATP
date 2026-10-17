"""灰度击穿自动熔断与秒级一键回滚看门狗服务 (T2.2)

监控金丝雀相对基线指标偏离红线，超标毫秒级自动触发切流断路与版本回滚:
1. 灰度熔断策略定义 (CanaryRollbackPolicy: 错误率差值上限、P99时延倍率红线、成功率底线);
2. 指标越界毫秒级判定 (evaluate_canary_rollback_guard);
3. 联动染色引擎自动切流 (execute_canary_rollback: 强制将分流权重置为 0% 并禁用染色规则);
4. 综合看门狗裁决审计输出 (CanaryRollbackGuardVerdict & CanaryGuardAction)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.canary_baseline_metric_comparator import (
    CanaryDualTrackComparisonReport,
    MetricDeviationVerdict,
)
from app.services.canary_traffic_coloration_engine import (
    get_global_canary_manager,
)


class CanaryGuardAction(str, enum.Enum):
    SAFE_PROCEED = "SAFE_PROCEED"  # 指标平稳受控，允许灰度放量
    WARNING_WATCH = "WARNING_WATCH"  # 处于预警边缘带，保持观察未触发熔断
    TRIGGERED_AUTO_ROLLBACK = "TRIGGERED_AUTO_ROLLBACK"  # 触碰安全红线击穿，看门狗已自动触发紧急切流回滚
    ROLLBACK_COMPLETED = "ROLLBACK_COMPLETED"  # 切流回滚完成，100% 流量已回退基线稳定态


@dataclass
class CanaryRollbackPolicy:
    policy_id: str = "policy_canary_strict_guard"
    max_error_rate_diff_pct: float = 2.0  # 允许的金丝雀错误率最大增加差值 (默认 2.0%)
    max_latency_ratio: float = 1.50  # 允许的金丝雀 P99 延迟最大倍数 (默认 1.50x)
    min_success_rate_floor_pct: float = 95.0  # 业务成功率最低硬性底线 (默认 95.0%)
    auto_rollback_enabled: bool = True  # 击穿是否自动触发毫秒级切流回滚

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanaryRollbackGuardVerdict:
    guard_verdict_id: str
    target_service: str
    canary_version: str
    is_tripped: bool
    action: CanaryGuardAction
    tripped_rules: List[str]
    disabled_rules_count: int
    verdict_message: str
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "guard_verdict_id": self.guard_verdict_id,
            "target_service": self.target_service,
            "canary_version": self.canary_version,
            "is_tripped": self.is_tripped,
            "action": self.action.value,
            "tripped_rules": self.tripped_rules,
            "disabled_rules_count": self.disabled_rules_count,
            "verdict_message": self.verdict_message,
            "checked_at": self.checked_at,
        }


def execute_canary_rollback(target_service: str, reason: str = "") -> int:
    """联动全链路流量染色引擎执行紧急切流回滚：将目标微服务所有金丝雀规则权重清零并禁用"""
    _ = reason
    mgr = get_global_canary_manager()
    disabled_count = 0
    for rule in mgr.list_rules(target_service=target_service):
        if rule.is_enabled:
            rule.is_enabled = False
            rule.weight_pct = 0.0
            disabled_count += 1
    return disabled_count


def evaluate_canary_rollback_guard(
    comparison_report: CanaryDualTrackComparisonReport,
    policy: Optional[CanaryRollbackPolicy] = None,
) -> CanaryRollbackGuardVerdict:
    """评估双轨比对指标，若击穿熔断红线则毫秒级自动触发版本切流回滚"""
    guard_id = f"cgrd_{uuid.uuid4().hex[:10]}"
    p = policy or CanaryRollbackPolicy()
    tripped_rules: List[str] = []

    # 1. 检查错误率相对差值
    err_diff = comparison_report.error_rate_diff_pct
    if err_diff > p.max_error_rate_diff_pct:
        tripped_rules.append(
            f"金丝雀相对基线错误率增量 ({round(err_diff, 2)}%) 击穿熔断红线 ({p.max_error_rate_diff_pct}%)"
        )

    # 2. 检查 P99 响应延迟倍率
    lat_ratio = comparison_report.latency_p99_ratio
    if lat_ratio > p.max_latency_ratio:
        tripped_rules.append(
            f"金丝雀 P99 响应延迟 ({round(lat_ratio, 2)}x) 超出基线倍率安全天花板 ({p.max_latency_ratio}x)"
        )

    # 3. 检查金丝雀业务成功率底线
    canary_succ = comparison_report.canary_metrics.success_rate_pct
    if canary_succ < p.min_success_rate_floor_pct:
        tripped_rules.append(
            f"金丝雀业务成功率 ({round(canary_succ, 1)}%) 跌破生产保底红线 ({p.min_success_rate_floor_pct}%)"
        )

    is_tripped = len(tripped_rules) > 0
    disabled_count = 0

    if is_tripped:
        if p.auto_rollback_enabled:
            disabled_count = execute_canary_rollback(
                target_service=comparison_report.target_service,
                reason="; ".join(tripped_rules),
            )
            action = CanaryGuardAction.TRIGGERED_AUTO_ROLLBACK
            msg = (
                f"【紧急熔断触发】金丝雀版本 [{comparison_report.canary_version}] 触碰安全红线！"
                f"看门狗已自动切断金丝雀流量 (已重置 {disabled_count} 条染色规则)，100% 流量秒级回退至稳定基线！"
            )
        else:
            action = CanaryGuardAction.WARNING_WATCH
            msg = f"【告警提示】金丝雀指标触碰红线，当前未开启自动回滚，请人工介入处理: {tripped_rules}"
    else:
        if comparison_report.overall_verdict == MetricDeviationVerdict.WARNING_DEGRADED:
            action = CanaryGuardAction.WARNING_WATCH
            msg = "金丝雀指标存在轻微偏离，仍在安全容忍带内，继续保持观察。"
        else:
            action = CanaryGuardAction.SAFE_PROCEED
            msg = "金丝雀与基线双轨指标平稳受控，符合灰度放量准则。"

    return CanaryRollbackGuardVerdict(
        guard_verdict_id=guard_id,
        target_service=comparison_report.target_service,
        canary_version=comparison_report.canary_version,
        is_tripped=is_tripped,
        action=action,
        tripped_rules=tripped_rules,
        disabled_rules_count=disabled_count,
        verdict_message=msg,
    )
