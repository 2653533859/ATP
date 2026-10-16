"""基于视觉大模型 (VLM) 的 UI 页面语义断言单元测试 (T2.1)。"""

from __future__ import annotations

import pytest
from app.services.vlm_ui_semantic_assertion_reasoner import (
    AssertionVerdict,
    VisualAssertionRuleInput,
    VisualAssertionRuleType,
    clear_vlm_assertion_store,
    evaluate_visual_semantic_assertions,
    get_vlm_assertion_report,
    list_vlm_assertion_reports,
)


@pytest.fixture(autouse=True)
def _reset_vlm_state():
    clear_vlm_assertion_store()
    yield
    clear_vlm_assertion_store()


def test_evaluate_visual_assertions_all_passed():
    """测试各项视觉断言均满足时判定 overall_passed 与 100% 满分。"""
    rules = [
        VisualAssertionRuleInput(
            rule_type=VisualAssertionRuleType.ASSERT_NO_WHITE_SCREEN,
            target_description="全页防白屏检测",
        ),
        VisualAssertionRuleInput(
            rule_type=VisualAssertionRuleType.ASSERT_NO_BROKEN_IMAGES,
            target_description="主图裂图碎图检测",
        ),
        VisualAssertionRuleInput(
            rule_type=VisualAssertionRuleType.ASSERT_KEY_ELEMENT_VISIBLE,
            target_description="立即结算按钮",
            expected_bounding_box={"x": 100, "y": 500, "width": 120, "height": 40},
        ),
        VisualAssertionRuleInput(
            rule_type=VisualAssertionRuleType.ASSERT_NO_INFINITE_LOADING,
            target_description="防数据加载旋转圈停滞",
        ),
    ]

    report = evaluate_visual_semantic_assertions(
        page_name="cart_checkout_screen",
        rules=rules,
        simulated_white_screen_ratio=0.05,
        simulated_broken_images_count=0,
        simulated_is_loading_stuck=False,
    )

    assert report.page_name == "cart_checkout_screen"
    assert report.overall_passed is True
    assert report.visual_semantic_score_pct == 100.0
    assert report.passed_count == 4
    assert report.failed_count == 0


def test_evaluate_visual_assertions_detect_white_screen_and_broken_image():
    """测试探测到白屏与碎图时触发 FAIL 裁决。"""
    rules = [
        VisualAssertionRuleInput(
            rule_type=VisualAssertionRuleType.ASSERT_NO_WHITE_SCREEN,
            target_description="白屏检测",
        ),
        VisualAssertionRuleInput(
            rule_type=VisualAssertionRuleType.ASSERT_NO_BROKEN_IMAGES,
            target_description="商品首图检测",
        ),
        VisualAssertionRuleInput(
            rule_type=VisualAssertionRuleType.ASSERT_KEY_ELEMENT_VISIBLE,
            target_description="提交订单按钮",
        ),
    ]

    report = evaluate_visual_semantic_assertions(
        page_name="broken_product_detail",
        rules=rules,
        simulated_white_screen_ratio=0.85,  # 严重白屏
        simulated_broken_images_count=3,  # 存在裂图
        simulated_missing_element_names=["提交订单按钮"],  # 按钮缺失
    )

    assert report.overall_passed is False
    assert report.failed_count == 3
    assert report.visual_semantic_score_pct == 0.0

    white_finding = report.findings[0]
    assert white_finding.verdict == AssertionVerdict.FAIL
    assert white_finding.detected_bounding_box is not None


def test_list_and_get_vlm_reports():
    """测试视觉断言报告持久化与列表查询。"""
    rules = [
        VisualAssertionRuleInput(
            rule_type=VisualAssertionRuleType.ASSERT_CUSTOM_NATURAL_LANGUAGE,
            target_description="导航栏呈现用户头像",
            custom_prompt="检查右上角是否渲染圆形用户头像",
        )
    ]
    rep = evaluate_visual_semantic_assertions(page_name="user_profile", rules=rules)

    saved = get_vlm_assertion_report(rep.report_id)
    assert saved is not None
    assert saved.report_id == rep.report_id

    reports = list_vlm_assertion_reports()
    assert len(reports) == 1
