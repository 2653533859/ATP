"""双端一致性评分与兼容性报表引擎服务 (T2.3)

为跨端（iOS vs Android / Web vs Mobile）提供四维加权健康度评分与发布门禁准入裁决:
1. 四维加权一致性评分模型 (控件对齐率 40% + 核心业务覆盖 30% + 文案一致性 20% + 交互兼容度 10%);
2. 双端合规等级评定 (ParityGrade: GRADE_A | GRADE_B | GRADE_C | GRADE_F);
3. 发布门禁准入判定 (Release Gate Verdict: PASS | WARN | BLOCK);
4. 综合审计报表生成与决策建议提炼 (ParityAuditReport)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.parity_alignment_analyzer import (
    AlignmentMatchType,
    ParityAlignmentMatrix,
    ParityScreenTree,
    align_screen_trees,
)
from app.services.parity_gap_detector import (
    ParityDiscrepancyReport,
    ParityGapType,
    detect_parity_gaps,
)


class ParityGrade(str, enum.Enum):
    GRADE_A = "GRADE_A"  # 极佳一致性 (>= 90分)
    GRADE_B = "GRADE_B"  # 合格一致性 (75 ~ 89分)
    GRADE_C = "GRADE_C"  # 风险预警 (60 ~ 74分)
    GRADE_F = "GRADE_F"  # 严重不对等 (< 60分 或 存在核心业务缺失)


class ReleaseGateVerdict(str, enum.Enum):
    PASS = "PASS"  # 准入通过，可直接上线
    WARN = "WARN"  # 附带风险告警放行
    BLOCK = "BLOCK"  # 门禁阻断，禁止上线


@dataclass
class ParityScoreBreakdown:
    control_alignment_score: float  # 满分 100, 权重 40%
    core_business_score: float  # 满分 100, 权重 30%
    text_consistency_score: float  # 满分 100, 权重 20%
    interaction_compatibility_score: float  # 满分 100, 权重 10%
    weighted_composite_score: float  # 综合总分 0.0 ~ 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "control_alignment_score": round(self.control_alignment_score, 2),
            "core_business_score": round(self.core_business_score, 2),
            "text_consistency_score": round(self.text_consistency_score, 2),
            "interaction_compatibility_score": round(self.interaction_compatibility_score, 2),
            "weighted_composite_score": round(self.weighted_composite_score, 2),
        }


@dataclass
class ParityAuditReport:
    report_id: str
    screen_name: str
    source_platform: str
    target_platform: str
    composite_score: float
    grade: ParityGrade
    verdict: ReleaseGateVerdict
    scores: ParityScoreBreakdown
    matrix_summary: Dict[str, Any]
    discrepancy_summary: Dict[str, Any]
    gaps: List[Dict[str, Any]]
    executive_summary: str
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "screen_name": self.screen_name,
            "source_platform": self.source_platform,
            "target_platform": self.target_platform,
            "composite_score": round(self.composite_score, 2),
            "grade": self.grade.value,
            "verdict": self.verdict.value,
            "scores": self.scores.to_dict(),
            "matrix_summary": self.matrix_summary,
            "discrepancy_summary": self.discrepancy_summary,
            "gaps": self.gaps,
            "executive_summary": self.executive_summary,
            "generated_at": self.generated_at,
        }


_PARITY_REPORT_STORE: Dict[str, ParityAuditReport] = {}


def clear_parity_reports() -> None:
    """清空报表内存库（测试使用）"""
    _PARITY_REPORT_STORE.clear()


def calculate_parity_scores(
    matrix: ParityAlignmentMatrix,
    discrepancy_report: ParityDiscrepancyReport,
) -> ParityScoreBreakdown:
    """计算四维加权双端一致性综合得分"""
    # 1. 控件对齐得分 (40%)
    control_score = matrix.overall_alignment_rate * 100.0

    # 2. 核心业务覆盖度得分 (30%): 每个 CRITICAL 扣 35 分，每个 HIGH 扣 15 分
    critical_penalty = discrepancy_report.critical_count * 35.0
    high_penalty = discrepancy_report.high_count * 15.0
    core_score = max(0.0, 100.0 - critical_penalty - high_penalty)

    # 3. 文案一致性得分 (20%): 统计已对齐节点中 EXACT 和 SYNONYM 的比例
    if matrix.aligned_pairs:
        good_text_count = sum(
            1 for p in matrix.aligned_pairs if p.match_type in (AlignmentMatchType.EXACT, AlignmentMatchType.SYNONYM)
        )
        text_score = (good_text_count / len(matrix.aligned_pairs)) * 100.0
    else:
        text_score = 100.0 if (matrix.total_source_nodes == 0 and matrix.total_target_nodes == 0) else 0.0

    # 4. 交互兼容度得分 (10%): 扣除 ACTION_CAPABILITY_MISMATCH
    role_mismatch_count = sum(
        1 for g in discrepancy_report.gaps if g.gap_type == ParityGapType.ACTION_CAPABILITY_MISMATCH
    )
    interaction_score = max(0.0, 100.0 - role_mismatch_count * 25.0)

    # 加权汇总: 40% + 30% + 20% + 10%
    composite = control_score * 0.40 + core_score * 0.30 + text_score * 0.20 + interaction_score * 0.10

    return ParityScoreBreakdown(
        control_alignment_score=control_score,
        core_business_score=core_score,
        text_consistency_score=text_score,
        interaction_compatibility_score=interaction_score,
        weighted_composite_score=composite,
    )


def determine_parity_grade_and_verdict(
    scores: ParityScoreBreakdown,
    discrepancy_report: ParityDiscrepancyReport,
) -> tuple[ParityGrade, ReleaseGateVerdict]:
    """根据得分与高危缺陷裁决一致性等级与发布门禁"""
    comp = scores.weighted_composite_score

    # 若存在 CRITICAL 缺陷，直接一票否决定级为 GRADE_F 并阻断发布
    if discrepancy_report.critical_count > 0:
        return ParityGrade.GRADE_F, ReleaseGateVerdict.BLOCK

    if comp >= 90.0:
        return ParityGrade.GRADE_A, ReleaseGateVerdict.PASS
    elif comp >= 75.0:
        return ParityGrade.GRADE_B, (
            ReleaseGateVerdict.WARN if discrepancy_report.high_count > 0 else ReleaseGateVerdict.PASS
        )
    elif comp >= 60.0:
        return ParityGrade.GRADE_C, ReleaseGateVerdict.WARN
    else:
        return ParityGrade.GRADE_F, ReleaseGateVerdict.BLOCK


def generate_parity_audit_report(
    matrix: ParityAlignmentMatrix,
    discrepancy_report: Optional[ParityDiscrepancyReport] = None,
) -> ParityAuditReport:
    """基于对齐矩阵与差异侦测结果，全量生成双端一致性综合合规审计报表"""
    report_id = f"parrep_{uuid.uuid4().hex[:12]}"

    if not discrepancy_report:
        discrepancy_report = detect_parity_gaps(matrix)

    scores = calculate_parity_scores(matrix, discrepancy_report)
    grade, verdict = determine_parity_grade_and_verdict(scores, discrepancy_report)

    # 生成高管决策层综述建议
    if verdict == ReleaseGateVerdict.BLOCK:
        exec_summary = (
            f"【门禁阻断】双端一致性综合评分为 {round(scores.weighted_composite_score, 1)} 分 (评级: {grade.value})。"
            f"检出 {discrepancy_report.critical_count} 项致命核心功能缺失或未覆盖，严禁直接上线，需立即优先修复单端缺失的业务操作！"
        )
    elif verdict == ReleaseGateVerdict.WARN:
        exec_summary = (
            f"【带险放行】双端一致性综合评分为 {round(scores.weighted_composite_score, 1)} 分 (评级: {grade.value})。"
            f"存在 {discrepancy_report.high_count} 项高危差异（如交互角色不对等或部分文案漂移），建议排查评估后推进。"
        )
    else:
        exec_summary = (
            f"【准入通过】双端一致性综合评分为 {round(scores.weighted_composite_score, 1)} 分 (评级: {grade.value})。"
            f"双端状态树对齐率达到 {round(matrix.overall_alignment_rate * 100, 1)}%，功能体验高度对称，符合全量发布标准。"
        )

    matrix_summary = {
        "total_source_nodes": matrix.total_source_nodes,
        "total_target_nodes": matrix.total_target_nodes,
        "aligned_pairs_count": matrix.aligned_pairs_count,
        "alignment_rate": round(matrix.overall_alignment_rate, 4),
    }

    disc_summary = {
        "total_gaps_count": discrepancy_report.total_gaps_count,
        "critical_count": discrepancy_report.critical_count,
        "high_count": discrepancy_report.high_count,
        "medium_count": discrepancy_report.medium_count,
        "low_count": discrepancy_report.low_count,
    }

    report = ParityAuditReport(
        report_id=report_id,
        screen_name=matrix.screen_name,
        source_platform=matrix.source_platform,
        target_platform=matrix.target_platform,
        composite_score=scores.weighted_composite_score,
        grade=grade,
        verdict=verdict,
        scores=scores,
        matrix_summary=matrix_summary,
        discrepancy_summary=disc_summary,
        gaps=[g.to_dict() for g in discrepancy_report.gaps],
        executive_summary=exec_summary,
    )

    _PARITY_REPORT_STORE[report_id] = report
    return report


def evaluate_screen_parity_end_to_end(
    source_tree: ParityScreenTree,
    target_tree: ParityScreenTree,
) -> ParityAuditReport:
    """从双端状态树输入直接端到端生成完整一致性审计报表"""
    matrix = align_screen_trees(source_tree, target_tree)
    discrepancy_report = detect_parity_gaps(matrix)
    return generate_parity_audit_report(matrix, discrepancy_report)


def get_parity_audit_report(report_id: str) -> Optional[ParityAuditReport]:
    """查询单张一致性审计报表详情"""
    return _PARITY_REPORT_STORE.get(report_id)


def list_parity_audit_reports(limit: int = 50) -> List[Dict[str, Any]]:
    """查询近期生成的双端一致性报表列表"""
    reports = list(_PARITY_REPORT_STORE.values())
    reports.sort(key=lambda x: x.generated_at, reverse=True)
    return [r.to_dict() for r in reports[:limit]]
