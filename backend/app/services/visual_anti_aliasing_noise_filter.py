"""动态忽略区域掩码与抗锯齿渲染微噪声过滤去噪器 (T1.2)。"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PixelNoiseType(str, Enum):
    """像素噪声分类。"""

    GENUINE_STRUCTURAL_DIFF = "GENUINE_STRUCTURAL_DIFF"  # 真实结构破坏差异
    MASKED_DYNAMIC_REGION = "MASKED_DYNAMIC_REGION"  # 位于动态忽略掩码区
    ANTI_ALIASING_EDGE = "ANTI_ALIASING_EDGE"  # 字体/图形抗锯齿微过渡噪点
    ISOLATED_SINGLE_PIXEL = "ISOLATED_SINGLE_PIXEL"  # 孤立单像素噪点


@dataclass
class MaskRegion:
    """动态忽略掩码区域矩形。"""

    region_id: str
    name: str
    x: int
    y: int
    width: int
    height: int
    reason: str = "动态时间戳或轮播组件"

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.width and self.y <= py < self.y + self.height

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "reason": self.reason,
        }


@dataclass
class RawDiffPixel:
    """单个差异像素点坐标与色差。"""

    x: int
    y: int
    delta_e: float = 15.0  # 色差值 (Delta E)
    is_edge: bool = False  # 是否为图形边缘轮廓点


@dataclass
class NoiseFilterAuditReport:
    """抗锯齿与掩码去噪审计报告。"""

    report_id: str
    target_name: str
    raw_diff_pixels_count: int
    mask_filtered_count: int
    anti_aliasing_filtered_count: int
    isolated_noise_filtered_count: int
    effective_structural_diff_count: int
    noise_reduction_ratio_pct: float
    raw_ssim_score: float
    denoised_ssim_score: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "target_name": self.target_name,
            "raw_diff_pixels_count": self.raw_diff_pixels_count,
            "mask_filtered_count": self.mask_filtered_count,
            "anti_aliasing_filtered_count": self.anti_aliasing_filtered_count,
            "isolated_noise_filtered_count": self.isolated_noise_filtered_count,
            "effective_structural_diff_count": self.effective_structural_diff_count,
            "noise_reduction_ratio_pct": round(self.noise_reduction_ratio_pct, 1),
            "raw_ssim_score": round(self.raw_ssim_score, 4),
            "denoised_ssim_score": round(self.denoised_ssim_score, 4),
            "created_at": self.created_at.isoformat(),
        }


# 全局掩码库与报告存储
_REGISTERED_MASKS: dict[str, MaskRegion] = {}
_NOISE_FILTER_REPORTS: dict[str, NoiseFilterAuditReport] = {}


def clear_noise_filter_store() -> None:
    """清空掩码库与报告仓库（单测专用）。"""
    _REGISTERED_MASKS.clear()
    _NOISE_FILTER_REPORTS.clear()


def register_mask_region(
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    reason: str = "动态时间戳或轮播组件",
) -> MaskRegion:
    """登记常用动态忽略掩码区域。"""
    reg_id = f"mask_{uuid.uuid4().hex[:6]}"
    region = MaskRegion(
        region_id=reg_id,
        name=name,
        x=x,
        y=y,
        width=width,
        height=height,
        reason=reason,
    )
    _REGISTERED_MASKS[reg_id] = region
    return region


def list_mask_regions() -> list[dict[str, Any]]:
    """获取所有已注册的掩码区域。"""
    return [m.to_dict() for m in _REGISTERED_MASKS.values()]


def filter_visual_noise_and_mask(
    target_name: str,
    raw_pixels: list[dict[str, Any]],
    active_mask_ids: list[str] | None = None,
    extra_masks: list[dict[str, Any]] | None = None,
    canvas_width: int = 1920,
    canvas_height: int = 1080,
    anti_aliasing_threshold_delta_e: float = 20.0,
) -> NoiseFilterAuditReport:
    """执行掩码遮盖、抗锯齿边缘过滤与孤立单像素噪点消除。"""
    # 汇总生效的掩码集合
    masks: list[MaskRegion] = []
    if active_mask_ids:
        for mid in active_mask_ids:
            if mid in _REGISTERED_MASKS:
                masks.append(_REGISTERED_MASKS[mid])
    else:
        masks.extend(_REGISTERED_MASKS.values())

    if extra_masks:
        for em in extra_masks:
            masks.append(
                MaskRegion(
                    region_id=f"extra_{uuid.uuid4().hex[:4]}",
                    name=em.get("name", "extra_mask"),
                    x=em.get("x", 0),
                    y=em.get("y", 0),
                    width=em.get("width", 10),
                    height=em.get("height", 10),
                    reason=em.get("reason", "即时临时掩码"),
                )
            )

    parsed_pixels = [
        RawDiffPixel(
            x=p.get("x", 0),
            y=p.get("y", 0),
            delta_e=float(p.get("delta_e", 15.0)),
            is_edge=bool(p.get("is_edge", False)),
        )
        for p in raw_pixels
    ]

    total_raw = len(parsed_pixels)
    pixel_set = {(p.x, p.y) for p in parsed_pixels}

    mask_filtered = 0
    aa_filtered = 0
    isolated_filtered = 0
    genuine_diffs: list[RawDiffPixel] = []

    for p in parsed_pixels:
        # 1. 检查是否落在掩码区域内
        is_masked = False
        for m in masks:
            if m.contains(p.x, p.y):
                is_masked = True
                break
        if is_masked:
            mask_filtered += 1
            continue

        # 2. 检查是否为抗锯齿边缘次像素微噪点 (色差较小且处于轮廓边缘)
        if p.is_edge and p.delta_e <= anti_aliasing_threshold_delta_e:
            aa_filtered += 1
            continue

        # 3. 检查是否为周围 8 邻域无任何差异点的孤立单像素噪点
        neighbors = [
            (p.x - 1, p.y - 1),
            (p.x, p.y - 1),
            (p.x + 1, p.y - 1),
            (p.x - 1, p.y),
            (p.x + 1, p.y),
            (p.x - 1, p.y + 1),
            (p.x, p.y + 1),
            (p.x + 1, p.y + 1),
        ]
        has_neighbor_diff = any(n in pixel_set for n in neighbors)
        if not has_neighbor_diff and p.delta_e <= anti_aliasing_threshold_delta_e:
            isolated_filtered += 1
            continue

        genuine_diffs.append(p)

    total_filtered = mask_filtered + aa_filtered + isolated_filtered
    effective_count = len(genuine_diffs)
    reduction_pct = (total_filtered / total_raw * 100.0) if total_raw > 0 else 0.0

    total_canvas_pixels = canvas_width * canvas_height
    raw_loss = math.pow(total_raw / total_canvas_pixels, 0.7) if total_canvas_pixels > 0 else 0.0
    denoised_loss = math.pow(effective_count / total_canvas_pixels, 0.7) if total_canvas_pixels > 0 else 0.0

    raw_ssim = max(0.0, 1.0 - raw_loss)
    denoised_ssim = max(0.0, 1.0 - denoised_loss)

    now = datetime.now(timezone.utc)
    report_id = f"filter_{target_name[:12]}_{int(now.timestamp())}"
    report = NoiseFilterAuditReport(
        report_id=report_id,
        target_name=target_name,
        raw_diff_pixels_count=total_raw,
        mask_filtered_count=mask_filtered,
        anti_aliasing_filtered_count=aa_filtered,
        isolated_noise_filtered_count=isolated_filtered,
        effective_structural_diff_count=effective_count,
        noise_reduction_ratio_pct=reduction_pct,
        raw_ssim_score=raw_ssim,
        denoised_ssim_score=denoised_ssim,
        created_at=now,
    )
    _NOISE_FILTER_REPORTS[report_id] = report
    return report


def get_noise_filter_report(report_id: str) -> NoiseFilterAuditReport | None:
    """按 ID 查询去噪审计报告。"""
    return _NOISE_FILTER_REPORTS.get(report_id)


def list_noise_filter_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史去噪审计报告列表。"""
    reports = list(reversed(list(_NOISE_FILTER_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
