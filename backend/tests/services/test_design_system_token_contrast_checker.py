"""品牌设计规范 Token 与色彩对比度检查单元测试 (T2.3)。"""

from __future__ import annotations

import pytest
from app.services.design_system_token_contrast_checker import (
    TokenViolationType,
    audit_design_tokens_and_contrast,
    calculate_contrast_ratio,
    clear_design_audit_store,
    get_design_system_report,
    hex_to_rgb,
    list_design_system_reports,
)


@pytest.fixture(autouse=True)
def _reset_design_state():
    clear_design_audit_store()
    yield
    clear_design_audit_store()


def test_calculate_contrast_ratio_black_white():
    """测试黑白对比度达到最高 21:1。"""
    ratio = calculate_contrast_ratio("#000000", "#FFFFFF")
    assert round(ratio, 1) == 21.0

    # 相同颜色对比度 1:1
    same_ratio = calculate_contrast_ratio("#FFFFFF", "#FFFFFF")
    assert round(same_ratio, 1) == 1.0


def test_audit_design_tokens_detect_low_contrast_and_off_grid():
    """测试探测低对比度 (如浅灰配白底) 与字号间距偏离网格 Token。"""
    elements = [
        # 1. 低对比度文本: #94A3B8 (slate-400) on #FFFFFF -> 对比度仅约 2.3:1 < 4.5:1
        {
            "element_id": "sub_text",
            "color": "#94A3B8",
            "background_color": "#FFFFFF",
            "font_size": 13.5,  # 偏离标准字阶
            "padding": 19.0,  # 偏离 4px 网格
            "border_radius": 7.0,  # 偏离标准圆角
        },
        # 2. 合规元素: #0F172A (slate-900) on #FFFFFF -> 对比度 > 15:1，字号 14px，间距 16px，圆角 6px
        {
            "element_id": "primary_btn",
            "color": "#0F172A",
            "background_color": "#FFFFFF",
            "font_size": 14.0,
            "padding": 16.0,
            "border_radius": 6.0,
        },
    ]

    report = audit_design_tokens_and_contrast(target_name="test_page", elements=elements)
    assert report.total_elements_checked == 2
    assert report.total_violations_count == 4  # 对比度不足 + 字号偏离 + 间距偏离 + 圆角偏离
    assert report.contrast_fails_count == 1
    assert report.token_discrepancies_count == 3
    assert report.is_wcag_aa_compliant is False

    types = {v.violation_type for v in report.violations}
    assert TokenViolationType.CONTRAST_RATIO_FAIL in types
    assert TokenViolationType.FONT_SIZE_OFF_GRID in types
    assert TokenViolationType.SPACING_OFF_GRID in types
    assert TokenViolationType.BORDER_RADIUS_OFF_GRID in types


def test_hex_to_rgb_and_reports_persistence():
    """测试 HEX 解析与报告持久化。"""
    assert hex_to_rgb("#FFF") == (255, 255, 255)
    assert hex_to_rgb("#000000") == (0, 0, 0)

    report = audit_design_tokens_and_contrast(
        target_name="clean_page",
        elements=[{"element_id": "ok_el", "color": "#000", "background_color": "#FFF"}],
    )
    assert report.is_wcag_aa_compliant is True

    saved = get_design_system_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_design_system_reports()) == 1
