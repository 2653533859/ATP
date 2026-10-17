"""跨端控件模糊语义匹配与转换器单测 (T1.2)"""

from __future__ import annotations

from app.services.cross_platform_element_translator import (
    SemanticElementDescriptor,
    are_synonyms,
    batch_translate_elements,
    compute_role_compatibility,
    compute_text_similarity,
    compute_token_similarity,
    tokenize_identifier,
    translate_element,
)


def test_tokenize_identifier():
    tokens1 = tokenize_identifier("com.shop.app:id/btn_checkout_order")
    assert "btn" in tokens1
    assert "checkout" in tokens1
    assert "order" in tokens1

    tokens2 = tokenize_identifier("quickPayConfirmButton")
    assert "quick" in tokens2
    assert "pay" in tokens2
    assert "confirm" in tokens2
    assert "button" in tokens2


def test_synonym_detection_and_similarity():
    assert are_synonyms("立即支付", "去付款") is True
    assert are_synonyms("加入购物车", "加购") is True
    assert are_synonyms("取消", "确定") is False

    sim_exact = compute_text_similarity("确认提交", "确认提交")
    assert sim_exact == 1.0

    sim_synonym = compute_text_similarity("立即支付", "确认付款")
    assert sim_synonym >= 0.9


def test_token_and_role_compatibility():
    sim_id = compute_token_similarity("btn_submit_order", "order_submit_action")
    assert sim_id >= 0.5

    role_compat_button = compute_role_compatibility("button", "link")
    assert role_compat_button >= 0.8

    role_compat_diff = compute_role_compatibility("button", "input")
    assert role_compat_diff < 0.5


def test_translate_element_exact_and_synonym():
    source_btn = SemanticElementDescriptor(
        element_id="src_01",
        element_type="button",
        platform="ios",
        text="立即支付",
        identifier="btn_pay_now",
        bounding_box=[100, 500, 150, 45],
    )

    candidates = [
        SemanticElementDescriptor(
            element_id="target_01",
            element_type="button",
            platform="android",
            text="确认付款 (微信/支付宝)",
            identifier="com.shop.app:id/pay_confirm_btn",
            bounding_box=[80, 520, 160, 45],
        ),
        SemanticElementDescriptor(
            element_id="target_02",
            element_type="input",
            platform="android",
            text="搜索商品",
            identifier="search_input",
            bounding_box=[20, 50, 300, 40],
        ),
    ]

    res = translate_element(source_btn, candidates)
    assert res.matched_element is not None
    assert res.matched_element.element_id == "target_01"
    assert res.total_score >= 0.75
    assert res.is_confident is True
    assert res.match_strategy in ("SYNONYM_TEXT", "COMPOSITE_BEST")


def test_translate_element_empty_candidates():
    source_btn = SemanticElementDescriptor(
        element_id="src_02",
        element_type="button",
        platform="web",
        text="结算",
    )
    res = translate_element(source_btn, [])
    assert res.matched_element is None
    assert res.total_score == 0.0
    assert res.is_confident is False
    assert res.match_strategy == "NONE"


def test_batch_translate_elements():
    srcs = [
        SemanticElementDescriptor("s1", "button", "web", text="登录"),
        SemanticElementDescriptor("s2", "input", "web", text="账号"),
    ]
    targets = [
        SemanticElementDescriptor("t1", "button", "android", text="立即登录"),
        SemanticElementDescriptor("t2", "input", "android", text="请输入手机号/账号"),
    ]

    results = batch_translate_elements(srcs, targets)
    assert len(results) == 2
    assert results[0].matched_element is not None
    assert results[0].matched_element.element_id == "t1"
    assert results[1].matched_element is not None
    assert results[1].matched_element.element_id == "t2"
