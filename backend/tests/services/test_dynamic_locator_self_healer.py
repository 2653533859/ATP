"""多模态定位器动态自愈与相似度推导器单测 (T1.1)"""

from __future__ import annotations

from app.services.dynamic_locator_self_healer import (
    BrokenLocatorContext,
    CandidateDOMNode,
    HealingStrategyTier,
    LocatorHealingDiagnosisResult,
    _compute_identifier_score,
    _compute_text_score,
    derive_self_healing_candidates,
)


def test_text_and_identifier_similarity_scoring():
    assert _compute_text_score("立即购买", "立即购买") == 1.0
    assert _compute_text_score("立即购买", "立即购买商品") >= 0.85

    node = CandidateDOMNode(
        node_id="n1",
        tag_name="button",
        attributes={"id": "btn_order_checkout_new", "data-action": "checkout"},
    )
    score = _compute_identifier_score("#btn_order_checkout_legacy", node)
    assert score >= 0.5


def test_derive_self_healing_by_text_semantic():
    context = BrokenLocatorContext(
        step_id="step_checkout",
        failed_locator_type="css",
        failed_locator_value="#btn-checkout-v1",
        element_text_hint="去结算",
        element_role_hint="button",
    )

    screen_nodes = [
        CandidateDOMNode(
            node_id="node_new_checkout",
            tag_name="button",
            text="去结算",
            attributes={"data-action": "checkout", "class": "btn-primary"},
        ),
        CandidateDOMNode(
            node_id="node_other",
            tag_name="div",
            text="推荐商品",
        ),
    ]

    res = derive_self_healing_candidates(context, screen_nodes)
    assert isinstance(res, LocatorHealingDiagnosisResult)
    assert res.has_healed_candidate is True
    assert res.best_candidate is not None

    best = res.best_candidate
    assert best.matched_node.node_id == "node_new_checkout"
    assert best.strategy_tier == HealingStrategyTier.TIER_2_TEXT_SEMANTIC
    assert best.confidence_score >= 0.90
    assert best.recommended_locator_type == "css"
    assert "data-action='checkout'" in best.recommended_locator_value
    assert "文案语义精准对齐" in best.healing_explanation


def test_derive_self_healing_by_id_variation():
    context = BrokenLocatorContext(
        step_id="step_search",
        failed_locator_type="id",
        failed_locator_value="search_input_box",
        element_role_hint="input",
    )

    screen_nodes = [
        CandidateDOMNode(
            node_id="node_search_updated",
            tag_name="input",
            attributes={"id": "search_input_field", "data-testid": "search-input"},
        ),
    ]

    res = derive_self_healing_candidates(context, screen_nodes)
    assert res.has_healed_candidate is True
    best = res.best_candidate
    assert best is not None
    assert best.confidence_score >= 0.65
    assert best.matched_node.node_id == "node_search_updated"


def test_derive_self_healing_unmatched():
    context = BrokenLocatorContext(
        step_id="step_ghost",
        failed_locator_type="id",
        failed_locator_value="non_existent_elem",
        element_text_hint="根本不存在的控件",
    )
    res = derive_self_healing_candidates(context, [])
    assert res.has_healed_candidate is False
    assert res.best_candidate is None
    assert len(res.all_candidates) == 0

    d = res.to_dict()
    assert d["has_healed_candidate"] is False
    assert d["best_candidate"] is None
