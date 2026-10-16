"""测试执行准时率与团队研发效能 DORA 指标量化分析引擎 (D4.3).

基于业界权威 Google DORA (DevOps Research and Assessment) 标准模型，
量化部署频率、变更前置时间、变更失败率与故障恢复时长 (MTTR) 四维核心研发与测试效能指标，
并评估团队工程效能成熟度等级 (ELITE / HIGH / MEDIUM / LOW) 与瓶颈诊断。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class DoraLevel(str, Enum):
    ELITE = "elite"  # 卓越效能
    HIGH = "high"  # 高效能
    MEDIUM = "medium"  # 中等效能
    LOW = "low"  # 待改进效能


@dataclass
class DoraDimensionMetric:
    dimension_name: str
    value: float
    unit: str
    level: DoraLevel
    description: str
    benchmark_guideline: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension_name": self.dimension_name,
            "value": round(self.value, 2),
            "unit": self.unit,
            "level": self.level.value,
            "description": self.description,
            "benchmark_guideline": self.benchmark_guideline,
        }


@dataclass
class DoraPerformanceReport:
    report_id: str
    project_id: int | None
    evaluation_period_days: int
    overall_maturity_level: DoraLevel
    dimensions: dict[str, DoraDimensionMetric]
    test_on_time_completion_rate_pct: float
    bottlenecks_identified: list[str] = field(default_factory=list)
    engineering_efficiency_recommendations: list[str] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "project_id": self.project_id,
            "evaluation_period_days": self.evaluation_period_days,
            "overall_maturity_level": self.overall_maturity_level.value,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "test_on_time_completion_rate_pct": round(self.test_on_time_completion_rate_pct, 2),
            "bottlenecks_identified": self.bottlenecks_identified,
            "engineering_efficiency_recommendations": self.engineering_efficiency_recommendations,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


# 内存 DORA 报告仓库
_DORA_REPORTS: dict[str, DoraPerformanceReport] = {}


def _rate_deployment_frequency(daily_deployments: float) -> tuple[DoraLevel, str]:
    """评定部署频率等级。"""
    if daily_deployments >= 1.0:
        return DoraLevel.ELITE, "每天多次或日均 ≥ 1 次按需部署"
    elif daily_deployments >= 0.14:  # 每周至少一次
        return DoraLevel.HIGH, "每周 1 次至每月多次持续部署"
    elif daily_deployments >= 0.033:  # 每月至少一次
        return DoraLevel.MEDIUM, "每月 1 次至每季度定期部署"
    else:
        return DoraLevel.LOW, "数月一次或半年以上低频交付"


def _rate_lead_time(lead_time_hours: float) -> tuple[DoraLevel, str]:
    """评定变更前置时间 (从 Commit 到自动化验收上线)。"""
    if lead_time_hours <= 1.0:
        return DoraLevel.ELITE, "变更前置耗时 ≤ 1 小时 (极速交付)"
    elif lead_time_hours <= 24.0:
        return DoraLevel.HIGH, "变更前置耗时在 1 天以内 (敏捷日交付)"
    elif lead_time_hours <= 168.0:  # 7天
        return DoraLevel.MEDIUM, "变更前置耗时在 1 周以内 (双周迭代)"
    else:
        return DoraLevel.LOW, "变更前置耗时超过 1 周以上"


def _rate_change_failure_rate(failure_rate_pct: float) -> tuple[DoraLevel, str]:
    """评定变更失败率。"""
    if failure_rate_pct <= 5.0:
        return DoraLevel.ELITE, "变更失败率 ≤ 5% (高可靠发布)"
    elif failure_rate_pct <= 15.0:
        return DoraLevel.HIGH, "变更失败率在 5% ~ 15% 区间"
    elif failure_rate_pct <= 30.0:
        return DoraLevel.MEDIUM, "变更失败率在 15% ~ 30% 区间"
    else:
        return DoraLevel.LOW, "变更失败率超过 30% (高频故障返工)"


def _rate_mttr(mttr_minutes: float) -> tuple[DoraLevel, str]:
    """评定故障恢复平均时长 (MTTR)。"""
    if mttr_minutes <= 60.0:
        return DoraLevel.ELITE, "平均故障恢复时长 ≤ 1 小时 (瞬时熔断自愈)"
    elif mttr_minutes <= 1440.0:  # 1天
        return DoraLevel.HIGH, "平均故障恢复时长在 1 天以内"
    elif mttr_minutes <= 10080.0:  # 7天
        return DoraLevel.MEDIUM, "平均故障恢复时长在 1 周以内"
    else:
        return DoraLevel.LOW, "平均故障恢复时长超过 1 周"


def _compute_overall_maturity(levels: list[DoraLevel]) -> DoraLevel:
    """综合成熟度裁定模型：按多数派及均值权重。"""
    level_weights = {
        DoraLevel.ELITE: 4,
        DoraLevel.HIGH: 3,
        DoraLevel.MEDIUM: 2,
        DoraLevel.LOW: 1,
    }
    avg_score = sum(level_weights[lvl] for lvl in levels) / float(len(levels))

    if avg_score >= 3.5:
        return DoraLevel.ELITE
    elif avg_score >= 2.5:
        return DoraLevel.HIGH
    elif avg_score >= 1.5:
        return DoraLevel.MEDIUM
    else:
        return DoraLevel.LOW


def compute_dora_metrics(
    project_id: int | None = None,
    evaluation_period_days: int = 30,
    total_deployments_count: int = 45,
    lead_time_for_changes_hours: float = 0.8,
    change_failure_rate_pct: float = 4.2,
    time_to_restore_service_minutes: float = 35.0,
    test_runs_on_time_count: int = 95,
    test_runs_total_count: int = 100,
) -> DoraPerformanceReport:
    """计算完整的四维 DORA 效能指标与团队工程成熟度报告。"""
    report_id = f"dora_rep_{uuid.uuid4().hex[:12]}"

    # 1. 部署频率 (日均)
    days = max(1, evaluation_period_days)
    daily_deploy = total_deployments_count / float(days)
    dep_level, dep_guide = _rate_deployment_frequency(daily_deploy)

    # 2. 变更前置时长
    lead_level, lead_guide = _rate_lead_time(lead_time_for_changes_hours)

    # 3. 变更失败率
    fail_level, fail_guide = _rate_change_failure_rate(change_failure_rate_pct)

    # 4. 故障恢复时长 MTTR
    mttr_level, mttr_guide = _rate_mttr(time_to_restore_service_minutes)

    dimensions: dict[str, DoraDimensionMetric] = {
        "deployment_frequency": DoraDimensionMetric(
            dimension_name="Deployment Frequency (部署频率)",
            value=daily_deploy,
            unit="次/天",
            level=dep_level,
            description=f"过去 {days} 天内累计触发部署与验收 {total_deployments_count} 次，日均 {daily_deploy:.2f} 次",
            benchmark_guideline=dep_guide,
        ),
        "lead_time_for_changes": DoraDimensionMetric(
            dimension_name="Lead Time for Changes (变更前置时间)",
            value=lead_time_for_changes_hours,
            unit="小时",
            level=lead_level,
            description=f"从代码 Commit 提交到全自动化质检验收通过的平均耗时为 {lead_time_for_changes_hours:.1f} 小时",
            benchmark_guideline=lead_guide,
        ),
        "change_failure_rate": DoraDimensionMetric(
            dimension_name="Change Failure Rate (变更失败率)",
            value=change_failure_rate_pct,
            unit="%",
            level=fail_level,
            description=f"自动化构建与流水线发布失败导致返工的比率为 {change_failure_rate_pct:.1f}%",
            benchmark_guideline=fail_guide,
        ),
        "time_to_restore_service": DoraDimensionMetric(
            dimension_name="Time to Restore Service (故障恢复时长 MTTR)",
            value=time_to_restore_service_minutes,
            unit="分钟",
            level=mttr_level,
            description=f"流水线阻塞或执行失败后至修复自愈完成的平均修复耗时为 {time_to_restore_service_minutes:.1f} 分钟",
            benchmark_guideline=mttr_guide,
        ),
    }

    # 5. 测试执行准时完成率
    runs_total = max(1, test_runs_total_count)
    on_time_rate = (test_runs_on_time_count / float(runs_total)) * 100.0

    # 6. 综合成熟度等级评定
    all_levels = [dep_level, lead_level, fail_level, mttr_level]
    overall_maturity = _compute_overall_maturity(all_levels)

    # 7. 瓶颈诊断与建议
    bottlenecks: list[str] = []
    recommendations: list[str] = []

    if dep_level in {DoraLevel.MEDIUM, DoraLevel.LOW}:
        bottlenecks.append(f"部署交付频次偏低 (当前日均 {daily_deploy:.2f} 次)")
        recommendations.append("建议缩减需求批次规模，推行特性分支自动化流水线每日多次按需触发。")

    if lead_level in {DoraLevel.MEDIUM, DoraLevel.LOW}:
        bottlenecks.append(f"代码变更前置耗时过长 ({lead_time_for_changes_hours:.1f} 小时)")
        recommendations.append("建议利用 ATP 分布式 Worker 并发执行与瞬时沙箱分流，压缩用例排队与套件执行等待时延。")

    if fail_level in {DoraLevel.MEDIUM, DoraLevel.LOW}:
        bottlenecks.append(f"变更失败率偏高 ({change_failure_rate_pct:.1f}%)")
        recommendations.append("建议加强 PR 阶段质量门禁卡点校验，引入 AI 选择器自愈与柔性断言减少假阳性误报。")

    if mttr_level in {DoraLevel.MEDIUM, DoraLevel.LOW}:
        bottlenecks.append(f"故障平均恢复时长偏慢 ({time_to_restore_service_minutes:.1f} 分钟)")
        recommendations.append("建议启用全网心跳超时自动收割与孤儿任务故障转移重调度，提升自愈防灾时效。")

    if not bottlenecks:
        bottlenecks.append("全链路各项效能指标均表现卓越，暂未发现明显的工程交付瓶颈。")
        recommendations.append("团队处于业界最高水准的 Elite 卓越效能阶段，建议继续保持全自动 CI/CD 质量治理闭环。")

    report = DoraPerformanceReport(
        report_id=report_id,
        project_id=project_id,
        evaluation_period_days=days,
        overall_maturity_level=overall_maturity,
        dimensions=dimensions,
        test_on_time_completion_rate_pct=on_time_rate,
        bottlenecks_identified=bottlenecks,
        engineering_efficiency_recommendations=recommendations,
    )

    _DORA_REPORTS[report_id] = report
    logger.info(
        "Computed DORA metrics report_id=%s maturity=%s on_time_rate=%.2f%%",
        report_id,
        overall_maturity.value,
        on_time_rate,
    )
    return report


def get_dora_report(report_id: str) -> DoraPerformanceReport | None:
    """获取指定 DORA 效能分析报告。"""
    return _DORA_REPORTS.get(report_id)


def list_dora_reports(project_id: int | None = None) -> list[DoraPerformanceReport]:
    """查询历史 DORA 效能分析报告列表。"""
    reports = list(_DORA_REPORTS.values())
    if project_id is not None:
        reports = [r for r in reports if r.project_id == project_id]
    return reports


def reset_dora_registry() -> None:
    """供单元测试清理状态使用。"""
    _DORA_REPORTS.clear()
