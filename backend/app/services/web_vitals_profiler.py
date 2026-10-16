"""Web 性能 Core Web Vitals (LCP, INP, CLS) 自动化深度诊断服务 (D3.2).

基于 Google 官方 Web Vitals 标准（LCP、INP/FID、CLS、FCP、TTFB、TBT），
对 Web 端应用页面加载性能与交互流畅度进行量化评估，自动分析关键渲染阻塞资源并输出优化建议。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class VitalRating(str, Enum):
    GOOD = "good"  # 绿色优秀
    NEEDS_IMPROVEMENT = "needs_improvement"  # 橙色需改进
    POOR = "poor"  # 红色较差


@dataclass
class WebVitalMetric:
    name: str
    value: float
    unit: str
    rating: VitalRating
    good_threshold: float
    poor_threshold: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 3),
            "unit": self.unit,
            "rating": self.rating.value,
            "good_threshold": self.good_threshold,
            "poor_threshold": self.poor_threshold,
            "description": self.description,
        }


@dataclass
class BlockingResource:
    url: str
    resource_type: str  # script | stylesheet | image | font
    duration_ms: float
    transfer_size_kb: float
    impact: str  # high | medium | low
    suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "resource_type": self.resource_type,
            "duration_ms": round(self.duration_ms, 2),
            "transfer_size_kb": round(self.transfer_size_kb, 2),
            "impact": self.impact,
            "suggestion": self.suggestion,
        }


@dataclass
class WebVitalsAuditReport:
    audit_id: str
    target_url: str
    browser_type: str
    device_emulation: str
    overall_performance_score: float
    overall_rating: VitalRating
    core_vitals: dict[str, WebVitalMetric]
    supplementary_vitals: dict[str, WebVitalMetric]
    blocking_resources: list[BlockingResource] = field(default_factory=list)
    optimization_recommendations: list[str] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "target_url": self.target_url,
            "browser_type": self.browser_type,
            "device_emulation": self.device_emulation,
            "overall_performance_score": round(self.overall_performance_score, 1),
            "overall_rating": self.overall_rating.value,
            "core_vitals": {k: v.to_dict() for k, v in self.core_vitals.items()},
            "supplementary_vitals": {k: v.to_dict() for k, v in self.supplementary_vitals.items()},
            "blocking_resources": [r.to_dict() for r in self.blocking_resources],
            "optimization_recommendations": self.optimization_recommendations,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


# 内存报告仓库
_WEB_VITALS_REPORTS: dict[str, WebVitalsAuditReport] = {}


def _rate_metric(
    value: float, good_threshold: float, poor_threshold: float, lower_is_better: bool = True
) -> VitalRating:
    """按 Google 官方标准评估单个指标评级。"""
    if lower_is_better:
        if value <= good_threshold:
            return VitalRating.GOOD
        if value <= poor_threshold:
            return VitalRating.NEEDS_IMPROVEMENT
        return VitalRating.POOR
    else:
        if value >= good_threshold:
            return VitalRating.GOOD
        if value >= poor_threshold:
            return VitalRating.NEEDS_IMPROVEMENT
        return VitalRating.POOR


def _metric_score_contribution(value: float, good_threshold: float, poor_threshold: float) -> float:
    """计算单个指标在 [0, 100] 分数区间的折算得分。"""
    if value <= good_threshold:
        return 100.0
    if value >= poor_threshold:
        return max(0.0, 50.0 - ((value - poor_threshold) / poor_threshold) * 50.0)
    # 在 [good, poor] 之间线性插值 90 -> 50
    ratio = (value - good_threshold) / (poor_threshold - good_threshold)
    return 90.0 - ratio * 40.0


def diagnose_web_vitals(
    target_url: str,
    lcp_ms: float = 2200.0,
    inp_ms: float = 120.0,
    cls_score: float = 0.05,
    fcp_ms: float = 1400.0,
    ttfb_ms: float = 350.0,
    tbt_ms: float = 150.0,
    raw_resources: list[dict[str, Any]] | None = None,
    browser_type: str = "chromium",
    device_emulation: str = "desktop",
) -> WebVitalsAuditReport:
    """核心诊断引擎：构建 Core Web Vitals 评估树，分析渲染阻断与优化建议。"""
    audit_id = f"audit_wv_{uuid.uuid4().hex[:12]}"

    # 1. 核心 Web Vitals (Core Web Vitals)
    core_vitals: dict[str, WebVitalMetric] = {
        "LCP": WebVitalMetric(
            name="Largest Contentful Paint (最大内容绘制)",
            value=lcp_ms,
            unit="ms",
            rating=_rate_metric(lcp_ms, 2500.0, 4000.0),
            good_threshold=2500.0,
            poor_threshold=4000.0,
            description="页面视口内最大文本块或图像绘制完成的时间，衡量主内容可见速度",
        ),
        "INP": WebVitalMetric(
            name="Interaction to Next Paint (交互到下次绘制延迟)",
            value=inp_ms,
            unit="ms",
            rating=_rate_metric(inp_ms, 200.0, 500.0),
            good_threshold=200.0,
            poor_threshold=500.0,
            description="衡量用户在页面交互操作后渲染下次绘制的整体延迟与响应流畅度",
        ),
        "CLS": WebVitalMetric(
            name="Cumulative Layout Shift (累积布局偏移)",
            value=cls_score,
            unit="score",
            rating=_rate_metric(cls_score, 0.1, 0.25),
            good_threshold=0.1,
            poor_threshold=0.25,
            description="页面生命周期内所有意外布局抖动的累积分数，衡量视觉稳定性",
        ),
    }

    # 2. 辅助关键性能指标 (Supplementary Vitals)
    supplementary_vitals: dict[str, WebVitalMetric] = {
        "FCP": WebVitalMetric(
            name="First Contentful Paint (首次内容绘制)",
            value=fcp_ms,
            unit="ms",
            rating=_rate_metric(fcp_ms, 1800.0, 3000.0),
            good_threshold=1800.0,
            poor_threshold=3000.0,
            description="浏览器首次渲染任何文本、图像或非空白 Canvas 的时间点",
        ),
        "TTFB": WebVitalMetric(
            name="Time to First Byte (首字节响应时间)",
            value=ttfb_ms,
            unit="ms",
            rating=_rate_metric(ttfb_ms, 800.0, 1800.0),
            good_threshold=800.0,
            poor_threshold=1800.0,
            description="浏览器发出请求到接收到服务器首个字节数据的等待网络时延",
        ),
        "TBT": WebVitalMetric(
            name="Total Blocking Time (总阻塞时间)",
            value=tbt_ms,
            unit="ms",
            rating=_rate_metric(tbt_ms, 200.0, 600.0),
            good_threshold=200.0,
            poor_threshold=600.0,
            description="FCP 到 TTI 之间所有超过 50ms 的长任务阻塞时间累加总和",
        ),
    }

    # 3. 综合性能加权计算 (Lighthouse 标准权重模型)
    # LCP 25%, TBT 30%, CLS 15%, FCP 10%, INP 10%, TTFB 10%
    score_lcp = _metric_score_contribution(lcp_ms, 2500.0, 4000.0)
    score_tbt = _metric_score_contribution(tbt_ms, 200.0, 600.0)
    score_cls = _metric_score_contribution(cls_score, 0.1, 0.25)
    score_fcp = _metric_score_contribution(fcp_ms, 1800.0, 3000.0)
    score_inp = _metric_score_contribution(inp_ms, 200.0, 500.0)
    score_ttfb = _metric_score_contribution(ttfb_ms, 800.0, 1800.0)

    composite_score = (
        score_lcp * 0.25 + score_tbt * 0.30 + score_cls * 0.15 + score_fcp * 0.10 + score_inp * 0.10 + score_ttfb * 0.10
    )

    overall_rating = (
        VitalRating.GOOD
        if composite_score >= 85.0
        else VitalRating.NEEDS_IMPROVEMENT
        if composite_score >= 60.0
        else VitalRating.POOR
    )

    # 4. 分析渲染阻断资源
    blocking_resources: list[BlockingResource] = []
    if raw_resources:
        for r in raw_resources:
            duration = float(r.get("duration_ms", 0.0))
            size = float(r.get("transfer_size_kb", 0.0))
            rtype = str(r.get("resource_type", "script"))
            impact = "high" if duration > 300 or size > 500 else "medium" if duration > 100 or size > 200 else "low"
            sugg = (
                f"建议对 {rtype} 资源进行异步加载 (async/defer) 或代码分包"
                if rtype == "script"
                else "建议提取关键 CSS 内联，其余延迟加载"
            )
            blocking_resources.append(
                BlockingResource(
                    url=str(r.get("url", "")),
                    resource_type=rtype,
                    duration_ms=duration,
                    transfer_size_kb=size,
                    impact=impact,
                    suggestion=sugg,
                )
            )

    # 5. 生成针对性工程优化建议
    recommendations: list[str] = []
    if core_vitals["LCP"].rating != VitalRating.GOOD:
        recommendations.append(
            f"LCP 耗时达到 {lcp_ms}ms（建议 ≤2500ms），优先优化首屏首图预加载（<link rel='preload'>）并采用 WebP 压缩。"
        )
    if core_vitals["CLS"].rating != VitalRating.GOOD:
        recommendations.append(
            f"CLS 布局偏移分数为 {cls_score}（建议 ≤0.1），请为首屏动态图像、广告容器与骨架屏提前声明确切 width/height 尺寸。"
        )
    if core_vitals["INP"].rating != VitalRating.GOOD:
        recommendations.append(
            f"INP 交互延迟为 {inp_ms}ms（建议 ≤200ms），建议将主线程长任务拆分至 Web Worker 或 requestIdleCallback。"
        )
    if supplementary_vitals["TTFB"].rating != VitalRating.GOOD:
        recommendations.append(
            f"TTFB 首字节耗时达 {ttfb_ms}ms，建议排查服务端 SSR 渲染瓶颈或开启 CDN 全球边缘缓存加速。"
        )

    if not recommendations:
        recommendations.append("页面 Core Web Vitals 各项体验指标表现卓越，全维度均严格处于 Google 推荐绿色优秀区间！")

    report = WebVitalsAuditReport(
        audit_id=audit_id,
        target_url=target_url,
        browser_type=browser_type,
        device_emulation=device_emulation,
        overall_performance_score=composite_score,
        overall_rating=overall_rating,
        core_vitals=core_vitals,
        supplementary_vitals=supplementary_vitals,
        blocking_resources=blocking_resources,
        optimization_recommendations=recommendations,
    )

    _WEB_VITALS_REPORTS[audit_id] = report
    logger.info(
        "Diagnosed Web Vitals audit_id=%s url=%s score=%.1f rating=%s",
        audit_id,
        target_url,
        composite_score,
        overall_rating.value,
    )
    return report


def get_web_vitals_report(audit_id: str) -> WebVitalsAuditReport | None:
    """获取指定 Web Vitals 诊断报告。"""
    return _WEB_VITALS_REPORTS.get(audit_id)


def list_web_vitals_reports() -> list[WebVitalsAuditReport]:
    """查询历史 Web Vitals 诊断报告列表。"""
    return list(_WEB_VITALS_REPORTS.values())


def reset_web_vitals_registry() -> None:
    """供单元测试清理状态使用。"""
    _WEB_VITALS_REPORTS.clear()
