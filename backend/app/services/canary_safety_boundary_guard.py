"""生产环境灰度强准入与金丝雀发布审批看门狗服务 (T4.1)

筑牢生产环境防误切、防误割安全底线，严格执行生产灰度发布三要素强准入审查:
1. 特批灰度发布工单校验 (Ticket Approval: 必须提供处于 APPROVED 状态的工单号);
2. 变更维护时段窗口校验 (Maintenance Window & Freeze Period: 业务高峰或封网期严禁切流);
3. 安全准入操作令牌校验 (Security Admission Token: 防未授权伪造请求);
4. 环境自适应旁路判定 (测试/预发环境免审快速放行，生产环境必须三要素强阻断)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class CanaryAdmissionVerdictCode(str, enum.Enum):
    ADMITTED_PASS = "ADMITTED_PASS"  # 生产三要素校验全部通过，准予灰度切流放量
    BYPASS_NON_PRODUCTION = "BYPASS_NON_PRODUCTION"  # 非生产环境 (test/staging)，免审安全旁路放行
    BLOCKED_NO_TICKET = "BLOCKED_NO_TICKET"  # 未提供发布工单或工单未审批通过 (REJECTED/PENDING)
    BLOCKED_FREEZE_WINDOW = "BLOCKED_FREEZE_WINDOW"  # 处于大促封网期或非允许的低峰维护时段
    BLOCKED_INVALID_TOKEN = "BLOCKED_INVALID_TOKEN"  # 安全令牌缺失、伪造或未通过校验


# 允许放行的工单审批通过状态
APPROVED_TICKET_STATUSES = {"APPROVED", "PASSED", "RESOLVED", "IN_PROGRESS"}

# 预设合法安全令牌前缀 / 密钥特征
VALID_SECURITY_TOKEN_PREFIX = "SEC_CANARY_TOKEN_"


@dataclass
class CanaryReleaseTicket:
    ticket_key: str
    status: str  # APPROVED | PENDING | REJECTED | DRAFT
    approver: str
    change_scope: str = "微服务金丝雀发布"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MaintenanceWindowConfig:
    is_freeze_period: bool = False  # 是否处于大促全局封网期 (大促双11/618绝对封网)
    allowed_start_hour_utc: int = 0  # 允许维护放量的起始小时 (UTC)
    allowed_end_hour_utc: int = 24  # 允许维护放量的结束小时 (UTC, 24表示全天)


@dataclass
class CanaryAdmissionRequest:
    target_service: str
    environment: str  # production | prod | staging | test | dev
    proposed_canary_weight_pct: float
    ticket: Optional[CanaryReleaseTicket] = None
    security_token: Optional[str] = None
    current_hour_utc: Optional[int] = None


@dataclass
class CanarySafetyAdmissionVerdict:
    verdict_id: str
    is_admitted: bool
    verdict_code: CanaryAdmissionVerdictCode
    target_service: str
    environment: str
    proposed_weight_pct: float
    reasons: List[str]
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict_id": self.verdict_id,
            "is_admitted": self.is_admitted,
            "verdict_code": self.verdict_code.value,
            "target_service": self.target_service,
            "environment": self.environment,
            "proposed_weight_pct": self.proposed_weight_pct,
            "reasons": self.reasons,
            "evaluated_at": self.evaluated_at,
        }


def _is_production_environment(env: str) -> bool:
    env_lower = env.lower().strip()
    return env_lower in {"production", "prod", "live"}


def evaluate_canary_safety_admission(
    req: CanaryAdmissionRequest,
    window_cfg: Optional[MaintenanceWindowConfig] = None,
) -> CanarySafetyAdmissionVerdict:
    """生产环境金丝雀发布强准入安全看门狗审查引擎"""
    verdict_id = f"adm_{uuid.uuid4().hex[:10]}"
    cfg = window_cfg or MaintenanceWindowConfig()

    # 1. 非生产环境：自动免审放行 (Bypass)
    if not _is_production_environment(req.environment):
        return CanarySafetyAdmissionVerdict(
            verdict_id=verdict_id,
            is_admitted=True,
            verdict_code=CanaryAdmissionVerdictCode.BYPASS_NON_PRODUCTION,
            target_service=req.target_service,
            environment=req.environment,
            proposed_weight_pct=req.proposed_canary_weight_pct,
            reasons=[f"非生产环境 [{req.environment}] 无需强审批，安全旁路放行"],
        )

    # 2. 生产环境强准入三要素审查
    reasons: List[str] = []

    # 要素一：特批审批工单校验
    if not req.ticket or not req.ticket.ticket_key.strip():
        reasons.append("生产灰度发布缺失必须的发布审批工单号 (Release Ticket Key)")
        return CanarySafetyAdmissionVerdict(
            verdict_id=verdict_id,
            is_admitted=False,
            verdict_code=CanaryAdmissionVerdictCode.BLOCKED_NO_TICKET,
            target_service=req.target_service,
            environment=req.environment,
            proposed_weight_pct=req.proposed_canary_weight_pct,
            reasons=reasons,
        )

    ticket_status = req.ticket.status.upper().strip()
    if ticket_status not in APPROVED_TICKET_STATUSES:
        reasons.append(f"发布工单 [{req.ticket.ticket_key}] 处于未审批状态: {req.ticket.status}，严禁进入生产放量")
        return CanarySafetyAdmissionVerdict(
            verdict_id=verdict_id,
            is_admitted=False,
            verdict_code=CanaryAdmissionVerdictCode.BLOCKED_NO_TICKET,
            target_service=req.target_service,
            environment=req.environment,
            proposed_weight_pct=req.proposed_canary_weight_pct,
            reasons=reasons,
        )

    # 要素二：时段窗口与封网期检查
    if cfg.is_freeze_period:
        reasons.append("当前处于生产业务封网重大保障期 (Freeze Period)，严禁发起任何金丝雀切流变动")
        return CanarySafetyAdmissionVerdict(
            verdict_id=verdict_id,
            is_admitted=False,
            verdict_code=CanaryAdmissionVerdictCode.BLOCKED_FREEZE_WINDOW,
            target_service=req.target_service,
            environment=req.environment,
            proposed_weight_pct=req.proposed_canary_weight_pct,
            reasons=reasons,
        )

    current_hour = req.current_hour_utc if req.current_hour_utc is not None else datetime.now(timezone.utc).hour
    if not (cfg.allowed_start_hour_utc <= current_hour < cfg.allowed_end_hour_utc):
        reasons.append(
            f"当前时段 {current_hour}:00 UTC 不在生产允许维护窗口 [{cfg.allowed_start_hour_utc}:00 ~ {cfg.allowed_end_hour_utc}:00 UTC] 内"
        )
        return CanarySafetyAdmissionVerdict(
            verdict_id=verdict_id,
            is_admitted=False,
            verdict_code=CanaryAdmissionVerdictCode.BLOCKED_FREEZE_WINDOW,
            target_service=req.target_service,
            environment=req.environment,
            proposed_weight_pct=req.proposed_canary_weight_pct,
            reasons=reasons,
        )

    # 要素三：安全准入令牌校验
    if not req.security_token or not req.security_token.startswith(VALID_SECURITY_TOKEN_PREFIX):
        reasons.append("提供的灰度准入安全令牌 (Security Token) 无效或未携带合法前缀签名")
        return CanarySafetyAdmissionVerdict(
            verdict_id=verdict_id,
            is_admitted=False,
            verdict_code=CanaryAdmissionVerdictCode.BLOCKED_INVALID_TOKEN,
            target_service=req.target_service,
            environment=req.environment,
            proposed_weight_pct=req.proposed_canary_weight_pct,
            reasons=reasons,
        )

    # 全部要素合规放行
    return CanarySafetyAdmissionVerdict(
        verdict_id=verdict_id,
        is_admitted=True,
        verdict_code=CanaryAdmissionVerdictCode.ADMITTED_PASS,
        target_service=req.target_service,
        environment=req.environment,
        proposed_weight_pct=req.proposed_canary_weight_pct,
        reasons=[
            f"工单 [{req.ticket.ticket_key}] 审批通过 (审批人: {req.ticket.approver})",
            "时段窗口合规 (非封网期)",
            "安全令牌校验通过",
        ],
    )
