"""跨视口文本截断、元素重叠与布局溢出碰撞检测单元测试 (T2.2)。"""

from __future__ import annotations

import pytest
from app.services.ui_layout_overflow_collision_detector import (
    LayoutDefectSeverity,
    LayoutDefectType,
    clear_layout_defect_store,
    detect_layout_defects,
    get_layout_defect_report,
    list_layout_defect_reports,
)


@pytest.fixture(autouse=True)
def _reset_layout_state():
    clear_layout_defect_store()
    yield
    clear_layout_defect_store()


def test_detect_layout_defects_perfect_clean():
    """测试完全无碰撞重叠且未溢出的整洁响应式布局。"""
    elements = [
        {"element_id": "header", "x": 0, "y": 0, "width": 375, "height": 60},
        {"element_id": "content", "x": 16, "y": 70, "width": 343, "height": 400},
        {"element_id": "footer", "x": 0, "y": 480, "width": 375, "height": 50},
    ]

    report = detect_layout_defects(
        page_name="clean_mobile_page",
        viewport_width=375,
        viewport_height=812,
        elements=elements,
    )

    assert report.total_elements_checked == 3
    assert report.total_defects_count == 0
    assert report.layout_integrity_score_pct == 100.0


def test_detect_layout_defects_collision_and_overflow():
    """测试精确探查 AABB 元素重叠、视口水平溢出与文本截断。"""
    elements = [
        # 1. 元素重叠: 两个按钮在同一空间产生碰撞 (x: 100~180, y: 200~240)
        {"element_id": "btn_confirm", "tag_name": "button", "x": 100, "y": 200, "width": 100, "height": 40},
        {"element_id": "btn_cancel", "tag_name": "button", "x": 120, "y": 210, "width": 100, "height": 40},
        # 2. 水平溢出: 右边界超出 375px (x=300 + width=120 = 420 > 375)
        {"element_id": "wide_banner", "tag_name": "img", "x": 300, "y": 50, "width": 120, "height": 60},
        # 3. 文本截断: scroll_width > client_width
        {
            "element_id": "product_title",
            "tag_name": "span",
            "x": 16,
            "y": 300,
            "width": 150,
            "height": 20,
            "scroll_width": 260,
            "text_content": "超长商品促销标题名称溢出容器省略号截断",
        },
    ]

    report = detect_layout_defects(
        page_name="defective_mobile_page",
        viewport_width=375,
        viewport_height=812,
        elements=elements,
    )

    assert report.total_elements_checked == 4
    assert report.total_defects_count == 3
    assert report.collision_count == 1
    assert report.overflow_count == 1
    assert report.truncation_count == 1
    assert report.layout_integrity_score_pct < 60.0

    types_set = {d.defect_type for d in report.defects}
    assert LayoutDefectType.ELEMENT_COLLISION_OVERLAP in types_set
    assert LayoutDefectType.VIEWPORT_HORIZONTAL_OVERFLOW in types_set
    assert LayoutDefectType.TEXT_TRUNCATION_OVERFLOW in types_set

    # 验证按钮重叠评级为 CRITICAL
    coll_defect = next(d for d in report.defects if d.defect_type == LayoutDefectType.ELEMENT_COLLISION_OVERLAP)
    assert coll_defect.severity == LayoutDefectSeverity.CRITICAL


def test_list_and_get_layout_reports():
    """测试布局报告查询与持久化。"""
    elements = [{"element_id": "b1", "x": 0, "y": 0, "width": 100, "height": 50}]
    rep = detect_layout_defects("test_p", 375, 812, elements)

    saved = get_layout_defect_report(rep.report_id)
    assert saved is not None
    assert saved.report_id == rep.report_id

    reports = list_layout_defect_reports()
    assert len(reports) == 1
