"""色盲/色弱多模态视觉感知模拟与分类器单元测试 (T3.3)。"""

from __future__ import annotations

import pytest
from app.services.color_blindness_simulation_classifier import (
    CvdViolationType,
    audit_color_blindness_accessibility,
    clear_cvd_report_store,
    color_distance,
    get_color_blindness_report,
    list_color_blindness_reports,
    parse_hex_color,
    rgb_to_hex,
    simulate_color_vision_deficiency,
)


@pytest.fixture(autouse=True)
def _reset_cvd_state():
    clear_cvd_report_store()
    yield
    clear_cvd_report_store()


def test_simulate_color_vision_deficiency_channels():
    """测试将纯红、纯绿投影到色盲空间。"""
    # 纯红 #FF0000 -> 全色盲纯灰度
    red_sim = simulate_color_vision_deficiency("#FF0000")
    assert red_sim.original_hex == "#FF0000"
    assert red_sim.achromatopsia_hex == "#363636"  # 0.2126 * 255 = ~54.2 = 0x36

    # 纯绿 #00FF00
    green_sim = simulate_color_vision_deficiency("#00FF00")
    assert green_sim.original_hex == "#00FF00"
    assert green_sim.achromatopsia_hex == "#B6B6B6"  # 0.7152 * 255 = ~182.4 = 0xB6


def test_audit_color_blindness_detect_sole_color_and_confusion():
    """测试探测唯一色彩指示器缺陷 (WCAG 1.4.1) 与红绿状态混淆。"""
    indicators = [
        # 1. 仅靠绿点表示成功 (无文字、无图标) -> 违规
        {
            "element_id": "dot_success",
            "color_hex": "#22C55E",
            "has_text": False,
            "has_icon": False,
            "status_meaning": "success",
        },
        # 2. 仅靠红点表示失败 (无文字、无图标) -> 违规且与绿点混淆
        {
            "element_id": "dot_failure",
            "color_hex": "#EF4444",
            "has_text": False,
            "has_icon": False,
            "status_meaning": "failure",
        },
    ]

    report = audit_color_blindness_accessibility(component_or_page="run_status_panel", status_indicators=indicators)
    assert report.total_indicators_checked == 2
    assert report.total_violations_count >= 2
    assert report.critical_count >= 2
    assert report.is_wcag_1_4_1_compliant is False

    v_types = {v.violation_type for v in report.violations}
    assert CvdViolationType.SOLE_COLOR_INDICATOR in v_types


def test_audit_color_blindness_fully_accessible():
    """测试具备多重编码 (文字 + 图标) 的无障碍组件。"""
    indicators = [
        {
            "element_id": "tag_success",
            "color_hex": "#22C55E",
            "has_text": True,
            "has_icon": True,
            "status_meaning": "success",
        },
        {
            "element_id": "tag_failure",
            "color_hex": "#EF4444",
            "has_text": True,
            "has_icon": True,
            "status_meaning": "failure",
        },
    ]

    report = audit_color_blindness_accessibility(component_or_page="accessible_badge", status_indicators=indicators)
    assert report.total_violations_count == 0
    assert report.critical_count == 0
    assert report.is_wcag_1_4_1_compliant is True
    assert report.cvd_accessibility_score_pct == 100.0

    saved = get_color_blindness_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_color_blindness_reports()) == 1


def test_color_distance_and_helpers():
    """测试辅助工具函数。"""
    assert parse_hex_color("#FFF") == (255, 255, 255)
    assert rgb_to_hex(255.0, 0.0, 0.0) == "#FF0000"
    dist = color_distance("#000000", "#FFFFFF")
    assert round(dist, 1) > 400.0
