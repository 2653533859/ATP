"""自动化发版准入阻断裁决器 (Go/No-Go) 与豁免流转网关 (T4.2)。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ReleaseVerdict(str, Enum):
    """发版准入裁决结果。"""

    GO = "GO"  # 准入通过，可直接发布
    CAUTION = "CAUTION"  # 警示放行，需灰度观察
    NO_GO = "NO_GO"  # 严苛阻断，禁止上线发布
    WAIVED_GO = "WAIVED_GO"  # 经过特批风险豁免，破例放行


@dataclass
class ReleaseWaiverInfo:
    """特批风险豁免签署信息。"""

    approver: str
    waiver_reason: str
    rollback_plan: str
    waived_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "approver": self.approver,
            "waiver_reason": self.waiver_reason,
            "rollback_plan": self.rollback_plan,
            "waived_at": self.waived_at,
        }


@dataclass
class ReleaseGateVerdictRecord:
    """发版门禁准入裁决记录。"""

    release_id: str
    target_version: str
    verdict: ReleaseVerdict
    quality_score: float
    blocking_reasons: list[str]
    warning_reasons: list[str]
    is_waived: bool = False
    waiver_info: ReleaseWaiverInfo | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "target_version": self.target_version,
            "verdict": self.verdict.value,
            "quality_score": round(self.quality_score, 1),
            "blocking_reasons": self.blocking_reasons,
            "warning_reasons": self.warning_reasons,
            "is_waived": self.is_waived,
            "waiver_info": self.waiver_info.to_dict() if self.waiver_info else None,
            "created_at": self.created_at.isoformat(),
        }


# 全局准入裁决记录存储
_RELEASE_GATE_RECORDS: dict[str, ReleaseGateVerdictRecord] = {}


def clear_release_gate_store() -> None:
    """清空发版准入仓库（单测专用）。"""
    _RELEASE_GATE_RECORDS.clear()


def evaluate_release_gate(
    target_version: str,
    quality_score: float,
    p0_defects_count: int = 0,
    p1_defects_count: int = 0,
    critical_security_flaws_count: int = 0,
    test_pass_rate_pct: float = 100.0,
) -> ReleaseGateVerdictRecord:
    """评估发版质量门禁指标，输出客观严谨的准入裁决。"""
    blocking_reasons: list[str] = []
    warning_reasons: list[str] = []

    # 1. 阻断级卡点审查 (NO_GO)
    if p0_defects_count > 0:
        blocking_reasons.append(f"存在 {p0_defects_count} 个未修复的 P0 核心阻塞级缺陷")
    if critical_security_flaws_count > 0:
        blocking_reasons.append(f"检测到 {critical_security_flaws_count} 个 CRITICAL 级安全合规漏洞或特权容器逃逸隐患")
    if quality_score < 70.0:
        blocking_reasons.append(f"多维质量健康综合评分 ({round(quality_score, 1)}) 低于 70.0 准入门槛")
    if test_pass_rate_pct < 95.0:
        blocking_reasons.append(f"自动化测试通过率 ({round(test_pass_rate_pct, 1)}%) 严重低于 95.0% 门禁基准")

    # 2. 警示级卡点审查 (CAUTION)
    if not blocking_reasons:
        if p1_defects_count > 0:
            warning_reasons.append(f"存在 {p1_defects_count} 个 P1 级缺陷待跟进")
        if quality_score < 85.0:
            warning_reasons.append(f"综合质量健康得分 ({round(quality_score, 1)}) 处于 70~85 预警区间")
        if test_pass_rate_pct < 100.0:
            warning_reasons.append(f"测试通过率为 {round(test_pass_rate_pct, 1)}%，存在非阻塞失败用例")

    # 判定最终结论
    if blocking_reasons:
        verdict = ReleaseVerdict.NO_GO
    elif warning_reasons:
        verdict = ReleaseVerdict.CAUTION
    else:
        verdict = ReleaseVerdict.GO

    now = datetime.now(timezone.utc)
    clean_ver = target_version.replace(".", "_")
    release_id = f"rel_{clean_ver}_{uuid.uuid4().hex[:6]}"

    record = ReleaseGateVerdictRecord(
        release_id=release_id,
        target_version=target_version,
        verdict=verdict,
        quality_score=quality_score,
        blocking_reasons=blocking_reasons,
        warning_reasons=warning_reasons,
        is_waived=False,
        waiver_info=None,
        created_at=now,
    )
    _RELEASE_GATE_RECORDS[release_id] = record
    return record


def grant_risk_waiver(
    release_id: str,
    approver: str,
    waiver_reason: str,
    rollback_plan: str,
) -> dict[str, Any]:
    """对阻断的 NO_GO 发版申请特批签署风险豁免。"""
    record = _RELEASE_GATE_RECORDS.get(release_id)
    if not record:
        return {"success": False, "message": f"发布记录 [{release_id}] 不存在"}

    if record.verdict not in (ReleaseVerdict.NO_GO, ReleaseVerdict.CAUTION):
        return {"success": False, "message": f"当前状态 [{record.verdict.value}] 无需申请风险豁免"}

    now_str = datetime.now(timezone.utc).isoformat()
    waiver = ReleaseWaiverInfo(
        approver=approver,
        waiver_reason=waiver_reason,
        rollback_plan=rollback_plan,
        waived_at=now_str,
    )

    record.is_waived = True
    record.waiver_info = waiver
    record.verdict = ReleaseVerdict.WAIVED_GO

    return {
        "success": True,
        "message": f"版本 [{record.target_version}] 已由架构师 [{approver}] 成功签署风险特批豁免，状态流转为 WAIVED_GO。",
        "record": record.to_dict(),
    }


def revoke_risk_waiver(release_id: str) -> dict[str, Any]:
    """撤销已签署的发版风险特批豁免。"""
    record = _RELEASE_GATE_RECORDS.get(release_id)
    if not record:
        return {"success": False, "message": f"发布记录 [{release_id}] 不存在"}

    if not record.is_waived:
        return {"success": False, "message": "该发版记录未处于豁免状态"}

    record.is_waived = False
    record.waiver_info = None
    record.verdict = ReleaseVerdict.NO_GO

    return {
        "success": True,
        "message": f"版本 [{record.target_version}] 的特批风险豁免已被撤销，重新恢复为 NO_GO 阻断状态。",
        "record": record.to_dict(),
    }


def get_release_gate_record(release_id: str) -> ReleaseGateVerdictRecord | None:
    """按 ID 查询发版准入记录。"""
    return _RELEASE_GATE_RECORDS.get(release_id)


def list_release_gate_records(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史发版准入记录列表。"""
    records = list(reversed(list(_RELEASE_GATE_RECORDS.values())))
    return [r.to_dict() for r in records[:limit]]
