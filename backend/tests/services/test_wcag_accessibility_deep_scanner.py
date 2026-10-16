"""基于 WCAG 2.2 标准的 DOM 深度扫描器服务单元测试 (T3.1)。"""

from __future__ import annotations

import pytest
from app.services.wcag_accessibility_deep_scanner import (
    WcagRuleId,
    clear_wcag_report_store,
    get_wcag_report,
    list_wcag_reports,
    scan_dom_accessibility,
)


@pytest.fixture(autouse=True)
def _reset_wcag_state():
    clear_wcag_report_store()
    yield
    clear_wcag_report_store()


def test_scan_dom_accessibility_all_violations():
    """测试探测各类典型 WCAG 2.2 违规: 缺alt、表单无标签、空按钮、重复ID、无效ARIA、热区过小。"""
    elements = [
        # 1. 缺少 alt 的图像 (WCAG 1.1.1)
        {
            "element_id": "img_banner",
            "tag_name": "img",
            "attributes": {"src": "/banner.png"},
            "selector": "img.hero-banner",
        },
        # 2. 缺少 label 的输入框 (WCAG 1.3.1 - CRITICAL)
        {
            "element_id": "input_password",
            "tag_name": "input",
            "attributes": {"type": "password", "id": "dup_field"},
            "selector": "input#input_password",
        },
        # 3. 重复 DOM ID (WCAG 4.1.1)
        {
            "element_id": "input_email",
            "tag_name": "input",
            "attributes": {"type": "email", "id": "dup_field", "aria-label": "邮箱"},
            "selector": "input#input_email",
        },
        # 4. 空文本且无 aria-label 的图标按钮 (WCAG 2.4.4)
        {
            "element_id": "btn_icon_close",
            "tag_name": "button",
            "attributes": {},
            "text_content": "",
            "selector": "button.close-btn",
        },
        # 5. 无效非标准 ARIA 属性 (WCAG 4.1.2)
        {
            "element_id": "div_badge",
            "tag_name": "div",
            "attributes": {"aria-wrong-state": "true"},
            "selector": "div.badge",
        },
        # 6. 交互热区低于 24x24px (WCAG 2.2 准则 2.5.8)
        {
            "element_id": "btn_tiny_tag",
            "tag_name": "button",
            "attributes": {"aria-label": "删除标签"},
            "text_content": "x",
            "width": 16.0,
            "height": 16.0,
            "selector": "button.tiny-tag-close",
        },
    ]

    report = scan_dom_accessibility(
        page_url_or_name="https://test.atp/workbench",
        elements=elements,
    )

    assert report.total_elements_scanned == 6
    assert report.total_violations_count == 6
    assert report.critical_count == 1  # input 缺 label
    assert report.is_wcag_aa_compliant is False

    rule_ids = {v.rule_id for v in report.violations}
    assert WcagRuleId.NON_TEXT_CONTENT in rule_ids
    assert WcagRuleId.INFO_AND_RELATIONSHIPS in rule_ids
    assert WcagRuleId.DUPLICATE_ELEMENT_ID in rule_ids
    assert WcagRuleId.LINK_PURPOSE_IN_CONTEXT in rule_ids
    assert WcagRuleId.NAME_ROLE_VALUE in rule_ids
    assert WcagRuleId.TARGET_SIZE_MINIMUM in rule_ids


def test_scan_dom_accessibility_clean_page():
    """测试完全合规的无障碍页面。"""
    elements = [
        {
            "element_id": "accessible_img",
            "tag_name": "img",
            "attributes": {"src": "/logo.svg", "alt": "公司 Logo"},
            "selector": "img.logo",
        },
        {
            "element_id": "accessible_input",
            "tag_name": "input",
            "attributes": {"type": "text", "aria-label": "用户名"},
            "selector": "input#username",
        },
        {
            "element_id": "accessible_btn",
            "tag_name": "button",
            "text_content": "提交审核",
            "width": 88.0,
            "height": 36.0,
            "selector": "button.submit",
        },
    ]

    report = scan_dom_accessibility(page_url_or_name="https://test.atp/clean", elements=elements)
    assert report.total_violations_count == 0
    assert report.compliance_score_pct == 100.0
    assert report.is_wcag_aa_compliant is True

    saved = get_wcag_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_wcag_reports()) == 1
