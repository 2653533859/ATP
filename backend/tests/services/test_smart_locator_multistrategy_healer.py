"""Unit Tests for Smart Locator Multi-Strategy Healer (T4.1)。"""

from __future__ import annotations

import pytest

from app.services.smart_locator_multistrategy_healer import (
    CandidateElement,
    TargetElementSpec,
    clear_healing_history,
    get_healing_history,
    get_healing_statistics,
    heal_broken_locator,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_healing_history()
    yield
    clear_healing_history()


def test_heal_by_text_semantic_strategy():
    target = TargetElementSpec(
        original_locator="//button[@id='old-checkout-btn']",
        tag_name="button",
        text_content="立即提交订单",
        attributes={"id": "old-checkout-btn", "class": "btn-primary"},
        bounding_box={"x": 500.0, "y": 600.0, "width": 120.0, "height": 40.0},
    )

    candidates = [
        # 候选 1: 重构后的结算按钮，ID 变动态 hash，但文本依然是 "立即提交订单"
        CandidateElement(
            candidate_id="cand_1",
            tag_name="button",
            text_content="立即提交订单",
            attributes={"id": "btn-dynamic-hash-9182", "class": "rounded-lg bg-blue-600"},
            bounding_box={"x": 505.0, "y": 602.0, "width": 120.0, "height": 40.0},
            xpath="//div/button[1]",
        ),
        # 候选 2: 取消订单按钮
        CandidateElement(
            candidate_id="cand_2",
            tag_name="button",
            text_content="取消订单",
            attributes={"id": "cancel-btn"},
            bounding_box={"x": 300.0, "y": 600.0, "width": 100.0, "height": 40.0},
        ),
    ]

    res = heal_broken_locator(target, candidates)

    assert res.is_healed is True
    assert res.confidence_score >= 0.70
    assert "立即提交订单" in res.healed_locator
    assert res.scores_breakdown.text_semantic_score == 1.0
    assert "page.locator" in res.remediation_patch_code
    assert res.retry_success is True


def test_heal_by_test_id_strategy():
    target = TargetElementSpec(
        original_locator="#btn-pay",
        tag_name="button",
        test_id="checkout-action-submit",
        text_content="确认支付",
    )

    candidates = [
        CandidateElement(
            candidate_id="c_testid",
            tag_name="button",
            test_id="checkout-action-submit",
            text_content="立即支付 ￥99.0",  # 文本微调
            attributes={"data-testid": "checkout-action-submit"},
        ),
    ]

    res = heal_broken_locator(target, candidates)

    assert res.is_healed is True
    assert res.confidence_score >= 0.68
    assert "[data-testid='checkout-action-submit']" == res.healed_locator


def test_spatial_proximity_preference():
    # 两个按钮文本完全相同（如两个 "加入购物车" 按钮），靠近原坐标的候选者获得更高空间距离分
    target = TargetElementSpec(
        original_locator="//button[text()='加入购物车']",
        tag_name="button",
        text_content="加入购物车",
        bounding_box={"x": 100.0, "y": 200.0, "width": 80.0, "height": 30.0},
    )

    candidates = [
        # 候选 A: 极度靠近原坐标
        CandidateElement(
            candidate_id="cand_near",
            tag_name="button",
            text_content="加入购物车",
            bounding_box={"x": 105.0, "y": 202.0, "width": 80.0, "height": 30.0},
            xpath="//section[1]/button",
        ),
        # 候选 B: 屏幕远端相关推荐栏中的同名按钮
        CandidateElement(
            candidate_id="cand_far",
            tag_name="button",
            text_content="加入购物车",
            bounding_box={"x": 800.0, "y": 1200.0, "width": 80.0, "height": 30.0},
            xpath="//aside/div/button",
        ),
    ]

    res = heal_broken_locator(target, candidates)

    assert res.is_healed is True
    assert "//section[1]/button" in res.remediation_patch_code or "加入购物车" in res.healed_locator
    assert res.scores_breakdown.spatial_score >= 0.80


def test_unmatchable_locator_rejection():
    target = TargetElementSpec(
        original_locator="//input[@name='user_password']",
        tag_name="input",
        text_content="",
        attributes={"name": "user_password", "type": "password"},
    )

    candidates = [
        # 毫无关联的页脚链接
        CandidateElement(
            candidate_id="cand_footer",
            tag_name="a",
            text_content="关于我们",
            attributes={"href": "/about"},
        ),
    ]

    res = heal_broken_locator(target, candidates)

    assert res.is_healed is False
    assert res.confidence_score < 0.68
    assert res.healed_locator == target.original_locator
    assert res.retry_success is False


def test_healing_history_and_high_success_rate():
    # 执行多次有效自愈与极少数失败自愈
    t1 = TargetElementSpec("//button[@id='btn1']", tag_name="button", text_content="保存设置")
    c1 = [CandidateElement("c1", tag_name="button", text_content="保存设置")]
    heal_broken_locator(t1, c1)

    t2 = TargetElementSpec("//button[@id='btn2']", tag_name="button", text_content="导出报表")
    c2 = [CandidateElement("c2", tag_name="button", text_content="导出报表")]
    heal_broken_locator(t2, c2)

    history = get_healing_history()
    assert len(history) == 2

    stats = get_healing_statistics()
    assert stats["total_healing_attempts"] == 2
    assert stats["successful_healings_count"] == 2
    assert stats["healing_success_rate_pct"] == 100.0  # >= 90%
