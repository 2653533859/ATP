"""生产全链路压测安全审计与爆炸半径评估器 (T4.2)。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class BlastRadiusTier(str, Enum):
    """故障潜在爆炸半径分级。"""

    TIER_1_ISOLATED = "TIER_1_ISOLATED"  # 局域可控 (仅限沙箱容器，零溢出)
    TIER_2_CELL_BOUND = "TIER_2_CELL_BOUND"  # 单元受限 (限定在单个可用区，跨可用区隔离)
    TIER_3_SHARED_PERIPHERAL = "TIER_3_SHARED_PERIPHERAL"  # 涉及共享外围 (存在共享 MQ/Redis 争用)
    TIER_4_UNCONTROLLED_GLOBAL = "TIER_4_UNCONTROLLED_GLOBAL"  # 全局失控高危 (严禁上线压测)


class StressSafetyVerdict(str, Enum):
    """压测安全准入裁决结论。"""

    PASS_READY_FOR_STRESS = "PASS_READY_FOR_STRESS"  # 准入通过 (可安全发起全链路压测)
    CAUTION_MONITORED = "CAUTION_MONITORED"  # 有条件放行 (需 SRE 实时密切监控)
    BLOCKED_HIGH_BLAST_RADIUS = "BLOCKED_HIGH_BLAST_RADIUS"  # 严重阻断 (一票否决禁止上线压测)


@dataclass
class SafetyCheckItem:
    """单项安全防护准入检查。"""

    check_name: str
    is_passed: bool
    risk_weight: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_name": self.check_name,
            "is_passed": self.is_passed,
            "risk_weight": self.risk_weight,
            "description": self.description,
        }


@dataclass
class StressBlastRadiusReport:
    """压测爆炸半径与安全合规全景报告。"""

    report_id: str
    drill_id: str
    blast_radius_tier: BlastRadiusTier
    safety_verdict: StressSafetyVerdict
    safety_score_pct: float
    is_stress_approved: bool
    audit_tamper_evident_fingerprint: str  # 64 位 SHA-256 防篡改验签指纹
    safety_checks: list[SafetyCheckItem]
    emergency_rollback_procedures: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "drill_id": self.drill_id,
            "blast_radius_tier": self.blast_radius_tier.value,
            "safety_verdict": self.safety_verdict.value,
            "safety_score_pct": round(self.safety_score_pct, 1),
            "is_stress_approved": self.is_stress_approved,
            "audit_tamper_evident_fingerprint": self.audit_tamper_evident_fingerprint,
            "safety_checks": [c.to_dict() for c in self.safety_checks],
            "emergency_rollback_procedures": self.emergency_rollback_procedures,
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告存储
_BLAST_RADIUS_REPORTS: dict[str, StressBlastRadiusReport] = {}


def clear_blast_radius_store() -> None:
    """清空爆炸半径报告仓库 (单测专用)。"""
    _BLAST_RADIUS_REPORTS.clear()


def evaluate_stress_blast_radius_safety(
    drill_id: str,
    target_services: list[str],
    shadow_traffic_isolated: bool,
    shadow_tables_ready: bool,
    external_bypasses_ready: bool,
    circuit_breaker_active: bool,
    estimated_max_qps: float = 2000.0,
    participating_cell_ids: list[str] | None = None,
) -> StressBlastRadiusReport:
    """全息评估生产全链路压测的潜在爆炸半径与安全准入资质，生成防篡改指纹。"""
    participating_cell_ids = participating_cell_ids or ["cell_east_01"]

    checks: list[SafetyCheckItem] = [
        SafetyCheckItem(
            check_name="全链路影子流量染色标 100% 透传隔离",
            is_passed=shadow_traffic_isolated,
            risk_weight=30.0,
            description="保证 HTTP Header、gRPC 与 MQ 消息头携带影子标，严禁未染色流量穿透。",
        ),
        SafetyCheckItem(
            check_name="影子数据库与影子表防污染 100% 映射就绪",
            is_passed=shadow_tables_ready,
            risk_weight=30.0,
            description="写操作自动路由至影子库表，无未配置生产表裸写风险。",
        ),
        SafetyCheckItem(
            check_name="外部高危依赖 (短信/支付) 旁路 Mock/Drop 就绪",
            is_passed=external_bypasses_ready,
            risk_weight=20.0,
            description="对第三方支付网关、真实用户手机短信开启强制静默丢弃或 Mock 假回执。",
        ),
        SafetyCheckItem(
            check_name="毫秒级防雪崩自适应熔断保护大脑在线处于就绪状态",
            is_passed=circuit_breaker_active,
            risk_weight=20.0,
            description="当下游基础设施容量超过 85% 时，具备毫秒级阶梯限流与自动中止压测能力。",
        ),
    ]

    passed_weight = sum(c.risk_weight for c in checks if c.is_passed)
    total_weight = sum(c.risk_weight for c in checks)
    safety_score = (passed_weight / total_weight) * 100.0

    # 爆炸半径等级与准入裁决
    if not shadow_tables_ready or not shadow_traffic_isolated:
        tier = BlastRadiusTier.TIER_4_UNCONTROLLED_GLOBAL
        verdict = StressSafetyVerdict.BLOCKED_HIGH_BLAST_RADIUS
        is_approved = False
    elif not external_bypasses_ready:
        tier = BlastRadiusTier.TIER_3_SHARED_PERIPHERAL
        verdict = StressSafetyVerdict.BLOCKED_HIGH_BLAST_RADIUS
        is_approved = False
    elif not circuit_breaker_active:
        tier = BlastRadiusTier.TIER_2_CELL_BOUND
        verdict = StressSafetyVerdict.CAUTION_MONITORED
        is_approved = False
    else:
        tier = (
            BlastRadiusTier.TIER_1_ISOLATED if len(participating_cell_ids) <= 1 else BlastRadiusTier.TIER_2_CELL_BOUND
        )
        verdict = StressSafetyVerdict.PASS_READY_FOR_STRESS
        is_approved = True

    procedures: list[str] = [
        "应急一键阻断指令: POST /api/v1/stress/bottleneck-guardian/circuit-breaker/evaluate (触发强制 ABORT)。",
        "压测执行机集群一键急刹: 停止所有压测 Pod 进程并排空剩余线程队列。",
        "数据隔离自愈检查: 检查生产核心表是否有非预期自增 ID 跳跃或脏数据渗入。",
    ]

    now = datetime.now(timezone.utc)
    # 计算 SHA-256 防篡改审计指纹
    fingerprint_raw = json.dumps(
        {
            "drill_id": drill_id,
            "score": round(safety_score, 1),
            "tier": tier.value,
            "verdict": verdict.value,
            "estimated_max_qps": round(estimated_max_qps, 1),
            "target_services": sorted(target_services),
            "timestamp": now.isoformat(),
        },
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(fingerprint_raw.encode("utf-8")).hexdigest()

    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", drill_id)[:16]
    report_id = f"blast_rpt_{safe_name}_{int(now.timestamp())}"

    report = StressBlastRadiusReport(
        report_id=report_id,
        drill_id=drill_id,
        blast_radius_tier=tier,
        safety_verdict=verdict,
        safety_score_pct=safety_score,
        is_stress_approved=is_approved,
        audit_tamper_evident_fingerprint=fingerprint,
        safety_checks=checks,
        emergency_rollback_procedures=procedures,
        created_at=now,
    )

    _BLAST_RADIUS_REPORTS[report_id] = report
    return report


def get_blast_radius_report(report_id: str) -> StressBlastRadiusReport | None:
    """按 ID 查询爆炸半径报告。"""
    return _BLAST_RADIUS_REPORTS.get(report_id)


def list_blast_radius_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史爆炸半径报告列表。"""
    reports = list(reversed(list(_BLAST_RADIUS_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
