"""智能金丝雀健康度评分与多阶步进调度器服务 (T2.1)

综合评估五维健康度得分并自动化驱动金丝雀灰度流量阶梯式自适应步进:
1. 五维金丝雀健康度评分模型 (错误率、P99时延、业务成功率、CPU负载、稳定性);
2. 标准阶梯灰度步进计划 (5% -> 10% -> 25% -> 50% -> 100% 全量割接);
3. 步进自适应裁决调度 (CanaryStepperAction: 步进下一阶、维持观察、冻结阻断、就绪全量割接);
4. 综合步进决策报告输出 (CanarySteppingDecision & CanaryHealthScoreReport)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.services.canary_baseline_metric_comparator import (
    CanaryDualTrackComparisonReport,
    MetricDeviationVerdict,
)


class CanaryStepStage(str, enum.Enum):
    STAGE_1_5PCT = "STAGE_1_5PCT"  # 初始金丝雀探针分流: 5%
    STAGE_2_10PCT = "STAGE_2_10PCT"  # 第二阶平稳灰度: 10%
    STAGE_3_25PCT = "STAGE_3_25PCT"  # 第三阶扩大放量: 25%
    STAGE_4_50PCT = "STAGE_4_50PCT"  # 第四阶半数流量攻坚: 50%
    STAGE_5_CUTOVER_100PCT = "STAGE_5_CUTOVER_100PCT"  # 最终全量割接: 100%


class CanaryStepperAction(str, enum.Enum):
    PROMOTE_NEXT_STAGE = "PROMOTE_NEXT_STAGE"  # 健康度优异且平稳，自适应放量步进至下一阶梯
    HOLD_OBSERVING = "HOLD_OBSERVING"  # 处于观察窗口或指标轻度波动，维持当前权重继续采样
    BLOCK_OR_FREEZE = "BLOCK_OR_FREEZE"  # 健康度过低或触发警告，冻结步进放量
    READY_FOR_FULL_CUTOVER = "READY_FOR_FULL_CUTOVER"  # 50% 阶梯全面达标，准予执行 100% 生产全量割接


STAGE_WEIGHT_MAP: Dict[CanaryStepStage, float] = {
    CanaryStepStage.STAGE_1_5PCT: 5.0,
    CanaryStepStage.STAGE_2_10PCT: 10.0,
    CanaryStepStage.STAGE_3_25PCT: 25.0,
    CanaryStepStage.STAGE_4_50PCT: 50.0,
    CanaryStepStage.STAGE_5_CUTOVER_100PCT: 100.0,
}

NEXT_STAGE_MAP: Dict[CanaryStepStage, CanaryStepStage] = {
    CanaryStepStage.STAGE_1_5PCT: CanaryStepStage.STAGE_2_10PCT,
    CanaryStepStage.STAGE_2_10PCT: CanaryStepStage.STAGE_3_25PCT,
    CanaryStepStage.STAGE_3_25PCT: CanaryStepStage.STAGE_4_50PCT,
    CanaryStepStage.STAGE_4_50PCT: CanaryStepStage.STAGE_5_CUTOVER_100PCT,
    CanaryStepStage.STAGE_5_CUTOVER_100PCT: CanaryStepStage.STAGE_5_CUTOVER_100PCT,
}


@dataclass
class CanaryHealthDimensionScore:
    dimension_key: str
    dimension_name: str
    score: float  # 0.0 ~ 100.0
    weight: float
    verdict: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["score"] = round(self.score, 1)
        return d


@dataclass
class CanaryHealthScoreReport:
    composite_score: float  # 加权综合得分 0.0 ~ 100.0
    grade: str  # EXCELLENT (>=90) | GOOD (>=75) | MARGINAL (>=60) | POOR (<60)
    dimensions: List[CanaryHealthDimensionScore]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "composite_score": round(self.composite_score, 1),
            "grade": self.grade,
            "dimensions": [d.to_dict() for d in self.dimensions],
        }


@dataclass
class CanarySteppingDecision:
    decision_id: str
    target_service: str
    canary_version: str
    current_stage: CanaryStepStage
    current_weight_pct: float
    recommended_action: CanaryStepperAction
    next_recommended_weight_pct: float
    health_score: CanaryHealthScoreReport
    evaluation_summary: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "target_service": self.target_service,
            "canary_version": self.canary_version,
            "current_stage": self.current_stage.value,
            "current_weight_pct": round(self.current_weight_pct, 1),
            "recommended_action": self.recommended_action.value,
            "next_recommended_weight_pct": round(self.next_recommended_weight_pct, 1),
            "health_score": self.health_score.to_dict(),
            "evaluation_summary": self.evaluation_summary,
            "timestamp": self.timestamp,
        }


def calculate_canary_health_score(comparison: CanaryDualTrackComparisonReport) -> CanaryHealthScoreReport:
    """计算五维金丝雀健康度评分模型"""
    # 1. 错误率得分 (30% 权重)
    err_diff = comparison.error_rate_diff_pct
    if err_diff <= 0.0:
        score_err = 100.0
    elif err_diff <= 0.3:
        score_err = 95.0
    elif err_diff <= 1.0:
        score_err = 80.0
    elif err_diff <= 2.0:
        score_err = 50.0
    else:
        score_err = 20.0

    # 2. P99 响应时延得分 (25% 权重)
    lat_ratio = comparison.latency_p99_ratio
    if lat_ratio <= 1.05:
        score_lat = 100.0
    elif lat_ratio <= 1.15:
        score_lat = 90.0
    elif lat_ratio <= 1.25:
        score_lat = 75.0
    elif lat_ratio <= 1.50:
        score_lat = 50.0
    else:
        score_lat = 20.0

    # 3. 业务成功率得分 (25% 权重)
    succ_rate = comparison.canary_metrics.success_rate_pct
    if succ_rate >= 99.9:
        score_succ = 100.0
    elif succ_rate >= 99.0:
        score_succ = 90.0
    elif succ_rate >= 95.0:
        score_succ = 70.0
    else:
        score_succ = 30.0

    # 4. CPU 开销偏离 (10% 权重)
    cpu_diff = comparison.cpu_diff_pct
    if cpu_diff <= 5.0:
        score_cpu = 100.0
    elif cpu_diff <= 15.0:
        score_cpu = 85.0
    elif cpu_diff <= 30.0:
        score_cpu = 60.0
    else:
        score_cpu = 30.0

    # 5. 综合状态稳定性 (10% 权重)
    if comparison.overall_verdict == MetricDeviationVerdict.CONFORMANT:
        score_stab = 100.0
    elif comparison.overall_verdict == MetricDeviationVerdict.WARNING_DEGRADED:
        score_stab = 70.0
    else:
        score_stab = 20.0

    dimensions = [
        CanaryHealthDimensionScore("error_stability", "错误率平稳度", score_err, 0.30, f"差值: {err_diff}%"),
        CanaryHealthDimensionScore("latency_performance", "P99响应时延", score_lat, 0.25, f"倍率: {lat_ratio}x"),
        CanaryHealthDimensionScore("business_success", "业务成功率", score_succ, 0.25, f"成功率: {succ_rate}%"),
        CanaryHealthDimensionScore("resource_overhead", "计算资源开销", score_cpu, 0.10, f"CPU差值: {cpu_diff}%"),
        CanaryHealthDimensionScore(
            "overall_stability", "综合指标偏离", score_stab, 0.10, comparison.overall_verdict.value
        ),
    ]

    composite = sum(d.score * d.weight for d in dimensions)

    if composite >= 90.0:
        grade = "EXCELLENT"
    elif composite >= 75.0:
        grade = "GOOD"
    elif composite >= 60.0:
        grade = "MARGINAL"
    else:
        grade = "POOR"

    return CanaryHealthScoreReport(
        composite_score=composite,
        grade=grade,
        dimensions=dimensions,
    )


def evaluate_canary_stepping_schedule(
    comparison_report: CanaryDualTrackComparisonReport,
    current_stage: CanaryStepStage = CanaryStepStage.STAGE_1_5PCT,
    window_requests_accumulated: int = 600,
    min_requests_threshold: int = 500,
) -> CanarySteppingDecision:
    """自动化评估金丝雀灰度步进调度决策"""
    decision_id = f"cdec_{uuid.uuid4().hex[:10]}"
    health = calculate_canary_health_score(comparison_report)
    curr_weight = STAGE_WEIGHT_MAP.get(current_stage, 5.0)

    # 1. 检查观察窗口样本量是否充分
    if window_requests_accumulated < min_requests_threshold:
        return CanarySteppingDecision(
            decision_id=decision_id,
            target_service=comparison_report.target_service,
            canary_version=comparison_report.canary_version,
            current_stage=current_stage,
            current_weight_pct=curr_weight,
            recommended_action=CanaryStepperAction.HOLD_OBSERVING,
            next_recommended_weight_pct=curr_weight,
            health_score=health,
            evaluation_summary=f"当前阶段采样请求数 ({window_requests_accumulated}) 未达到最小观察窗口要求 ({min_requests_threshold})，继续保持观察。",
        )

    # 2. 健康度过低 -> 冻结步进
    if health.composite_score < 75.0 or comparison_report.overall_verdict == MetricDeviationVerdict.BREACHED_DEFICIT:
        return CanarySteppingDecision(
            decision_id=decision_id,
            target_service=comparison_report.target_service,
            canary_version=comparison_report.canary_version,
            current_stage=current_stage,
            current_weight_pct=curr_weight,
            recommended_action=CanaryStepperAction.BLOCK_OR_FREEZE,
            next_recommended_weight_pct=curr_weight,
            health_score=health,
            evaluation_summary=f"金丝雀健康度得分 ({round(health.composite_score, 1)}) 偏低或指标击穿，已安全冻结步进放量，请排查原因。",
        )

    # 3. 如果当前已经是 50% 阶梯，且健康度卓越 -> 就绪全量割接
    if current_stage == CanaryStepStage.STAGE_4_50PCT:
        if health.composite_score >= 90.0:
            return CanarySteppingDecision(
                decision_id=decision_id,
                target_service=comparison_report.target_service,
                canary_version=comparison_report.canary_version,
                current_stage=current_stage,
                current_weight_pct=curr_weight,
                recommended_action=CanaryStepperAction.READY_FOR_FULL_CUTOVER,
                next_recommended_weight_pct=100.0,
                health_score=health,
                evaluation_summary="金丝雀版本在 50% 半数流量下表现卓越满分，双轨指标坚固，准予执行 100% 生产全量割接！",
            )
        else:
            return CanarySteppingDecision(
                decision_id=decision_id,
                target_service=comparison_report.target_service,
                canary_version=comparison_report.canary_version,
                current_stage=current_stage,
                current_weight_pct=curr_weight,
                recommended_action=CanaryStepperAction.HOLD_OBSERVING,
                next_recommended_weight_pct=curr_weight,
                health_score=health,
                evaluation_summary=f"50% 阶梯下健康度 ({round(health.composite_score, 1)}) 处于良好区间但未达卓越门槛 (90.0)，继续保持观察。",
            )

    # 4. 如果健康度卓越 (>= 90) -> 驱动步进到下一阶梯
    if health.composite_score >= 90.0:
        next_stage = NEXT_STAGE_MAP[current_stage]
        next_weight = STAGE_WEIGHT_MAP[next_stage]
        return CanarySteppingDecision(
            decision_id=decision_id,
            target_service=comparison_report.target_service,
            canary_version=comparison_report.canary_version,
            current_stage=current_stage,
            current_weight_pct=curr_weight,
            recommended_action=CanaryStepperAction.PROMOTE_NEXT_STAGE,
            next_recommended_weight_pct=next_weight,
            health_score=health,
            evaluation_summary=f"金丝雀健康度综合得分 {round(health.composite_score, 1)} 分 (EXCELLENT)，平稳度过当前观察期，自适应推进至下一阶梯 [{next_stage.value} ({next_weight}%)]。",
        )

    # 5. 健康度良好 (75~90) -> 维持当前阶梯继续观察
    return CanarySteppingDecision(
        decision_id=decision_id,
        target_service=comparison_report.target_service,
        canary_version=comparison_report.canary_version,
        current_stage=current_stage,
        current_weight_pct=curr_weight,
        recommended_action=CanaryStepperAction.HOLD_OBSERVING,
        next_recommended_weight_pct=curr_weight,
        health_score=health,
        evaluation_summary=f"健康度良好 ({round(health.composite_score, 1)})，但略有轻微偏离，建议在当前阶梯 ({curr_weight}%) 延长观察期。",
    )
