"""缺陷 SLA 超时预警与升级看门狗服务 (T2.3)

针对各级严重度缺陷建立刚性解决时效契约与动态升级看门狗机制:
1. 分级 SLA 时效契约模型 (DefectSLAPolicy: P0 2h响应/24h解决, P1 4h响应/48h解决);
2. 动态履约健康状态判定 (SLAComplianceStatus: 正常健康、临期告急、击穿超时、及时履约);
3. 自动多级升级与发布阻断 (SLAEscalationAction: 黄色预警、升级主管、P0超时强阻断发版);
4. 综合 SLA 履约看板报表输出 (DefectSLAWatchdogBatchReport & DefectSLAEvaluationResult)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DefectSeverity(str, enum.Enum):
    P0_BLOCKING = "P0_BLOCKING"  # 核心阻塞级 (支付/资损/核心业务中断)
    P1_CRITICAL = "P1_CRITICAL"  # 严重级 (次核心流程受阻)
    P2_MAJOR = "P2_MAJOR"  # 一般级 (常规业务异常)
    P3_MINOR = "P3_MINOR"  # 轻微级 (文案/轻微样式)


class SLAComplianceStatus(str, enum.Enum):
    HEALTHY_ON_TRACK = "HEALTHY_ON_TRACK"  # 正常健康推进中 (消耗时限 <= 70%)
    WARNING_NEAR_BREACH = "WARNING_NEAR_BREACH"  # 临期告急预警 (消耗时限 > 70% 且未超时)
    BREACHED_TIMEOUT = "BREACHED_TIMEOUT"  # 击穿超时 (严重超期)
    RESOLVED_IN_TIME = "RESOLVED_IN_TIME"  # 及时履约完成 (在规定时限内已关闭)


class SLAEscalationAction(str, enum.Enum):
    NO_ACTION = "NO_ACTION"  # 正常推进无需动作
    SEND_YELLOW_WARNING = "SEND_YELLOW_WARNING"  # 发送黄色告急预警通知当前处理人
    AUTO_ESCALATE_TO_LEAD = "AUTO_ESCALATE_TO_LEAD"  # 响应超时，自动升级指派至架构师与技术主管
    EMERGENCY_RELEASE_BLOCK = "EMERGENCY_RELEASE_BLOCK"  # P0 缺陷解决超时，触发上线发布强阻断！


@dataclass
class SLATargetContract:
    max_response_hours: float
    max_resolution_hours: float


@dataclass
class DefectSLAPolicy:
    policy_id: str = "policy_enterprise_sla"
    contracts: Dict[DefectSeverity, SLATargetContract] = field(
        default_factory=lambda: {
            DefectSeverity.P0_BLOCKING: SLATargetContract(max_response_hours=2.0, max_resolution_hours=24.0),
            DefectSeverity.P1_CRITICAL: SLATargetContract(max_response_hours=4.0, max_resolution_hours=48.0),
            DefectSeverity.P2_MAJOR: SLATargetContract(max_response_hours=12.0, max_resolution_hours=72.0),
            DefectSeverity.P3_MINOR: SLATargetContract(max_response_hours=24.0, max_resolution_hours=168.0),
        }
    )


@dataclass
class DefectSLATrackingItem:
    defect_id: str
    title: str
    severity: DefectSeverity
    status: str  # OPEN | IN_PROGRESS | RESOLVED | CLOSED
    created_at: datetime
    current_assignee: str
    target_service: str = "core-service"
    first_responded_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    escalated_to: Optional[str] = None


@dataclass
class DefectSLAEvaluationResult:
    tracking_id: str
    defect_id: str
    severity: DefectSeverity
    compliance_status: SLAComplianceStatus
    escalation_action: SLAEscalationAction
    elapsed_hours: float
    max_allowed_resolution_hours: float
    remaining_hours: float
    is_release_blocked: bool
    escalation_notice: str
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tracking_id": self.tracking_id,
            "defect_id": self.defect_id,
            "severity": self.severity.value,
            "compliance_status": self.compliance_status.value,
            "escalation_action": self.escalation_action.value,
            "elapsed_hours": round(self.elapsed_hours, 1),
            "max_allowed_resolution_hours": round(self.max_allowed_resolution_hours, 1),
            "remaining_hours": round(self.remaining_hours, 1),
            "is_release_blocked": self.is_release_blocked,
            "escalation_notice": self.escalation_notice,
            "evaluated_at": self.evaluated_at,
        }


@dataclass
class DefectSLAWatchdogBatchReport:
    report_id: str
    total_tracked_defects: int
    healthy_count: int
    warning_count: int
    breached_count: int
    overall_sla_compliance_rate_pct: float
    evaluations: List[DefectSLAEvaluationResult]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_tracked_defects": self.total_tracked_defects,
            "healthy_count": self.healthy_count,
            "warning_count": self.warning_count,
            "breached_count": self.breached_count,
            "overall_sla_compliance_rate_pct": round(self.overall_sla_compliance_rate_pct, 1),
            "evaluations": [e.to_dict() for e in self.evaluations],
            "generated_at": self.generated_at,
        }


def evaluate_defect_sla(
    item: DefectSLATrackingItem,
    policy: Optional[DefectSLAPolicy] = None,
    current_time: Optional[datetime] = None,
) -> DefectSLAEvaluationResult:
    """深度评估单项缺陷的解决 SLA 履约健康度并计算看门狗升级动作"""
    tracking_id = f"sla_{uuid.uuid4().hex[:10]}"
    pol = policy or DefectSLAPolicy()
    contract = pol.contracts.get(item.severity, SLATargetContract(24.0, 72.0))
    now = current_time or datetime.now(timezone.utc)

    # 1. 如果已解决
    if item.status in ("RESOLVED", "CLOSED"):
        end_t = item.resolved_at or now
        total_time = (end_t - item.created_at).total_seconds() / 3600.0
        is_in_time = total_time <= contract.max_resolution_hours
        status = SLAComplianceStatus.RESOLVED_IN_TIME if is_in_time else SLAComplianceStatus.BREACHED_TIMEOUT
        action = SLAEscalationAction.NO_ACTION
        notice = f"缺陷已闭环，总耗时 {round(total_time, 1)}h (SLA限制: {contract.max_resolution_hours}h)"
        return DefectSLAEvaluationResult(
            tracking_id=tracking_id,
            defect_id=item.defect_id,
            severity=item.severity,
            compliance_status=status,
            escalation_action=action,
            elapsed_hours=total_time,
            max_allowed_resolution_hours=contract.max_resolution_hours,
            remaining_hours=0.0,
            is_release_blocked=False,
            escalation_notice=notice,
        )

    # 2. 未解决，实时计算消耗时间
    elapsed_hours = (now - item.created_at).total_seconds() / 3600.0
    remaining_hours = contract.max_resolution_hours - elapsed_hours

    # 3. 响应 SLA 检查
    resp_hours = (
        (item.first_responded_at - item.created_at).total_seconds() / 3600.0
        if item.first_responded_at
        else elapsed_hours
    )
    response_breached = (item.first_responded_at is None and elapsed_hours > contract.max_response_hours) or (
        item.first_responded_at and resp_hours > contract.max_response_hours
    )

    is_blocked = False
    action = SLAEscalationAction.NO_ACTION

    if remaining_hours <= 0:
        # 严重超时击穿
        status = SLAComplianceStatus.BREACHED_TIMEOUT
        if item.severity == DefectSeverity.P0_BLOCKING:
            action = SLAEscalationAction.EMERGENCY_RELEASE_BLOCK
            is_blocked = True
            notice = f"【致命阻断】P0 阻塞级缺陷已超时击穿 {round(abs(remaining_hours), 1)}h！看门狗已启动上线发布强阻断拦截！"
        else:
            action = SLAEscalationAction.AUTO_ESCALATE_TO_LEAD
            notice = f"【超时升级】缺陷已超时解决 {round(abs(remaining_hours), 1)}h，看门狗自动升级指派至领域架构主管。"
    elif remaining_hours <= contract.max_resolution_hours * 0.3:
        # 临期告急预警 (剩余时间 < 30%)
        status = SLAComplianceStatus.WARNING_NEAR_BREACH
        action = SLAEscalationAction.SEND_YELLOW_WARNING
        notice = f"【临期预警】距离解决 SLA 截止仅剩 {round(remaining_hours, 1)}h，请加快推进排查。"
    else:
        # 正常进行中
        status = SLAComplianceStatus.HEALTHY_ON_TRACK
        if response_breached and item.first_responded_at is None:
            action = SLAEscalationAction.AUTO_ESCALATE_TO_LEAD
            notice = f"响应超时 (已超 {round(elapsed_hours - contract.max_response_hours, 1)}h 无人认领)，看门狗自动升级指派主管。"
        else:
            action = SLAEscalationAction.NO_ACTION
            notice = f"SLA 推进正常，剩余 {round(remaining_hours, 1)}h。"

    return DefectSLAEvaluationResult(
        tracking_id=tracking_id,
        defect_id=item.defect_id,
        severity=item.severity,
        compliance_status=status,
        escalation_action=action,
        elapsed_hours=elapsed_hours,
        max_allowed_resolution_hours=contract.max_resolution_hours,
        remaining_hours=max(0.0, remaining_hours),
        is_release_blocked=is_blocked,
        escalation_notice=notice,
    )


def batch_evaluate_defects_sla(
    items: List[DefectSLATrackingItem],
    policy: Optional[DefectSLAPolicy] = None,
    current_time: Optional[datetime] = None,
) -> DefectSLAWatchdogBatchReport:
    """批量评估缺陷看板 SLA 履约健康度"""
    report_id = f"sla_rep_{uuid.uuid4().hex[:10]}"
    evals: List[DefectSLAEvaluationResult] = []

    for item in items:
        evals.append(evaluate_defect_sla(item, policy=policy, current_time=current_time))

    healthy = sum(
        1
        for e in evals
        if e.compliance_status in (SLAComplianceStatus.HEALTHY_ON_TRACK, SLAComplianceStatus.RESOLVED_IN_TIME)
    )
    warning = sum(1 for e in evals if e.compliance_status == SLAComplianceStatus.WARNING_NEAR_BREACH)
    breached = sum(1 for e in evals if e.compliance_status == SLAComplianceStatus.BREACHED_TIMEOUT)

    tot = len(evals)
    compliance_rate = (healthy / tot * 100.0) if tot > 0 else 100.0

    return DefectSLAWatchdogBatchReport(
        report_id=report_id,
        total_tracked_defects=tot,
        healthy_count=healthy,
        warning_count=warning,
        breached_count=breached,
        overall_sla_compliance_rate_pct=compliance_rate,
        evaluations=evals,
    )
