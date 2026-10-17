"""混沌演练非生产隔离与绝对安全围栏看门狗服务 (T4.1)

严防在生产非演练时段或对关键生产数据库执行破坏性故障注入,提供绝对环境强隔离与权限阻断:
1. 绝对环境准入校验 (环境隔离门禁: 生产环境必须具备变更工单、特批维护窗口与安全令牌);
2. 高危保护资产阻断黑名单 (Forbidden Targets: 核心主库、清算账本、控制面强禁止注入);
3. 破坏性算子参数边界看门狗 (超高丢包率、恶性载荷破坏强制拦截);
4. 结构化安全裁决报告输出 (ChaosSafetyGuardVerdict)。
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class SafetyVerdictAction(str, enum.Enum):
    ALLOW_SAFE = "ALLOW_SAFE"  # 安全检查通过，允许注入
    BLOCKED_PROD_UNAUTHORIZED = "BLOCKED_PROD_UNAUTHORIZED"  # 生产环境未经授权或超出维护窗口，强制拦截
    BLOCKED_FORBIDDEN_ASSET = "BLOCKED_FORBIDDEN_ASSET"  # 触碰高危禁止注入核心资产(主库/账本)，绝对阻断
    BLOCKED_UNSAFE_OPERATOR = "BLOCKED_UNSAFE_OPERATOR"  # 算子破坏性参数击穿安全防护底线，拦截


# 绝不可被注入的最高危核心资产黑名单 (正则匹配模式)
FORBIDDEN_ASSET_PATTERNS = [
    r".*(master.*db|db.*master).*",
    r".*(primary.*mysql|mysql.*primary).*",
    r".*(pg.*cluster.*writer|postgres.*writer).*",
    r".*core.*ledger.*",
    r".*billing.*settlement.*",
    r".*k8s.*apiserver.*",
    r".*etcd.*cluster.*",
    r".*production.*vault.*",
]


@dataclass
class ChaosSafetyGuardVerdict:
    verdict_id: str
    is_allowed: bool
    action: SafetyVerdictAction
    environment: str
    target_service: str
    block_reasons: List[str]
    safety_rule_applied: str
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict_id": self.verdict_id,
            "is_allowed": self.is_allowed,
            "action": self.action.value,
            "environment": self.environment,
            "target_service": self.target_service,
            "block_reasons": self.block_reasons,
            "safety_rule_applied": self.safety_rule_applied,
            "checked_at": self.checked_at,
        }


def is_forbidden_target_asset(target_service: str, target_pattern: str) -> bool:
    """检查是否触碰严禁注入的高危核心存储或控制面资产"""
    text_to_check = f"{target_service}:{target_pattern}".lower()
    for pattern in FORBIDDEN_ASSET_PATTERNS:
        if re.search(pattern, text_to_check):
            return True
    return False


def is_valid_safety_token(token: Optional[str]) -> bool:
    """校验生产特批安全令牌格式与合法性 (需 ATP-SAFETY-SECURE- 统一前缀且长度至少 24 位)"""
    if not token:
        return False
    return token.startswith("ATP-SAFETY-SECURE-") and len(token) >= 24


def evaluate_chaos_safety_boundary(
    environment: str,
    target_service: str,
    target_pattern: str,
    fault_type: str,
    config: Dict[str, Any],
    approved_ticket_id: Optional[str] = None,
    maintenance_window_start: Optional[datetime] = None,
    maintenance_window_end: Optional[datetime] = None,
    safety_token: Optional[str] = None,
    current_time: Optional[datetime] = None,
) -> ChaosSafetyGuardVerdict:
    """全面裁决当前混沌故障注入是否符合非生产隔离与绝对安全围栏准则"""
    verdict_id = f"saf_{uuid.uuid4().hex[:10]}"
    block_reasons: List[str] = []
    env_lower = environment.strip().lower()
    is_prod = env_lower in ("prod", "production", "live", "online")
    now = current_time or datetime.now(timezone.utc)

    # 1. 绝对最高优先级: 高危禁止资产阻断 (即使生产特批也不能注入主库)
    if is_forbidden_target_asset(target_service, target_pattern):
        block_reasons.append(
            f"目标资产 [{target_service}:{target_pattern}] 命中绝对禁止注入高危资产黑名单 (如数据库主库/核心账本/控制面)"
        )
        return ChaosSafetyGuardVerdict(
            verdict_id=verdict_id,
            is_allowed=False,
            action=SafetyVerdictAction.BLOCKED_FORBIDDEN_ASSET,
            environment=environment,
            target_service=target_service,
            block_reasons=block_reasons,
            safety_rule_applied="FORBIDDEN_CORE_ASSET_RULE",
        )

    # 2. 算子自身破坏性红线检查 (防范超高丢包率引起不可逆网络分区)
    packet_loss = config.get("packet_loss_rate", 0.0)
    if packet_loss > 0.8:
        block_reasons.append(
            f"丢包率参数 ({round(packet_loss * 100, 1)}%) 超过安全防线红线 (80.0%)，可能导致集群心跳失联与雪崩式分区"
        )
    latency_ms = config.get("latency_ms", 0.0)
    if latency_ms > 30000.0:
        block_reasons.append(f"网络延迟参数 ({latency_ms}ms) 超过安全防护上限 (30,000ms)，可能导致底层 TCP 连接耗尽")

    if block_reasons:
        return ChaosSafetyGuardVerdict(
            verdict_id=verdict_id,
            is_allowed=False,
            action=SafetyVerdictAction.BLOCKED_UNSAFE_OPERATOR,
            environment=environment,
            target_service=target_service,
            block_reasons=block_reasons,
            safety_rule_applied="UNSAFE_OPERATOR_PARAMETER_RULE",
        )

    # 3. 生产环境强隔离与三要素校验 (工单、维护窗口、安全令牌)
    if is_prod:
        prod_violations: List[str] = []
        if not approved_ticket_id or not approved_ticket_id.startswith("CHG-"):
            prod_violations.append("缺少合法的生产演练特批变更工单号 (须以 CHG- 前缀开头)")

        if maintenance_window_start is None or maintenance_window_end is None:
            prod_violations.append("生产演练必须指定明确的特批演练维护窗口 (起止时间)")
        else:
            if now < maintenance_window_start or now > maintenance_window_end:
                prod_violations.append(
                    f"当前时间 ({now.strftime('%Y-%m-%d %H:%M:%S')}) 不在特批演练维护窗口内 "
                    f"({maintenance_window_start.strftime('%Y-%m-%d %H:%M:%S')} ~ {maintenance_window_end.strftime('%Y-%m-%d %H:%M:%S')})"
                )

        if is_prod and fault_type == "PAYLOAD_CORRUPTION":
            prod_violations.append("生产环境绝对严禁注入载荷篡改算子 (PAYLOAD_CORRUPTION)，存在脏数据污染风险")
        if not is_valid_safety_token(safety_token):
            prod_violations.append("生产演练安全令牌 (Safety Token) 缺失或签名无效")

        if prod_violations:
            return ChaosSafetyGuardVerdict(
                verdict_id=verdict_id,
                is_allowed=False,
                action=SafetyVerdictAction.BLOCKED_PROD_UNAUTHORIZED,
                environment=environment,
                target_service=target_service,
                block_reasons=prod_violations,
                safety_rule_applied="PRODUCTION_ENVIRONMENT_QUARANTINE_RULE",
            )

    # 4. 全部安全策略校验通过
    return ChaosSafetyGuardVerdict(
        verdict_id=verdict_id,
        is_allowed=True,
        action=SafetyVerdictAction.ALLOW_SAFE,
        environment=environment,
        target_service=target_service,
        block_reasons=[],
        safety_rule_applied="ALL_SAFETY_GUARDS_PASSED",
    )
