"""Full-Lifecycle Software Quality Health Metrics & Multi-Dimensional Scoring Engine (C4.1).

Provides:
1. Automated coverage index calculation across requirement & API case domains.
2. Defect escape rate measurement (production vs internal test discovery).
3. Test execution stability and flaky test fluctuation variance scoring.
4. Mean Time to Repair (MTTR) tracking and penalty calculation.
5. Composite 0-100 quality health score and Grade A-F release readiness assessment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


@dataclass
class QualityDimensionMetrics:
    # 1. Automation Coverage (30% weight)
    total_test_cases: int = 100
    automated_test_cases: int = 85
    coverage_pct: float = 85.0
    coverage_score: float = 85.0

    # 2. Defect Escape Rate (25% weight)
    internal_defects_count: int = 40
    production_escape_defects: int = 2
    escape_rate_pct: float = 4.76
    escape_score: float = 52.4

    # 3. Execution Stability (25% weight)
    total_runs_evaluated: int = 50
    flaky_runs_count: int = 2
    flaky_ratio_pct: float = 4.0
    stability_score: float = 92.0

    # 4. Mean Time To Repair (20% weight)
    mttr_hours: float = 3.5
    mttr_score: float = 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "automation_coverage": {
                "total_cases": self.total_test_cases,
                "automated_cases": self.automated_test_cases,
                "coverage_pct": round(self.coverage_pct, 2),
                "score": round(self.coverage_score, 1),
                "weight_pct": 30,
            },
            "defect_escape": {
                "internal_defects": self.internal_defects_count,
                "production_escapes": self.production_escape_defects,
                "escape_rate_pct": round(self.escape_rate_pct, 2),
                "score": round(self.escape_score, 1),
                "weight_pct": 25,
            },
            "execution_stability": {
                "total_runs": self.total_runs_evaluated,
                "flaky_runs": self.flaky_runs_count,
                "flaky_ratio_pct": round(self.flaky_ratio_pct, 2),
                "score": round(self.stability_score, 1),
                "weight_pct": 25,
            },
            "mttr": {
                "mttr_hours": round(self.mttr_hours, 1),
                "score": round(self.mttr_score, 1),
                "weight_pct": 20,
            },
        }


@dataclass
class QualityHealthReport:
    report_id: str
    project_id: int
    evaluated_at: str
    composite_health_score: float
    grade: str  # "A" | "B" | "C" | "D" | "F"
    release_readiness: str  # "APPROVED" | "WARNING" | "BLOCKED"
    dimensions: QualityDimensionMetrics
    risk_alerts: list[str] = field(default_factory=list)
    actionable_recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "project_id": self.project_id,
            "evaluated_at": self.evaluated_at,
            "composite_health_score": round(self.composite_health_score, 1),
            "grade": self.grade,
            "release_readiness": self.release_readiness,
            "dimensions": self.dimensions.to_dict(),
            "risk_alerts": self.risk_alerts,
            "actionable_recommendations": self.actionable_recommendations,
        }


def calculate_coverage_score(total_cases: int, automated_cases: int) -> tuple[float, float]:
    """Calculate automation coverage percentage and normalized score (0-100)."""
    if total_cases <= 0:
        return 100.0, 100.0
    cov_pct = min(100.0, (automated_cases / total_cases) * 100.0)
    # Target baseline is 80%: >80% gets 90-100, 50-80% gets 60-90, <50% penalized
    if cov_pct >= 80.0:
        score = 90.0 + (cov_pct - 80.0) * 0.5
    elif cov_pct >= 50.0:
        score = 60.0 + (cov_pct - 50.0) * 1.0
    else:
        score = max(0.0, cov_pct * 1.2)
    return cov_pct, min(100.0, score)


def calculate_escape_score(internal_defects: int, prod_escapes: int) -> tuple[float, float]:
    """Calculate defect escape rate and normalized score (0-100)."""
    total_defects = internal_defects + prod_escapes
    if total_defects <= 0:
        return 0.0, 100.0
    escape_pct = (prod_escapes / total_defects) * 100.0
    # Escape rate <= 3% is optimal (95-100), 3-8% (70-95), >15% heavily penalized
    score = max(0.0, 100.0 - escape_pct * 5.0)
    return escape_pct, min(100.0, score)


def calculate_stability_score(total_runs: int, flaky_runs: int) -> tuple[float, float]:
    """Calculate test execution fluctuation and flaky penalty score."""
    if total_runs <= 0:
        return 0.0, 100.0
    flaky_pct = min(100.0, (flaky_runs / total_runs) * 100.0)
    score = max(0.0, 100.0 - flaky_pct * 2.5)
    return flaky_pct, score


def calculate_mttr_score(avg_repair_hours: float) -> float:
    """Calculate MTTR score based on average repair latency in hours."""
    if avg_repair_hours <= 2.0:
        return 100.0
    if avg_repair_hours <= 8.0:
        return 85.0
    if avg_repair_hours <= 24.0:
        return 70.0
    if avg_repair_hours <= 48.0:
        return 50.0
    return 30.0


def compute_quality_health_report(
    project_id: int,
    *,
    total_cases: int = 100,
    automated_cases: int = 85,
    internal_defects: int = 40,
    prod_escapes: int = 2,
    total_runs: int = 50,
    flaky_runs: int = 2,
    mttr_hours: float = 3.5,
) -> QualityHealthReport:
    """Evaluate full-lifecycle quality health and grade release readiness."""
    report_id = f"qrep_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Dimensions calculation
    cov_pct, cov_score = calculate_coverage_score(total_cases, automated_cases)
    esc_pct, esc_score = calculate_escape_score(internal_defects, prod_escapes)
    flaky_pct, stab_score = calculate_stability_score(total_runs, flaky_runs)
    mttr_score = calculate_mttr_score(mttr_hours)

    dimensions = QualityDimensionMetrics(
        total_test_cases=total_cases,
        automated_test_cases=automated_cases,
        coverage_pct=cov_pct,
        coverage_score=cov_score,
        internal_defects_count=internal_defects,
        production_escape_defects=prod_escapes,
        escape_rate_pct=esc_pct,
        escape_score=esc_score,
        total_runs_evaluated=total_runs,
        flaky_runs_count=flaky_runs,
        flaky_ratio_pct=flaky_pct,
        stability_score=stab_score,
        mttr_hours=mttr_hours,
        mttr_score=mttr_score,
    )

    # 2. Weighted sum composite score
    composite_score = 0.30 * cov_score + 0.25 * esc_score + 0.25 * stab_score + 0.20 * mttr_score
    composite_score = max(0.0, min(100.0, composite_score))

    # 3. Grade & Readiness classification
    risks: list[str] = []
    recommendations: list[str] = []

    if composite_score >= 90.0:
        grade = "A"
        readiness = "APPROVED"
        recommendations.append("质量表现卓越，各项核心度量指标均处于企业顶级成熟度，准予一键发版上线。")
    elif composite_score >= 80.0:
        grade = "B"
        readiness = "APPROVED" if prod_escapes == 0 else "WARNING"
        recommendations.append("整体质量稳定，低风险平稳运行，建议进一步提升自动化用例占比。")
    elif composite_score >= 65.0:
        grade = "C"
        readiness = "WARNING"
        recommendations.append("质量指标存在明显波动，建议排查高频缺陷模块并组织专项回归。")
    else:
        grade = "D" if composite_score >= 50.0 else "F"
        readiness = "BLOCKED"
        recommendations.append("质量处于高危不可控状态，严禁发版！必须解决核心缺陷并降低逃逸率。")

    # Specific risk alerts
    if esc_pct > 10.0:
        risks.append(f"缺陷逃逸率严重超标: {esc_pct:.1f}% > 10.0% 预警红线！")
    if cov_pct < 60.0:
        risks.append(f"自动化覆盖率偏低: {cov_pct:.1f}% < 60.0% 基准线！")
    if flaky_pct > 8.0:
        risks.append(f"测试用例抖动率偏高: {flaky_pct:.1f}%，存在较多 Flaky 测试干扰 CI 准入！")
    if mttr_hours > 24.0:
        risks.append(f"平均故障修复时延较慢: MTTR = {mttr_hours:.1f} 小时，协同修复效率需改善！")

    return QualityHealthReport(
        report_id=report_id,
        project_id=project_id,
        evaluated_at=now_iso,
        composite_health_score=composite_score,
        grade=grade,
        release_readiness=readiness,
        dimensions=dimensions,
        risk_alerts=risks,
        actionable_recommendations=recommendations,
    )
