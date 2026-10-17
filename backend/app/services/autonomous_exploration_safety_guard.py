"""自主探索高危动作防护看门狗服务 (T4.1)

在多模态 VLM 自主探索与意图驱动执行过程中提供实时安全防护与熔断拦截:
1. 高危敏感操作模式库 (账号注销、系统重置、抹除真机、大额转账、修改敏感密码、删库);
2. 动作实时安全评估 (SafetyVerdict: ALLOW | WARN | BLOCK);
3. 风险阻断与熔断保护 (Circuit Breaker: 阻断危险手势向下游设备下发, 会话状态切为 CIRCUIT_BROKEN);
4. 违规事件审计追踪 (SafetyViolationEvent 归档与检索)。
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class RiskCategory(str, enum.Enum):
    ACCOUNT_DESTRUCTION = "ACCOUNT_DESTRUCTION"  # 账号销户与注销
    SYSTEM_PURGE = "SYSTEM_PURGE"  # 恢复出厂设置与设备抹除
    FINANCIAL_RISK = "FINANCIAL_RISK"  # 真实大额扣款与资金解绑
    SECURITY_TAMPERING = "SECURITY_TAMPERING"  # 修改安全凭据与Root提权
    DATABASE_DESTRUCTION = "DATABASE_DESTRUCTION"  # 破坏性SQL执行与删库


class RiskSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SafetyVerdict(str, enum.Enum):
    ALLOW = "ALLOW"  # 安全放行
    WARN = "WARN"  # 警告并记录
    BLOCK = "BLOCK"  # 立即阻断并熔断


@dataclass
class SafetyRule:
    rule_id: str
    category: RiskCategory
    severity: RiskSeverity
    keywords: List[str]
    description: str
    verdict: SafetyVerdict = SafetyVerdict.BLOCK


@dataclass
class SafetyViolationEvent:
    violation_id: str
    session_id: str
    category: RiskCategory
    severity: RiskSeverity
    verdict: SafetyVerdict
    triggered_keyword: str
    target_element_label: str
    action_type: str
    blocked_input: Optional[str]
    explanation: str
    intercepted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 默认内置高危防护规则矩阵
DEFAULT_SAFETY_RULES: List[SafetyRule] = [
    SafetyRule(
        rule_id="RULE_ACC_01",
        category=RiskCategory.ACCOUNT_DESTRUCTION,
        severity=RiskSeverity.CRITICAL,
        keywords=[
            "注销账号",
            "注销账户",
            "注销会员",
            "永久注销",
            "删除账号",
            "关闭账号",
            "deregister",
            "delete account",
        ],
        description="拦截注销会员账号或永久销户操作，防止测试账号与资产丢失",
    ),
    SafetyRule(
        rule_id="RULE_SYS_02",
        category=RiskCategory.SYSTEM_PURGE,
        severity=RiskSeverity.CRITICAL,
        keywords=[
            "恢复出厂设置",
            "抹掉所有内容",
            "抹掉所有数据",
            "格式化手机",
            "清空所有数据",
            "factory reset",
            "erase all",
            "wipe device",
        ],
        description="拦截抹除手机系统与恢复出厂设置操作，保护物理真机资产",
    ),
    SafetyRule(
        rule_id="RULE_FIN_03",
        category=RiskCategory.FINANCIAL_RISK,
        severity=RiskSeverity.HIGH,
        keywords=["解绑银行卡", "立即充值1000", "真实扣款", "大额支付确认", "转出全部余额", "解绑支付托管"],
        description="拦截生产/预发环境中不可逆的大额真实资金流转手势",
    ),
    SafetyRule(
        rule_id="RULE_SEC_04",
        category=RiskCategory.SECURITY_TAMPERING,
        severity=RiskSeverity.HIGH,
        keywords=["修改交易密码", "重置支付密码", "开启开发者Root", "关闭防火墙", "禁用安全认证", "disable security"],
        description="拦截篡改设备核心安全凭据与提权破坏操作",
    ),
    SafetyRule(
        rule_id="RULE_DB_05",
        category=RiskCategory.DATABASE_DESTRUCTION,
        severity=RiskSeverity.CRITICAL,
        keywords=["drop database", "drop table", "truncate table", "delete from", "清空所有业务表", "rm -rf"],
        description="拦截测试工作流执行过程中的破坏性 SQL 删库指令",
    ),
]

_VIOLATION_STORE: Dict[str, SafetyViolationEvent] = {}


def clear_safety_violations() -> None:
    """清空安全违规拦截内存记录（测试夹具使用）"""
    _VIOLATION_STORE.clear()


def evaluate_action_safety(
    session_id: str,
    action_type: str,
    target_element_label: str = "",
    input_text: Optional[str] = None,
    custom_rules: Optional[List[SafetyRule]] = None,
) -> Tuple[SafetyVerdict, Optional[SafetyViolationEvent]]:
    """实时评估待执行动作的安全性，返回审查结论与可能触发的违规阻断事件

    Returns:
        (SafetyVerdict, SafetyViolationEvent | None)
    """
    rules = custom_rules or DEFAULT_SAFETY_RULES

    text_to_inspect = f"{target_element_label} {input_text or ''}".lower()

    for rule in rules:
        for kw in rule.keywords:
            pattern = re.escape(kw.lower())
            if re.search(pattern, text_to_inspect):
                # 命中高危规则
                vid = f"viol_{uuid.uuid4().hex[:12]}"
                event = SafetyViolationEvent(
                    violation_id=vid,
                    session_id=session_id,
                    category=rule.category,
                    severity=rule.severity,
                    verdict=rule.verdict,
                    triggered_keyword=kw,
                    target_element_label=target_element_label,
                    action_type=action_type,
                    blocked_input=input_text,
                    explanation=(
                        f"看门狗拦截: 动作 [{action_type}] 针对控件 [{target_element_label}] 触发了 "
                        f"{rule.category.value} 级别高危规则, 包含敏感词 '{kw}'。规则说明: {rule.description}"
                    ),
                )
                _VIOLATION_STORE[vid] = event
                return rule.verdict, event

    return SafetyVerdict.ALLOW, None


def list_safety_violations(session_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """查询安全违规拦截审计事件列表"""
    events = list(_VIOLATION_STORE.values())
    if session_id:
        events = [e for e in events if e.session_id == session_id]
    events.sort(key=lambda x: x.intercepted_at, reverse=True)
    return [e.to_dict() for e in events[:limit]]
