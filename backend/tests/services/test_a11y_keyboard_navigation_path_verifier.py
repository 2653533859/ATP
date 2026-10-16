"""键盘导航流转与焦点可达性单元测试 (T3.2)。"""

from __future__ import annotations

import pytest
from app.services.a11y_keyboard_navigation_path_verifier import (
    KeyboardDefectType,
    clear_keyboard_nav_store,
    get_keyboard_nav_report,
    list_keyboard_nav_reports,
    simulate_keyboard_navigation,
)


@pytest.fixture(autouse=True)
def _reset_keyboard_state():
    clear_keyboard_nav_store()
    yield
    clear_keyboard_nav_store()


def test_simulate_keyboard_navigation_with_defects():
    """测试探测焦点死锁、剥离焦点样式、关键按钮不可达、正tabindex与缺skip link。"""
    elements = [
        # 1. 设置正 tabindex (破坏顺序)
        {
            "element_id": "search_input",
            "tag_name": "input",
            "tabindex": 2,
            "has_focus_ring": True,
        },
        # 2. 剥离了焦点样式 (outline: none)
        {
            "element_id": "nav_link",
            "tag_name": "a",
            "tabindex": 0,
            "has_focus_ring": False,
        },
        # 3. 产生键盘死锁 (Focus Trap)
        {
            "element_id": "modal_confirm_btn",
            "tag_name": "button",
            "tabindex": 0,
            "has_focus_ring": True,
            "container_id": "payment_dialog",
            "is_focus_trapped": True,
        },
        # 4. 关键按钮带负数 tabindex (无法键盘聚焦)
        {
            "element_id": "modal_close_btn",
            "tag_name": "button",
            "tabindex": -1,
            "has_focus_ring": True,
        },
        # 5. 额外两项使可聚焦元素 >= 5 项，触发 SKIP_TO_CONTENT_MISSING 检查
        {
            "element_id": "footer_link_1",
            "tag_name": "a",
            "tabindex": 0,
            "has_focus_ring": True,
        },
        {
            "element_id": "footer_link_2",
            "tag_name": "a",
            "tabindex": 0,
            "has_focus_ring": True,
        },
    ]

    report = simulate_keyboard_navigation(page_name="payment_view", elements=elements)

    assert report.total_defects_count >= 4
    assert report.has_focus_trap is True
    assert report.is_fully_keyboard_accessible is False

    defect_types = {d.defect_type for d in report.defects}
    assert KeyboardDefectType.FOCUS_TRAP_DETECTED in defect_types
    assert KeyboardDefectType.FOCUS_RING_INVISIBLE in defect_types
    assert KeyboardDefectType.POSITIVE_TABINDEX_ABUSE in defect_types
    assert KeyboardDefectType.UNREACHABLE_INTERACTIVE in defect_types
    assert KeyboardDefectType.SKIP_TO_CONTENT_MISSING in defect_types

    # 验证排序: positive tabindex (search_input: step 1) 优先于 tabindex=0 的项
    assert report.traversal_path[0].element_id == "search_input"


def test_simulate_keyboard_navigation_clean_accessible():
    """测试完全符合无障碍的键盘导航流。"""
    elements = [
        # 跳过导航链接
        {
            "element_id": "skip_link",
            "tag_name": "a",
            "tabindex": 0,
            "text_content": "跳至主要内容 (Skip to content)",
            "has_focus_ring": True,
        },
        {
            "element_id": "main_btn",
            "tag_name": "button",
            "tabindex": 0,
            "has_focus_ring": True,
        },
    ]

    report = simulate_keyboard_navigation(page_name="accessible_page", elements=elements)
    assert report.total_defects_count == 0
    assert report.has_focus_trap is False
    assert report.is_fully_keyboard_accessible is True
    assert report.keyboard_accessibility_score_pct == 100.0

    saved = get_keyboard_nav_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_keyboard_nav_reports()) == 1
