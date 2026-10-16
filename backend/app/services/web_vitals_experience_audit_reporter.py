"""核心体验 Web Vitals (LCP/INP/CLS) 全景审计报告生成器 (T4.3)。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MetricRating(str, Enum):
    """Google Web Vitals 官方单项指标评级。"""

    GOOD = "GOOD"  # 体验优质
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"  # 需持续改进
    POOR = "POOR"  # 严重恶化


@dataclass
class WebVitalMetricItem:
    """单个 Web Vitals 核心指标详情。"""

    name: str  # LCP, INP, CLS, FCP, TTFB
    value: float
    unit: str  # ms 或 score
    rating: MetricRating
    good_threshold: float
    poor_threshold: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 3 if self.unit == "score" else 1),
            "unit": self.unit,
            "rating": self.rating.value,
            "good_threshold": self.good_threshold,
            "poor_threshold": self.poor_threshold,
            "description": self.description,
        }


@dataclass
class WebVitalsAuditReport:
    """Web Vitals 全景综合审计报告。"""

    report_id: str
    target_url_or_page: str
    overall_cwv_passed: bool  # LCP, INP, CLS 均处于 GOOD 判定为达标
    performance_score_pct: float  # 0~100 综合得分
    lcp_metric: WebVitalMetricItem
    inp_metric: WebVitalMetricItem
    cls_metric: WebVitalMetricItem
    auxiliary_metrics: list[WebVitalMetricItem]
    optimization_recommendations: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "target_url_or_page": self.target_url_or_page,
            "overall_cwv_passed": self.overall_cwv_passed,
            "performance_score_pct": round(self.performance_score_pct, 1),
            "lcp": self.lcp_metric.to_dict(),
            "inp": self.inp_metric.to_dict(),
            "cls": self.cls_metric.to_dict(),
            "auxiliary_metrics": [m.to_dict() for m in self.auxiliary_metrics],
            "optimization_recommendations": self.optimization_recommendations,
            "created_at": self.created_at.isoformat(),
        }

    def to_markdown(self) -> str:
        """导出结构化 Markdown 审计报告。"""
        status_text = "✅ 达标 (PASS)" if self.overall_cwv_passed else "❌ 未达标 (FAIL)"
        lines = [
            f"# Web Vitals 核心体验审计报告 - {self.target_url_or_page}",
            f"> 生成时间: {self.created_at.isoformat()} | 审计单号: `{self.report_id}`",
            "",
            "## 1. 综合结论",
            f"- **CWV 总体判定**: **{status_text}**",
            f"- **综合体验得分**: **{self.performance_score_pct:.1f} / 100**",
            "",
            "## 2. 核心指标矩阵 (Core Web Vitals)",
            "| 指标项 | 采集数值 | 单位 | 评级状态 | 优秀标准 (Good) | 较差标准 (Poor) |",
            "|---|---|---|---|---|---|",
            f"| **LCP** (最大内容渲染) | {self.lcp_metric.value:.1f} | ms | {self.lcp_metric.rating.value} | ≤ 2500ms | > 4000ms |",
            f"| **INP** (交互到下次绘制) | {self.inp_metric.value:.1f} | ms | {self.inp_metric.rating.value} | ≤ 200ms | > 500ms |",
            f"| **CLS** (累积布局偏移) | {self.cls_metric.value:.3f} | score | {self.cls_metric.rating.value} | ≤ 0.100 | > 0.250 |",
            "",
            "## 3. 辅助诊断指标",
        ]
        for aux in self.auxiliary_metrics:
            lines.append(f"- **{aux.name}**: {aux.value:.1f}{aux.unit} ({aux.rating.value}) - {aux.description}")

        lines.extend(
            [
                "",
                "## 4. 针对性性能调优指引",
            ]
        )
        for idx, rec in enumerate(self.optimization_recommendations, 1):
            lines.append(f"{idx}. {rec}")

        return "\n".join(lines)


# 全局审计报告存储
_WEB_VITALS_REPORTS: dict[str, WebVitalsAuditReport] = {}


def clear_web_vitals_store() -> None:
    """清空 Web Vitals 报告仓库 (单测专用)。"""
    _WEB_VITALS_REPORTS.clear()


def _rate_metric(value: float, good_th: float, poor_th: float) -> MetricRating:
    """依据官方区间评定指标等级。"""
    if value <= good_th:
        return MetricRating.GOOD
    if value <= poor_th:
        return MetricRating.NEEDS_IMPROVEMENT
    return MetricRating.POOR


def generate_web_vitals_report(
    target_url_or_page: str,
    lcp_ms: float,
    inp_ms: float,
    cls_score: float,
    fcp_ms: float | None = None,
    ttfb_ms: float | None = None,
) -> WebVitalsAuditReport:
    """汇总量化 Google Core Web Vitals 核心指标，输出体验达标率与针对性性能调优指引。"""
    # 1. 评估三大核心指标
    lcp_rating = _rate_metric(lcp_ms, 2500.0, 4000.0)
    inp_rating = _rate_metric(inp_ms, 200.0, 500.0)
    cls_rating = _rate_metric(cls_score, 0.1, 0.25)

    lcp_item = WebVitalMetricItem(
        name="LCP",
        value=lcp_ms,
        unit="ms",
        rating=lcp_rating,
        good_threshold=2500.0,
        poor_threshold=4000.0,
        description="Largest Contentful Paint 测量页面主要内容完全加载并呈现在屏幕上的耗时。",
    )

    inp_item = WebVitalMetricItem(
        name="INP",
        value=inp_ms,
        unit="ms",
        rating=inp_rating,
        good_threshold=200.0,
        poor_threshold=500.0,
        description="Interaction to Next Paint 评估用户与页面交互时发生的整体最长延迟反馈时间。",
    )

    cls_item = WebVitalMetricItem(
        name="CLS",
        value=cls_score,
        unit="score",
        rating=cls_rating,
        good_threshold=0.1,
        poor_threshold=0.25,
        description="Cumulative Layout Shift 衡量页面在整个生命周期中发生的意外布局偏移量。",
    )

    # 2. 辅助指标
    auxiliary_items: list[WebVitalMetricItem] = []
    if fcp_ms is not None:
        auxiliary_items.append(
            WebVitalMetricItem(
                name="FCP",
                value=fcp_ms,
                unit="ms",
                rating=_rate_metric(fcp_ms, 1800.0, 3000.0),
                good_threshold=1800.0,
                poor_threshold=3000.0,
                description="First Contentful Paint 测量浏览器从导航开始到渲染出第一个文本或图像的时间。",
            )
        )
    if ttfb_ms is not None:
        auxiliary_items.append(
            WebVitalMetricItem(
                name="TTFB",
                value=ttfb_ms,
                unit="ms",
                rating=_rate_metric(ttfb_ms, 800.0, 1800.0),
                good_threshold=800.0,
                poor_threshold=1800.0,
                description="Time to First Byte 测量网络请求到服务器返回首个响应字节的等待时间。",
            )
        )

    # 3. 总体判定与综合评分
    is_passed = lcp_rating == MetricRating.GOOD and inp_rating == MetricRating.GOOD and cls_rating == MetricRating.GOOD

    # 计分算法 (LCP 35分, INP 35分, CLS 30分)
    score_lcp = (
        35.0 if lcp_rating == MetricRating.GOOD else (20.0 if lcp_rating == MetricRating.NEEDS_IMPROVEMENT else 5.0)
    )
    score_inp = (
        35.0 if inp_rating == MetricRating.GOOD else (20.0 if inp_rating == MetricRating.NEEDS_IMPROVEMENT else 5.0)
    )
    score_cls = (
        30.0 if cls_rating == MetricRating.GOOD else (15.0 if cls_rating == MetricRating.NEEDS_IMPROVEMENT else 0.0)
    )
    overall_score = score_lcp + score_inp + score_cls

    # 4. 优化指引生成
    recommendations: list[str] = []
    if lcp_rating != MetricRating.GOOD:
        recommendations.append(
            f"LCP 耗时高达 {lcp_ms:.1f}ms: 针对主视口大图/文字卡片采用 `<link rel='preload'>` 预加载，"
            f"压缩静态资源并启用 CDN 边缘缓存。"
        )
    if inp_rating != MetricRating.GOOD:
        recommendations.append(
            f"INP 延迟达到 {inp_ms:.1f}ms: 避免在点击事件处理函数中执行同步昂贵操作，"
            f"使用 `scheduler.yield()` 或 `requestAnimationFrame` 将渲染与逻辑解耦。"
        )
    if cls_rating != MetricRating.GOOD:
        recommendations.append(
            f"CLS 布局偏移量高达 {cls_score:.3f}: 为所有图片、骨架屏、动态图表容器显式声明固定尺寸或 `aspect-ratio`，"
            f"严禁在现有内容上方动态插入未预留高度的异步广告或通知 Banner。"
        )
    if not recommendations:
        recommendations.append("各项核心指标全绿，表现卓越！建议在生产环境持续监控 75 分位数 (p75) 性能波动。")

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", target_url_or_page)[:16]
    report_id = f"cwv_rpt_{safe_name}_{int(now.timestamp())}"

    report = WebVitalsAuditReport(
        report_id=report_id,
        target_url_or_page=target_url_or_page,
        overall_cwv_passed=is_passed,
        performance_score_pct=overall_score,
        lcp_metric=lcp_item,
        inp_metric=inp_item,
        cls_metric=cls_item,
        auxiliary_metrics=auxiliary_items,
        optimization_recommendations=recommendations,
        created_at=now,
    )

    _WEB_VITALS_REPORTS[report_id] = report
    return report


def get_web_vitals_report(report_id: str) -> WebVitalsAuditReport | None:
    """按 ID 查询 Web Vitals 报告。"""
    return _WEB_VITALS_REPORTS.get(report_id)


def list_web_vitals_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史 Web Vitals 报告列表。"""
    reports = list(reversed(list(_WEB_VITALS_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
