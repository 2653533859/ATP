"""动态忽略掩码与抗锯齿微噪声过滤单元测试 (T1.2)。"""

from __future__ import annotations

import pytest
from app.services.visual_anti_aliasing_noise_filter import (
    clear_noise_filter_store,
    filter_visual_noise_and_mask,
    get_noise_filter_report,
    list_mask_regions,
    list_noise_filter_reports,
    register_mask_region,
)


@pytest.fixture(autouse=True)
def _reset_filter_state():
    clear_noise_filter_store()
    yield
    clear_noise_filter_store()


def test_filter_visual_noise_with_masks_and_isolated():
    """测试动态区域掩码过滤与孤立抗锯齿单像素噪点消除。"""
    # 注册一个右上角时间戳掩码 (x: 1800, y: 10, width: 100, height: 30)
    register_mask_region(name="header_time", x=1800, y=10, width=100, height=30)

    raw_pixels = [
        # 1. 落在掩码区的时间戳噪点 (1850, 20)
        {"x": 1850, "y": 20, "delta_e": 35.0, "is_edge": False},
        {"x": 1860, "y": 22, "delta_e": 28.0, "is_edge": False},
        # 2. 抗锯齿边缘微噪点 (色差较小 12.0 <= 20.0，且 is_edge 为 True)
        {"x": 500, "y": 300, "delta_e": 12.0, "is_edge": True},
        # 3. 孤立噪点 (周围无任何邻域差异，色差较小)
        {"x": 100, "y": 100, "delta_e": 15.0, "is_edge": False},
        # 4. 真实的业务有效结构差异 (聚集在一起，且色差大)
        {"x": 300, "y": 400, "delta_e": 45.0, "is_edge": False},
        {"x": 301, "y": 400, "delta_e": 48.0, "is_edge": False},
        {"x": 300, "y": 401, "delta_e": 50.0, "is_edge": False},
    ]

    report = filter_visual_noise_and_mask(
        target_name="dashboard_page",
        raw_pixels=raw_pixels,
    )

    assert report.raw_diff_pixels_count == 7
    assert report.mask_filtered_count == 2
    assert report.anti_aliasing_filtered_count == 1
    assert report.isolated_noise_filtered_count == 1
    assert report.effective_structural_diff_count == 3  # 仅保留真实结构差异 3 个像素
    assert report.noise_reduction_ratio_pct > 50.0
    assert report.denoised_ssim_score > report.raw_ssim_score

    # 验证持久化存储
    saved = get_noise_filter_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_noise_filter_reports()) == 1


def test_register_and_list_mask_regions():
    """测试掩码区域登记与列表查询。"""
    m1 = register_mask_region(name="banner_carousel", x=0, y=100, width=1920, height=400)
    assert m1.name == "banner_carousel"
    assert m1.contains(100, 200) is True
    assert m1.contains(100, 600) is False

    masks = list_mask_regions()
    assert len(masks) == 1
