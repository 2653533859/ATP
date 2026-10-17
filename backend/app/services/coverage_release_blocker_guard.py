"""质量门禁发布强阻断与非合规豁免审批看门狗服务 (T4.1)

在 CI/CD 发布流水线中执行强阻断拦截，防范绕过门禁上线，提供合规审批单豁免通道:
1. 流水线强阻断逻辑 (若增量覆盖率未达标且无特批豁免，直接终止构建发布流程);
2. 紧急线上 Hotfix 豁免审计门禁 (验证特批工单 WAIVER-HOTFIX-*、审批人资质与豁免令牌);
3. 四态阻断裁决结论输出 (ReleaseGuardAction: CONFORMANT 放行、WAIVED 特批放行、BLOCKED 强阻断);
4. 综合看门狗裁决审计记录输出 (ReleaseBlockerGuardVerdict)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.incremental_coverage_gate_evaluator import (
    CoverageGateVerdictAction,
    IncrementalCoverageGateVerdict,
)


class ReleaseGuardAction(str, enum.Enum):
    ALLOW_RELEASE_CONFORMANT = "ALLOW_RELEASE_CONFORMANT"  # 覆盖率指标完全达标，合规放行发布
    ALLOW_RELEASE_WAIVED = "ALLOW_RELEASE_WAIVED"  # 指标未达标，但携带合法合规特批豁免单，受控放行
    BLOCKED_DEFICIT_NO_WAIVER = "BLOCKED_DEFICIT_NO_WAIVER"  # 覆盖率未达标且无审批单，流水线强阻断
    BLOCKED_INVALID_WAIVER = "BLOCKED_INVALID_WAIVER"  # 豁免审批单缺失三要素或签名伪造，安全拦截


# 具备发布豁免审批权限的高级技术专家与架构师白名单
AUTHORIZED_WAIVER_APPROVERS = [
    "chief_architect@atp.io",
    "qa_director@atp.io",
    "sec_officer@atp.io",
    "release_manager@atp.io",
]


@dataclass
class ReleaseBlockerGuardVerdict:
    guard_verdict_id: str
    pipeline_id: str
    environment: str
    is_blocked: bool
    action: ReleaseGuardAction
    reasons: List[str]
    waiver_ticket_id: Optional[str]
    approved_by: Optional[str]
    remediation_plan: List[str]
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "guard_verdict_id": self.guard_verdict_id,
            "pipeline_id": self.pipeline_id,
            "environment": self.environment,
            "is_blocked": self.is_blocked,
            "action": self.action.value,
            "reasons": self.reasons,
            "waiver_ticket_id": self.waiver_ticket_id,
            "approved_by": self.approved_by,
            "remediation_plan": self.remediation_plan,
            "checked_at": self.checked_at,
        }


def is_valid_waiver_token(token: Optional[str]) -> bool:
    """校验合规豁免签名令牌 (须以 ATP-COV-WAIVER- 开头且长度至少 24 位)"""
    if not token:
        return False
    return token.startswith("ATP-COV-WAIVER-") and len(token) >= 24


def enforce_coverage_release_gate(
    pipeline_id: str,
    environment: str,
    gate_verdict: IncrementalCoverageGateVerdict,
    waiver_ticket_id: Optional[str] = None,
    approved_by: Optional[str] = None,
    waiver_token: Optional[str] = None,
    remediation_deadline: Optional[str] = None,
) -> ReleaseBlockerGuardVerdict:
    """执行 CI/CD 流水线发布准入强卡点与豁免合规审批检验"""
    verdict_id = f"grd_{uuid.uuid4().hex[:10]}"
    env_lower = environment.strip().lower()
    is_prod = env_lower in ("prod", "production", "live", "online")

    # 1. 如果覆盖率指标已完全合规放行
    if gate_verdict.is_passed and gate_verdict.action == CoverageGateVerdictAction.PASSED_CONFORMANT:
        return ReleaseBlockerGuardVerdict(
            guard_verdict_id=verdict_id,
            pipeline_id=pipeline_id,
            environment=environment,
            is_blocked=False,
            action=ReleaseGuardAction.ALLOW_RELEASE_CONFORMANT,
            reasons=["增量代码覆盖率与分支指标完全达标，无任何未覆盖高危漏洞，准予放行发布。"],
            waiver_ticket_id=None,
            approved_by=None,
            remediation_plan=[],
        )

    # 2. 如果是条件预警放行 (非生产环境或准入容差)
    if gate_verdict.is_passed and gate_verdict.action == CoverageGateVerdictAction.WARNING_CONDITIONAL and not is_prod:
        return ReleaseBlockerGuardVerdict(
            guard_verdict_id=verdict_id,
            pipeline_id=pipeline_id,
            environment=environment,
            is_blocked=False,
            action=ReleaseGuardAction.ALLOW_RELEASE_CONFORMANT,
            reasons=["处于非生产容差预警区间内，无 P0 阻塞，允许合并。"],
            waiver_ticket_id=None,
            approved_by=None,
            remediation_plan=gate_verdict.remediation_suggestions,
        )

    # 3. 覆盖率不达标：检查是否具备特批合规豁免单 (Emergency Release Waiver)
    if waiver_ticket_id:
        waiver_errors: List[str] = []

        if not waiver_ticket_id.startswith("WAIVER-HOTFIX-"):
            waiver_errors.append("豁免工单编号格式非法 (必须以 WAIVER-HOTFIX- 前缀开头)")

        if not approved_by or approved_by not in AUTHORIZED_WAIVER_APPROVERS:
            waiver_errors.append(f"审批人 [{approved_by}] 无权签发覆盖率发布豁免单，不在专家白名单内")

        if not is_valid_waiver_token(waiver_token):
            waiver_errors.append("豁免签名安全令牌 (Waiver Token) 缺失或长度不足 24 位")

        if not remediation_deadline:
            waiver_errors.append("豁免发布必须承诺严格的限期补测截止时间 (remediation_deadline)")

        if waiver_errors:
            # 携带了豁免单，但校验失败，直接安全阻断
            return ReleaseBlockerGuardVerdict(
                guard_verdict_id=verdict_id,
                pipeline_id=pipeline_id,
                environment=environment,
                is_blocked=True,
                action=ReleaseGuardAction.BLOCKED_INVALID_WAIVER,
                reasons=[f"豁免审批合规校验未通过: {'; '.join(waiver_errors)}"],
                waiver_ticket_id=waiver_ticket_id,
                approved_by=approved_by,
                remediation_plan=gate_verdict.remediation_suggestions,
            )

        # 豁免校验完全通过，特批放行发布
        return ReleaseBlockerGuardVerdict(
            guard_verdict_id=verdict_id,
            pipeline_id=pipeline_id,
            environment=environment,
            is_blocked=False,
            action=ReleaseGuardAction.ALLOW_RELEASE_WAIVED,
            reasons=[
                f"【特批放行】已核验紧急豁免工单 [{waiver_ticket_id}]，审批人: {approved_by}，承诺于 {remediation_deadline} 前全量补齐测试用例。"
            ],
            waiver_ticket_id=waiver_ticket_id,
            approved_by=approved_by,
            remediation_plan=[
                f"限期整改责任人工单: {waiver_ticket_id}",
                f"截止时间: {remediation_deadline}",
                *gate_verdict.remediation_suggestions,
            ],
        )

    # 4. 覆盖率不达标且未携带任何豁免审批单 -> 触发流水线发布强阻断
    block_reasons = [
        f"增量代码覆盖率未达到准入门槛 (实际: {gate_verdict.actual_diff_line_coverage_pct}% < 目标: {gate_verdict.target_min_diff_line_coverage_pct}%)",
        *gate_verdict.breached_rules,
    ]
    return ReleaseBlockerGuardVerdict(
        guard_verdict_id=verdict_id,
        pipeline_id=pipeline_id,
        environment=environment,
        is_blocked=True,
        action=ReleaseGuardAction.BLOCKED_DEFICIT_NO_WAIVER,
        reasons=block_reasons,
        waiver_ticket_id=None,
        approved_by=None,
        remediation_plan=gate_verdict.remediation_suggestions,
    )
