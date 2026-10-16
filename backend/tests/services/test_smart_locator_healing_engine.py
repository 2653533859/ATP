"""Unit tests for D2.1 Smart Locator Healing Engine Service."""

import pytest

from app.services.smart_locator_healing_engine import (
    BrokenLocatorContext,
    ElementFingerprint,
    LocatorType,
    heal_broken_locator,
    list_healing_history,
    parse_dom_elements_snapshot,
    reset_locator_healing_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_locator_healing_registry()
    yield
    reset_locator_healing_registry()


def test_heal_broken_locator_by_testid_match():
    # 历史指纹：按钮，带 data-testid="checkout-btn"，原 id 为 "btn-old-101"
    last_known = ElementFingerprint(
        tag_name="button",
        text_content="确认支付并提交订单",
        element_id="btn-old-101",
        attributes={"data-testid": "checkout-btn", "role": "button"},
    )
    context = BrokenLocatorContext(
        original_locator="//button[@id='btn-old-101']",
        locator_type=LocatorType.XPATH,
        last_known_fingerprint=last_known,
    )

    # 当前页面 DOM 快照：id 被重构为 "btn-v2-dynamic-999"，但保留了 data-testid="checkout-btn"
    live_elements = [
        ElementFingerprint(
            tag_name="div",
            text_content="页面头部标题",
            attributes={},
        ),
        ElementFingerprint(
            tag_name="button",
            text_content="确认支付并提交订单",
            element_id="btn-v2-dynamic-999",
            attributes={"data-testid": "checkout-btn", "role": "button"},
            class_names=["ant-btn", "ant-btn-primary"],
        ),
    ]

    result = heal_broken_locator(context, live_elements)

    assert result.success is True
    assert result.best_proposal is not None
    assert result.best_proposal.confidence_score >= 0.70
    assert result.best_proposal.healed_locator == "//*[@data-testid='checkout-btn']"
    assert result.best_proposal.locator_type == LocatorType.TEST_ID
    assert "data-testid='checkout-btn'" in result.best_proposal.reason


def test_heal_broken_locator_by_semantic_text_and_tag():
    # 历史指纹：链接 <a>，文本 "返回购物车"
    last_known = ElementFingerprint(
        tag_name="a",
        text_content="返回购物车",
        attributes={"href": "/cart"},
    )
    context = BrokenLocatorContext(
        original_locator="a.cart-link-old",
        locator_type=LocatorType.CSS_SELECTOR,
        last_known_fingerprint=last_known,
    )

    live_elements = [
        ElementFingerprint(
            tag_name="a",
            text_content="返回购物车",
            class_names=["new-back-btn"],
            attributes={"href": "/cart/v2"},
        ),
        ElementFingerprint(
            tag_name="input",
            text_content=None,
            attributes={"placeholder": "搜索商品"},
        ),
    ]

    result = heal_broken_locator(context, live_elements, min_confidence=0.35)

    assert result.success is True
    assert result.best_proposal is not None
    assert result.best_proposal.healed_locator == "//a[text()='返回购物车']"
    assert "文本完全匹配='返回购物车'" in result.best_proposal.reason


def test_heal_broken_locator_no_match_returns_failure():
    last_known = ElementFingerprint(
        tag_name="button",
        text_content="提交工单",
        attributes={"data-testid": "submit-ticket"},
    )
    context = BrokenLocatorContext(
        original_locator="//button[@data-testid='submit-ticket']",
        last_known_fingerprint=last_known,
    )

    # 当前页面已跳转到完全无关的登录页
    live_elements = [
        ElementFingerprint(tag_name="input", attributes={"type": "password"}),
        ElementFingerprint(tag_name="span", text_content="忘记密码"),
    ]

    result = heal_broken_locator(context, live_elements, min_confidence=0.60)

    assert result.success is False
    assert result.best_proposal is None
    assert len(result.all_proposals) == 0


def test_parse_dom_elements_snapshot_and_history():
    raw_snapshot = [
        {
            "tag_name": "button",
            "text_content": "立即保存",
            "element_id": "btn_save",
            "attributes": {"data-testid": "btn-save-record"},
            "class_names": ["btn", "btn-success"],
        }
    ]

    parsed = parse_dom_elements_snapshot(raw_snapshot)
    assert len(parsed) == 1
    assert parsed[0].tag_name == "button"
    assert parsed[0].element_id == "btn_save"

    # 执行一次自愈并记录历史
    context = BrokenLocatorContext(
        original_locator="#btn_save_old",
        last_known_fingerprint=parsed[0],
    )
    heal_broken_locator(context, parsed)

    history = list_healing_history()
    assert len(history) == 1
    assert history[0].original_locator == "#btn_save_old"
