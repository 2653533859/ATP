"""演练爆炸半径实时监控与紧急熔断回滚看门狗服务 (T2.2)

贯彻混沌工程最小爆炸半径原则，实时监控故障波及面并在触碰红线时毫秒级紧急熔断回滚:
1. 爆炸半径多维防线策略定义 (BlastRadiusPolicy: 最大服务数、错误率红线、延迟天花板、VIP租户豁免);
2. 实时拓扑波及面动态探测与超标判定 (BlastRadiusObservation & check_blast_radius);
3. 毫秒级自动紧急熔断与全局故障算子安全剥离 (Emergency Abort & Teardown Execution);
4. 综合熔断裁决结论与安全审计记录输出 (BlastControllerVerdict)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.chaos_fault_injector_library import get_global_fault_library
from app.services.chaos_steady_state_evaluator import get_global_chaos_manager


class BlastTripAction(str, enum.Enum):
    SAFE_CONTAINED = "SAFE_CONTAINED"  # 爆炸半径受控，演练安全进行中
    WARNING_BOUNDARY = "WARNING_BOUNDARY"  # 逼近爆炸半径安全边界，发出预警
    EMERGENCY_ABORT = "EMERGENCY_ABORT"  # 击穿安全红线，立即强制紧急熔断回滚并拔除故障
    TEARDOWN_COMPLETED = "TEARDOWN_COMPLETED"  # 故障算子已全部安全清理，现场恢复干净


@dataclass
class BlastRadiusPolicy:
    policy_id: str
    experiment_id: str
    max_impacted_services: int = 2  # 允许最大波及微服务节点数
    max_error_rate_pct: float = 5.0  # 全局业务错误率熔断红线 (默认 > 5.0% 立即熔断)
    latency_ceiling_ms: float = 1200.0  # P99 响应延迟绝对天花板 (默认 > 1200ms 熔断)
    exempt_tenant_ids: List[str] = field(default_factory=lambda: ["tenant_vip_001", "tenant_bank_core"])
    auto_abort_enabled: bool = True  # 是否自动触发紧急熔断回滚
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BlastRadiusObservation:
    observation_id: str
    impacted_services: List[str]
    current_error_rate_pct: float
    current_p99_latency_ms: float
    active_tenant_id: Optional[str] = None
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BlastControllerVerdict:
    experiment_id: str
    is_tripped: bool
    action: BlastTripAction
    verdict_id: str = field(default_factory=lambda: f"v_{uuid.uuid4().hex[:8]}")
    tripped_rules: List[str] = field(default_factory=list)
    teardown_actions_executed: List[str] = field(default_factory=list)
    verdict_message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict_id": self.verdict_id,
            "experiment_id": self.experiment_id,
            "is_tripped": self.is_tripped,
            "action": self.action.value,
            "tripped_rules": self.tripped_rules,
            "teardown_actions_executed": self.teardown_actions_executed,
            "verdict_message": self.verdict_message,
            "timestamp": self.timestamp,
        }


def is_tenant_exempt(tenant_id: Optional[str], policy: BlastRadiusPolicy) -> bool:
    """判定当前请求租户是否受白名单豁免保护 (严禁在演练中破坏核心 VIP 流量)"""
    if not tenant_id:
        return False
    return tenant_id in policy.exempt_tenant_ids


def execute_emergency_teardown(experiment_id: str) -> List[str]:
    """执行最高优先级紧急熔断剥离：强行拔除所有注入的混沌故障，终止演练实验"""
    actions: List[str] = []

    # 1. 禁用所有算子库中的故障规则
    lib = get_global_fault_library()
    for rule in lib.list_rules():
        if rule.enabled:
            rule.enabled = False
            actions.append(f"强制禁用故障算子 [{rule.name} ({rule.fault_id})]")

    # 2. 终止当前正在注入的混沌实验
    mgr = get_global_chaos_manager()
    session = mgr.stop_experiment(experiment_id)
    if session:
        actions.append(f"强行终止混沌实验会话 [{session.name} ({experiment_id})] 并重置为 STOPPED")

    return actions


def check_blast_radius(
    policy: BlastRadiusPolicy,
    observation: BlastRadiusObservation,
) -> BlastControllerVerdict:
    """实时评估当前演练爆炸半径是否越界，必要时毫秒级自动触发紧急熔断"""
    vid = f"bver_{uuid.uuid4().hex[:10]}"
    tripped_rules: List[str] = []

    # 1. 核心租户豁免检查
    if is_tenant_exempt(observation.active_tenant_id, policy):
        tripped_rules.append(f"检测到核心受保护豁免租户流量 [{observation.active_tenant_id}]，触发零破坏防御阻断")

    # 2. 检查波及服务节点数
    impacted_count = len(observation.impacted_services)
    if impacted_count > policy.max_impacted_services:
        tripped_rules.append(
            f"故障波及服务数超标: 当前波及 {impacted_count} 个服务 {observation.impacted_services} > 上限 {policy.max_impacted_services} 个"
        )

    # 3. 检查全局业务错误率红线
    if observation.current_error_rate_pct > policy.max_error_rate_pct:
        tripped_rules.append(
            f"业务错误率击穿熔断红线: 当前 {observation.current_error_rate_pct}% > 阈值 {policy.max_error_rate_pct}%"
        )

    # 4. 检查响应延迟天花板
    if observation.current_p99_latency_ms > policy.latency_ceiling_ms:
        tripped_rules.append(
            f"P99 延迟击穿绝对天花板: 当前 {observation.current_p99_latency_ms}ms > 阈值 {policy.latency_ceiling_ms}ms"
        )

    is_tripped = len(tripped_rules) > 0
    teardown_actions: List[str] = []

    if is_tripped:
        if policy.auto_abort_enabled:
            teardown_actions = execute_emergency_teardown(policy.experiment_id)
            action = BlastTripAction.EMERGENCY_ABORT
            msg = f"【紧急熔断触发】爆炸半径突破红线，已自动紧急剥离故障并终止演练！触发规则数: {len(tripped_rules)}"
        else:
            action = BlastTripAction.WARNING_BOUNDARY
            msg = f"【告警提示】爆炸半径突破预警边界，未配置自动熔断，请人工核查: {tripped_rules}"
    else:
        action = BlastTripAction.SAFE_CONTAINED
        msg = "演练爆炸半径受控正常，各项指标均在安全策略围栏之内"

    return BlastControllerVerdict(
        verdict_id=vid,
        experiment_id=policy.experiment_id,
        is_tripped=is_tripped,
        action=action,
        tripped_rules=tripped_rules,
        teardown_actions_executed=teardown_actions,
        verdict_message=msg,
    )
