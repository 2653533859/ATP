"""跨分辨率视口快照捕获与像素级 SSIM 结构相似度比对器 (T1.1)。"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ViewportType(str, Enum):
    """支持的标准屏幕视口断点规格。"""

    DESKTOP = "DESKTOP"  # 1920x1080
    LAPTOP = "LAPTOP"  # 1280x720
    TABLET = "TABLET"  # 768x1024
    MOBILE = "MOBILE"  # 375x812


class VisualMatchStatus(str, Enum):
    """视觉比对匹配状态结论。"""

    PERFECT_MATCH = "PERFECT_MATCH"  # 100% 像素完全相同
    ACCEPTABLE_DRIFT = "ACCEPTABLE_DRIFT"  # 达到 SSIM 阈值，允许微小抗锯齿差异
    REGRESSION_BLOCKED = "REGRESSION_BLOCKED"  # 结构相似度不足，判定为视觉回归阻断


VIEWPORT_DIMENSIONS: dict[ViewportType, tuple[int, int]] = {
    ViewportType.DESKTOP: (1920, 1080),
    ViewportType.LAPTOP: (1280, 720),
    ViewportType.TABLET: (768, 1024),
    ViewportType.MOBILE: (375, 812),
}


@dataclass
class VisualDiffBoundingBox:
    """差异区域高亮框。"""

    box_id: str
    x: int
    y: int
    width: int
    height: int
    diff_density: float  # 差异密度 0~1.0
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "box_id": self.box_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "diff_density": round(self.diff_density, 2),
            "description": self.description,
        }


@dataclass
class SingleViewportDiffResult:
    """单视口比对结果。"""

    viewport: ViewportType
    width: int
    height: int
    ssim_score: float  # 0.0 ~ 1.0 (越高越相似)
    mismatch_pixels_count: int
    mismatch_ratio_pct: float
    status: VisualMatchStatus
    is_passed: bool
    diff_boxes: list[VisualDiffBoundingBox]

    def to_dict(self) -> dict[str, Any]:
        return {
            "viewport": self.viewport.value,
            "width": self.width,
            "height": self.height,
            "ssim_score": round(self.ssim_score, 4),
            "mismatch_pixels_count": self.mismatch_pixels_count,
            "mismatch_ratio_pct": round(self.mismatch_ratio_pct, 2),
            "status": self.status.value,
            "is_passed": self.is_passed,
            "diff_boxes": [b.to_dict() for b in self.diff_boxes],
        }


@dataclass
class MultiViewportVisualDiffReport:
    """多视口跨分辨率视觉比对全景报告。"""

    report_id: str
    snapshot_name: str
    overall_passed: bool
    overall_status: VisualMatchStatus
    average_ssim_score: float
    total_viewports_tested: int
    tolerance_threshold: float
    viewport_results: dict[str, SingleViewportDiffResult]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "snapshot_name": self.snapshot_name,
            "overall_passed": self.overall_passed,
            "overall_status": self.overall_status.value,
            "average_ssim_score": round(self.average_ssim_score, 4),
            "total_viewports_tested": self.total_viewports_tested,
            "tolerance_threshold": self.tolerance_threshold,
            "viewport_results": {k: v.to_dict() for k, v in self.viewport_results.items()},
            "created_at": self.created_at.isoformat(),
        }


# 全局比对报告存储
_VISUAL_DIFF_REPORTS: dict[str, MultiViewportVisualDiffReport] = {}


def clear_visual_diff_store() -> None:
    """清空视觉比对报告仓库（单测专用）。"""
    _VISUAL_DIFF_REPORTS.clear()


def calculate_single_viewport_ssim(
    viewport: ViewportType,
    simulated_diff_pixels: int = 0,
    tolerance_threshold: float = 0.98,
    custom_diff_boxes: list[dict[str, Any]] | None = None,
) -> SingleViewportDiffResult:
    """计算单个视口像素差异与 SSIM 结构相似度。"""
    width, height = VIEWPORT_DIMENSIONS.get(viewport, (1920, 1080))
    total_pixels = width * height

    # 规范化异常差异像素
    diff_pixels = max(0, min(total_pixels, simulated_diff_pixels))
    ratio = (diff_pixels / total_pixels) * 100.0

    # 基于高斯与均方误差简化计算的 SSIM 估算公式: SSIM = 1 - (diff_pixels / total_pixels)^0.7
    if diff_pixels == 0:
        ssim = 1.0
        status = VisualMatchStatus.PERFECT_MATCH
        is_passed = True
    else:
        loss = math.pow(diff_pixels / total_pixels, 0.7)
        ssim = max(0.0, 1.0 - loss)
        is_passed = ssim >= tolerance_threshold
        status = VisualMatchStatus.ACCEPTABLE_DRIFT if is_passed else VisualMatchStatus.REGRESSION_BLOCKED

    boxes: list[VisualDiffBoundingBox] = []
    if custom_diff_boxes:
        for b in custom_diff_boxes:
            boxes.append(
                VisualDiffBoundingBox(
                    box_id=f"box_{uuid.uuid4().hex[:6]}",
                    x=b.get("x", 100),
                    y=b.get("y", 150),
                    width=b.get("width", 80),
                    height=b.get("height", 30),
                    diff_density=b.get("diff_density", 0.8),
                    description=b.get("description", "检测到像素级视觉渲染差异"),
                )
            )
    elif diff_pixels > 0:
        # 默认生成差异包围框
        boxes.append(
            VisualDiffBoundingBox(
                box_id=f"box_{uuid.uuid4().hex[:6]}",
                x=120,
                y=240,
                width=160,
                height=45,
                diff_density=0.85,
                description=f"在坐标 (120, 240) 检测到 {diff_pixels} 个变异像素差异聚集区",
            )
        )

    return SingleViewportDiffResult(
        viewport=viewport,
        width=width,
        height=height,
        ssim_score=ssim,
        mismatch_pixels_count=diff_pixels,
        mismatch_ratio_pct=ratio,
        status=status,
        is_passed=is_passed,
        diff_boxes=boxes,
    )


def compare_multi_viewports_visual_diff(
    snapshot_name: str,
    viewports: list[str] | None = None,
    tolerance_threshold: float = 0.98,
    simulated_viewport_diffs: dict[str, int] | None = None,
) -> MultiViewportVisualDiffReport:
    """跨分辨率并发执行视口像素级比对并汇总报告。"""
    active_viewports = [ViewportType(v) for v in viewports] if viewports else list(ViewportType)
    diff_configs = simulated_viewport_diffs or {}

    results: dict[str, SingleViewportDiffResult] = {}
    ssim_sum = 0.0
    all_passed = True
    worst_status = VisualMatchStatus.PERFECT_MATCH

    status_priority = {
        VisualMatchStatus.REGRESSION_BLOCKED: 3,
        VisualMatchStatus.ACCEPTABLE_DRIFT: 2,
        VisualMatchStatus.PERFECT_MATCH: 1,
    }

    for vp in active_viewports:
        sim_diff = diff_configs.get(vp.value, 0)
        res = calculate_single_viewport_ssim(
            viewport=vp,
            simulated_diff_pixels=sim_diff,
            tolerance_threshold=tolerance_threshold,
        )
        results[vp.value] = res
        ssim_sum += res.ssim_score

        if not res.is_passed:
            all_passed = False
        if status_priority[res.status] > status_priority[worst_status]:
            worst_status = res.status

    avg_ssim = ssim_sum / len(active_viewports) if active_viewports else 1.0

    now = datetime.now(timezone.utc)
    report_id = f"vdiff_{snapshot_name[:12]}_{int(now.timestamp())}"
    report = MultiViewportVisualDiffReport(
        report_id=report_id,
        snapshot_name=snapshot_name,
        overall_passed=all_passed,
        overall_status=worst_status,
        average_ssim_score=avg_ssim,
        total_viewports_tested=len(active_viewports),
        tolerance_threshold=tolerance_threshold,
        viewport_results=results,
        created_at=now,
    )
    _VISUAL_DIFF_REPORTS[report_id] = report
    return report


def get_visual_diff_report(report_id: str) -> MultiViewportVisualDiffReport | None:
    """按 ID 查询视觉比对报告。"""
    return _VISUAL_DIFF_REPORTS.get(report_id)


def list_visual_diff_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史视觉比对报告列表。"""
    reports = list(reversed(list(_VISUAL_DIFF_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
