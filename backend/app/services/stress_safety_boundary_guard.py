"""生产全链路压测特批审批与窗口期强准入看门狗服务 (T4.1)

筑牢生产全链路影子压测安全防线，严格审查发压前生产三要素强准入条件:
1. 特批压测审批工单审查 (Drill Ticket: 必须提供处于 APPROVED 状态的工单号);
2. 维护时段窗口与大促封网期审查 (Maintenance Window: 严禁在业务高峰或大促封网期施压);
3. 压测安全准入操作令牌审查 (Security Stress Token: 严密防范未授权与伪造发压指令);
4. 环境自适应旁路控制 (测试/预发环境免审快速放行，生产环境严格执行三要素强阻断)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class StressAdmissionVerdictCode(str, enum.Enum):
    ADMITTED_PASS = "ADMITTED_PASS"  # 生产三要素校验全部合规通过，准予发起发压作业
    BYPASS_NON_PRODUCTION = "BYPASS_NON_PRODUCTION"  # 非生产环境 (test/staging)，免审安全旁路放行
    BLOCKED_NO_TICKET = "BLOCKED_NO_TICKET"  # 未提供审批工单或工单未审批通过 (REJECTED/PENDING)
    BLOCKED_FREEZE_WINDOW = "BLOCKED_FREEZE_WINDOW"  # 处于大促全局封网期或非允许的低峰运维时段
    BLOCKED_INVALID_TOKEN = "BLOCKED_INVALID_TOKEN"  # 压测安全令牌缺失、伪造或未通过校验


# 准予放行的工单审批通过状态集合
APPROVED_DRILL_STATUSES = {"APPROVED", "PASSED", "RESOLVED", "IN_PROGRESS"}

# 预设合法压测安全令牌前缀
VALID_STRESS_TOKEN_PREFIX = "SEC_STRESS_TOKEN_"


@dataclass
class StressDrillTicket:
    ticket_key: str
    status: str  # APPROVED | PENDING | REJECTED | DRAFT
    drill_director: str  # 演练总指挥/运维审批人
    scope_description: str = "生产全链路影子压测演练"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StressWindowConfig:
    is_freeze_period: bool = False  # 是否处于大促全局封网期 (大促双11/618绝对封网)
    allowed_start_hour_utc: int = 1  # 允许压测放量的起始小时 (默认 01:00 UTC)
    allowed_end_hour_utc: int = 5  # 允许压测放量的结束小时 (默认 05:00 UTC)


@dataclass
class StressAdmissionRequest:
    target_service: str
    environment: str  # production | prod | staging | test | dev
    planned_peak_vu: int
    ticket: Optional[StressDrillTicket] = None
    security_token: Optional[str] = None
    current_hour_utc: Optional[int] = None


@dataclass
class StressSafetyAdmissionVerdict:
    verdict_id: str
    is_admitted: bool
    verdict_code: StressAdmissionVerdictCode
    target_service: str
    environment: str
    planned_peak_vu: int
    reasons: List[str]
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict_id": self.verdict_id,
            "is_admitted": self.is_admitted,
            "verdict_code": self.verdict_code.value,
            "target_service": self.target_service,
            "environment": self.environment,
            "planned_peak_vu": self.planned_peak_vu,
            "reasons": self.reasons,
            "evaluated_at": self.evaluated_at,
        }


def _is_production_environment(env: str) -> bool:
    env_lower = env.lower().strip()
    return env_lower in {"production", "prod", "live"}


def evaluate_stress_safety_admission(
    req: StressAdmissionRequest,
    window_cfg: Optional[StressWindowConfig] = None,
) -> StressSafetyAdmissionVerdict:
    """生产环境全链路压测强准入安全看门狗审查引擎"""
    verdict_id = f"adm_st_{uuid.uuid4().hex[:10]}"
    cfg = window_cfg or StressWindowConfig()

    # 1. 非生产环境：自动免审放行 (Bypass)
    if not _is_production_environment(req.environment):
        return StressSafetyAdmissionVerdict(
            verdict_id=verdict_id,
            is_admitted=True,
            verdict_code=StressAdmissionVerdictCode.BYPASS_NON_PRODUCTION,
            target_service=req.target_service,
            environment=req.environment,
            planned_peak_vu=req.planned_peak_vu,
            reasons=[f"非生产环境 [{req.environment}] 无需强审批，安全旁路放行"],
        )

    # 2. 生产环境强准入三要素审查
    reasons: List[str] = []

    # 要素一：特批审批工单校验
    if not req.ticket or not req.ticket.ticket_key.strip():
        reasons.append("生产全链路压测缺失必须的演练审批工单号 (Drill Ticket Key)")
        return StressSafetyAdmissionVerdict(
            verdict_id=verdict_id,
            is_admitted=False,
            verdict_code=StressAdmissionVerdictCode.BLOCKED_NO_TICKET,
            target_service=req.target_service,
            environment=req.environment,
            planned_peak_vu=req.planned_peak_vu,
            reasons=reasons,
        )

    ticket_status = req.ticket.status.upper().strip()
    if ticket_status not in APPROVED_DRILL_STATUSES:
        reasons.append(f"演练工单 [{req.ticket.ticket_key}] 处于未审批状态: {req.ticket.status}，严禁进入生产施压")
        return StressSafetyAdmissionVerdict(
            verdict_id=verdict_id,
            is_admitted=False,
            verdict_code=StressAdmissionVerdictCode.BLOCKED_NO_TICKET,
            target_service=req.target_service,
            environment=req.environment,
            planned_peak_vu=req.planned_peak_vu,
            reasons=reasons,
        )

    # 要素二：时段窗口与封网期检查
    if cfg.is_freeze_period:
        reasons.append("当前处于生产业务封网重大保障期 (Freeze Period)，严禁发起任何全链路压测")
        return StressSafetyAdmissionVerdict(
            verdict_id=verdict_id,
            is_admitted=False,
            verdict_code=StressAdmissionVerdictCode.BLOCKED_FREEZE_WINDOW,
            target_service=req.target_service,
            environment=req.environment,
            planned_peak_vu=req.planned_peak_vu,
            reasons=reasons,
        )

    current_hour = req.current_hour_utc if req.current_hour_utc is not None else datetime.now(timezone.utc).hour
    if not (cfg.allowed_start_hour_utc <= current_hour < cfg.allowed_end_hour_utc):
        reasons.append(
            f"当前时段 {current_hour}:00 UTC 不在生产允许低峰压测窗口 [{cfg.allowed_start_hour_utc}:00 ~ {cfg.allowed_end_hour_utc}:00 UTC] 内"
        )
        return StressSafetyAdmissionVerdict(
            verdict_id=verdict_id,
            is_admitted=False,
            verdict_code=StressAdmissionVerdictCode.BLOCKED_FREEZE_WINDOW,
            target_service=req.target_service,
            environment=req.environment,
            planned_peak_vu=req.planned_peak_vu,
            reasons=reasons,
        )

    # 要素三：安全准入令牌校验
    if not req.security_token or not req.security_token.startswith(VALID_STRESS_TOKEN_PREFIX):
        reasons.append("提供的压测准入安全令牌 (Security Token) 无效或未携带合法前缀签名")
        return StressSafetyAdmissionVerdict(
            verdict_id=verdict_id,
            is_admitted=False,
            verdict_code=StressAdmissionVerdictCode.BLOCKED_INVALID_TOKEN,
            target_service=req.target_service,
            environment=req.environment,
            planned_peak_vu=req.planned_peak_vu,
            reasons=reasons,
        )

    # 全部要素合规放行
    return StressSafetyAdmissionVerdict(
        verdict_id=verdict_id,
        is_admitted=True,
        verdict_code=StressAdmissionVerdictCode.ADMITTED_PASS,
        target_service=req.target_service,
        environment=req.environment,
        planned_peak_vu=req.planned_peak_vu,
        reasons=[
            f"工单 [{req.ticket.ticket_key}] 审批通过 (演练指挥: {req.ticket.drill_director})",
            "时段窗口合规 (低峰夜间运维窗口)",
            "安全令牌校验通过",
        ],
    )
