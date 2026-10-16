"""多视口像素级 SSIM 结构相似度比对单元测试 (T1.1)。"""

from __future__ import annotations

import pytest
from app.services.visual_pixel_ssim_diff_engine import (
    ViewportType,
    VisualMatchStatus,
    calculate_single_viewport_ssim,
    clear_visual_diff_store,
    compare_multi_viewports_visual_diff,
    get_visual_diff_report,
    list_visual_diff_reports,
)


@pytest.fixture(autouse=True)
def _reset_visual_state():
    clear_visual_diff_store()
    yield
    clear_visual_diff_store()


def test_calculate_single_viewport_perfect_match():
    """测试完全匹配时 SSIM 达到 1.0 与 PERFECT_MATCH 状态。"""
    res = calculate_single_viewport_ssim(
        viewport=ViewportType.DESKTOP,
        simulated_diff_pixels=0,
    )
    assert res.viewport == ViewportType.DESKTOP
    assert res.width == 1920
    assert res.height == 1080
    assert res.ssim_score == 1.0
    assert res.mismatch_pixels_count == 0
    assert res.status == VisualMatchStatus.PERFECT_MATCH
    assert res.is_passed is True
    assert len(res.diff_boxes) == 0


def test_calculate_single_viewport_acceptable_and_blocked():
    """测试微小漂移放行与显著像素突变阻断。"""
    # 微小抗锯齿差异 (50个像素)，仍符合 >= 0.98 阈值
    drift_res = calculate_single_viewport_ssim(
        viewport=ViewportType.MOBILE,
        simulated_diff_pixels=50,
        tolerance_threshold=0.98,
    )
    assert drift_res.is_passed is True
    assert drift_res.status == VisualMatchStatus.ACCEPTABLE_DRIFT
    assert len(drift_res.diff_boxes) >= 1

    # 严重视觉破坏 (35000个像素)，被阻断
    blocked_res = calculate_single_viewport_ssim(
        viewport=ViewportType.MOBILE,
        simulated_diff_pixels=35000,
        tolerance_threshold=0.98,
    )
    assert blocked_res.is_passed is False
    assert blocked_res.status == VisualMatchStatus.REGRESSION_BLOCKED


def test_compare_multi_viewports_visual_diff_flow():
    """测试跨桌面、平板、手机多视口综合比对。"""
    diff_configs = {
        "DESKTOP": 0,  # 桌面端完全通过
        "TABLET": 30,  # 平板端微小差异放行
        "MOBILE": 40000,  # 移动端严重错位阻断
    }

    report = compare_multi_viewports_visual_diff(
        snapshot_name="product_checkout_page",
        viewports=["DESKTOP", "TABLET", "MOBILE"],
        tolerance_threshold=0.98,
        simulated_viewport_diffs=diff_configs,
    )

    assert report.snapshot_name == "product_checkout_page"
    assert report.total_viewports_tested == 3
    assert report.overall_passed is False  # 移动端阻断导致总体阻断
    assert report.overall_status == VisualMatchStatus.REGRESSION_BLOCKED
    assert len(report.viewport_results) == 3

    # 验证持久化
    saved = get_visual_diff_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_visual_diff_reports()) == 1
