"""全生命周期多维质量健康综合评分引擎 (T4.1)。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class QualityGrade(str, Enum):
    """系统质量健康等级。"""

    GRADE_A_PLUS = "A+"  # >= 90
    GRADE_A = "A"  # 80 ~ 89.9
    GRADE_B = "B"  # 70 ~ 79.9
    GRADE_C = "C"  # < 70 (高危阻断)


@dataclass
class QualityInputMetrics:
    """输入的各项多维质量指标。"""

    test_pass_rate_pct: float = 100.0  # 测试执行通过率 0~100%
    code_coverage_pct: float = 85.0  # 核心业务代码覆盖率 0~100%
    mutation_score_pct: float = 80.0  # 变异测试得分 0~100%
    p0_defects_count: int = 0  # 未修复 P0 阻塞级缺陷数
    p1_defects_count: int = 0  # 未修复 P1 严重缺陷数
    p2_defects_count: int = 0  # 未修复 P2 一般缺陷数
    change_risk_score: float = 10.0  # 变更风险指数 0~100 (越低越安全)
    compliance_score_pct: float = 100.0  # 基础设施与配置合规度 0~100%


@dataclass
class QualityHealthScoreResult:
    """综合质量健康评分结果。"""

    report_id: str
    target_name: str
    composite_score: float
    grade: QualityGrade
    dimension_scores: dict[str, float]
    dimension_weights: dict[str, float]
    primary_risk_factors: list[str]
    optimization_recommendations: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "target_name": self.target_name,
            "composite_score": round(self.composite_score, 1),
            "grade": self.grade.value,
            "dimension_scores": {k: round(v, 1) for k, v in self.dimension_scores.items()},
            "dimension_weights": self.dimension_weights,
            "primary_risk_factors": self.primary_risk_factors,
            "optimization_recommendations": self.optimization_recommendations,
            "created_at": self.created_at.isoformat(),
        }


# 全局健康评分报告存储
_HEALTH_SCORE_REPORTS: dict[str, QualityHealthScoreResult] = {}


def clear_health_score_store() -> None:
    """清空健康评分仓库（单测专用）。"""
    _HEALTH_SCORE_REPORTS.clear()


def calculate_quality_health_score(
    target_name: str,
    metrics: QualityInputMetrics,
) -> QualityHealthScoreResult:
    """融合多维指标计算综合质量健康得分与评级。"""
    # 权重配置 (总和 1.0)
    weights = {
        "test_execution": 0.25,  # 测试执行通过率
        "code_coverage": 0.20,  # 代码覆盖率
        "mutation_score": 0.15,  # 变异测试
        "defect_density": 0.20,  # 缺陷密度
        "change_risk": 0.10,  # 变更风险
        "env_compliance": 0.10,  # 环境与配置合规
    }

    # 1. 测试通过率子分 (0~100)
    score_test = max(0.0, min(100.0, metrics.test_pass_rate_pct))

    # 2. 覆盖率子分 (0~100)
    score_cov = max(0.0, min(100.0, metrics.code_coverage_pct))

    # 3. 变异测试子分 (0~100)
    score_mut = max(0.0, min(100.0, metrics.mutation_score_pct))

    # 4. 缺陷密度子分: 初始 100 分，按 P0(-30), P1(-15), P2(-5) 扣分
    defect_penalty = (
        (metrics.p0_defects_count * 30.0) + (metrics.p1_defects_count * 15.0) + (metrics.p2_defects_count * 5.0)
    )
    score_defect = max(0.0, 100.0 - defect_penalty)

    # 5. 变更风险子分: 风险越低得分越高 100 - risk
    score_risk = max(0.0, min(100.0, 100.0 - metrics.change_risk_score))

    # 6. 环境合规子分 (0~100)
    score_comp = max(0.0, min(100.0, metrics.compliance_score_pct))

    dimension_scores = {
        "test_execution": score_test,
        "code_coverage": score_cov,
        "mutation_score": score_mut,
        "defect_density": score_defect,
        "change_risk": score_risk,
        "env_compliance": score_comp,
    }

    composite = (
        (score_test * weights["test_execution"])
        + (score_cov * weights["code_coverage"])
        + (score_mut * weights["mutation_score"])
        + (score_defect * weights["defect_density"])
        + (score_risk * weights["change_risk"])
        + (score_comp * weights["env_compliance"])
    )

    # 一票否决硬约束：若存在未解决的 P0 缺陷，最高评级不可超过 C 且得分上限截断为 65.0
    primary_risks: list[str] = []
    recommendations: list[str] = []

    if metrics.p0_defects_count > 0:
        composite = min(composite, 65.0)
        primary_risks.append(f"存在 {metrics.p0_defects_count} 个未修复的 P0 阻塞级缺陷，触发一票否决限制")
        recommendations.append("优先闭环修复未完成的 P0 核心阻塞缺陷，确保系统核心交易主流程畅通。")

    if metrics.test_pass_rate_pct < 98.0:
        primary_risks.append(f"自动化测试通过率仅为 {metrics.test_pass_rate_pct}%，未达到 98% 质量基线")
        recommendations.append("排查失败用例是由于功能缺陷或用例断言漂移，及时修复或自愈用例脚本。")

    if metrics.code_coverage_pct < 80.0:
        primary_risks.append(f"核心业务代码覆盖率 ({metrics.code_coverage_pct}%) 低于 80% 黄金基准线")
        recommendations.append("针对未覆盖的分支与异常处理路径增补单元或集成测试用例。")

    if metrics.mutation_score_pct < 70.0:
        primary_risks.append(f"变异测试得分 ({metrics.mutation_score_pct}%) 偏低，断言有效性不足")
        recommendations.append("增强用例断言深度，避免仅做 HTTP 状态码校验而忽略响应体业务数据校验。")

    if metrics.compliance_score_pct < 85.0:
        primary_risks.append(f"环境与 IaC 基础设施合规得分 ({metrics.compliance_score_pct}%) 偏低")
        recommendations.append("修复容器特权模式、敏感卷挂载或未受限网络策略配置。")

    if not primary_risks:
        primary_risks.append("系统各项核心质量指标均表现卓越，无显著扣分项。")
        recommendations.append("保持当前高水平的测试覆盖率与自动化防护体系，持续推进流水线自动验证。")

    # 确定等级
    if composite >= 90.0:
        grade = QualityGrade.GRADE_A_PLUS
    elif composite >= 80.0:
        grade = QualityGrade.GRADE_A
    elif composite >= 70.0:
        grade = QualityGrade.GRADE_B
    else:
        grade = QualityGrade.GRADE_C

    now = datetime.now(timezone.utc)
    report_id = f"health_{target_name[:12]}_{int(now.timestamp())}"
    result = QualityHealthScoreResult(
        report_id=report_id,
        target_name=target_name,
        composite_score=composite,
        grade=grade,
        dimension_scores=dimension_scores,
        dimension_weights=weights,
        primary_risk_factors=primary_risks,
        optimization_recommendations=recommendations,
        created_at=now,
    )
    _HEALTH_SCORE_REPORTS[report_id] = result
    return result


def get_quality_health_report(report_id: str) -> QualityHealthScoreResult | None:
    """按 ID 查询质量健康报告。"""
    return _HEALTH_SCORE_REPORTS.get(report_id)


def list_quality_health_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史质量健康评分报告列表。"""
    reports = list(reversed(list(_HEALTH_SCORE_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
