"""回放偏离评分与 Breaking Change 裁决控制器服务 (T2.3)

基于降噪后的双端响应差异报告，计算回放一致性评分并裁决发布阻断与放行:
1. 0~100 多维差异加权一致性评分算法 (Consistency Scoring Model);
2. Breaking 破坏性变迁与 Non-Breaking 兼容变迁精准定级 (ChangeImpactLevel);
3. 自动化门禁放行与阻断裁决器 (ReplayVerdict: PASSED | WARN_PERMISSIVE | BLOCKED_BREAKING);
4. 综合评估结果与整改行动建议输出 (ReplayEvaluationResult)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.services.dynamic_noise_suppressor import SuppressedDiffReport
from app.services.traffic_response_diff_comparator import (
    DiffSeverity,
    ResponseDiffCategory,
)


class ChangeImpactLevel(str, enum.Enum):
    NONE = "NONE"  # 无业务差异 (完全一致或纯噪声)
    NON_BREAKING = "NON_BREAKING"  # 向后兼容变迁 (仅新增字段或次要差异)
    BREAKING = "BREAKING"  # 破坏性不兼容变迁 (键缺失/状态码偏离/类型破坏)


class ReplayVerdict(str, enum.Enum):
    PASSED = "PASSED"  # 100% 验证通过 (Score = 100)
    WARN_PERMISSIVE = "WARN_PERMISSIVE"  # 带警示放行 (80 <= Score < 100 且无 BLOCKER)
    BLOCKED_BREAKING = "BLOCKED_BREAKING"  # 强行阻断 (Score < 80 或存在破坏性差异)


@dataclass
class ReplayEvaluationResult:
    evaluation_id: str
    record_id: str
    consistency_score: float  # 0.0 ~ 100.0
    impact_level: ChangeImpactLevel
    verdict: ReplayVerdict
    is_deployable: bool
    effective_diff_count: int
    suppressed_noise_count: int
    blocker_reasons: List[str]
    recommendations: List[str]
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "record_id": self.record_id,
            "consistency_score": round(self.consistency_score, 1),
            "impact_level": self.impact_level.value,
            "verdict": self.verdict.value,
            "is_deployable": self.is_deployable,
            "effective_diff_count": self.effective_diff_count,
            "suppressed_noise_count": self.suppressed_noise_count,
            "blocker_reasons": self.blocker_reasons,
            "recommendations": self.recommendations,
            "evaluated_at": self.evaluated_at,
        }


def evaluate_replay_drift(suppressed_report: SuppressedDiffReport) -> ReplayEvaluationResult:
    """综合评估降噪后的回放差异，计算一致性得分与门禁裁决"""
    eval_id = f"eval_rpl_{uuid.uuid4().hex[:10]}"
    base_score = 100.0

    blockers: List[str] = []
    recommendations: List[str] = []

    has_blocker_diff = False
    has_major_diff = False

    for diff in suppressed_report.effective_diffs:
        # 1. 状态码差异
        if diff.category == ResponseDiffCategory.STATUS_CODE_MISMATCH:
            if diff.severity == DiffSeverity.BLOCKER:
                base_score -= 50.0
                has_blocker_diff = True
                blockers.append(
                    f"HTTP 状态码发生跨大类严重偏离: 基线={diff.baseline_value}, 回放={diff.replayed_value}"
                )
            else:
                base_score -= 15.0
                has_major_diff = True
                blockers.append(f"HTTP 状态码微偏离: 基线={diff.baseline_value}, 回放={diff.replayed_value}")

        # 2. 字段丢失 (破坏性 Breaking)
        elif diff.category == ResponseDiffCategory.MISSING_KEY:
            base_score -= 20.0
            has_major_diff = True
            blockers.append(f"基线核心字段丢失: '{diff.json_path}'")

        # 3. 类型不匹配
        elif diff.category == ResponseDiffCategory.TYPE_MISMATCH:
            base_score -= 15.0
            has_major_diff = True
            blockers.append(f"数据类型不兼容: '{diff.json_path}' (基线与回放数据结构相斥)")

        # 4. 字段值偏离
        elif diff.category == ResponseDiffCategory.VALUE_MISMATCH:
            base_score -= 5.0
            recommendations.append(f"业务字段取值变化: '{diff.json_path}'")

        # 5. 新增意外字段
        elif diff.category == ResponseDiffCategory.UNEXPECTED_KEY:
            base_score -= 2.0
            recommendations.append(f"回放新增可选字段: '{diff.json_path}'")

    final_score = max(0.0, min(100.0, base_score))

    # 定级与裁决决策
    if suppressed_report.effective_diff_count == 0:
        impact = ChangeImpactLevel.NONE
        verdict = ReplayVerdict.PASSED
        is_deployable = True
        recommendations.append("双端响应完全一致或仅包含合法动态噪声，无任何破坏性变迁")
    elif has_blocker_diff or has_major_diff or final_score < 80.0:
        impact = ChangeImpactLevel.BREAKING
        verdict = ReplayVerdict.BLOCKED_BREAKING
        is_deployable = False
        recommendations.append("检测到阻断性破坏变迁（状态码异常或必要字段丢失），禁止合流上线，请排查下游接口兼容性")
    else:
        impact = ChangeImpactLevel.NON_BREAKING
        verdict = ReplayVerdict.WARN_PERMISSIVE
        is_deployable = True
        recommendations.append("存在次要业务值偏离或新增可选字段，属于向后兼容演进，允许带警示放行")

    return ReplayEvaluationResult(
        evaluation_id=eval_id,
        record_id=suppressed_report.record_id,
        consistency_score=final_score,
        impact_level=impact,
        verdict=verdict,
        is_deployable=is_deployable,
        effective_diff_count=suppressed_report.effective_diff_count,
        suppressed_noise_count=suppressed_report.suppressed_noise_count,
        blocker_reasons=blockers,
        recommendations=recommendations,
    )
