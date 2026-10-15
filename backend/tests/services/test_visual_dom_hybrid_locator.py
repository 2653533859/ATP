"""Unit tests for T2.2 Visual and Accessibility Tree Hybrid Intelligent Locator with Self-Healing.

Tests:
1. compute_text_similarity and parse_bounds geometry helpers
2. Tier 1: exact DOM / accessibility tree matching returns unhealed 1.0 confidence
3. Tier 2: fuzzy accessibility tree matching heals drifted selectors
4. Tier 3: visual screenshot OCR matching recovers elements absent from accessibility tree
5. Tier 4: returns failure when element cannot be resolved across any tier
"""

from __future__ import annotations

from app.services.visual_dom_hybrid_locator import (
    compute_text_similarity,
    get_center_coordinates,
    heal_and_locate_element,
    parse_bounds,
)


def test_text_similarity_and_bounds_geometry():
    # 1. Similarity
    assert compute_text_similarity("确认提交", "确认提交") == 1.0
    assert compute_text_similarity("立即支付", "立即支付 (¥99.00)") >= 0.80
    assert compute_text_similarity("Submit", "submit") == 1.0
    assert compute_text_similarity("", "abc") == 0.0

    # 2. Bounds parsing
    bounds = parse_bounds("[100,200][300,400]")
    assert bounds == (100, 200, 300, 400)
    assert bounds is not None
    assert get_center_coordinates(bounds) == (200, 300)

    # Invalid bounds
    assert parse_bounds("invalid") is None


def test_tier1_exact_dom_matching():
    ax_elements = [
        {"resource_id": "com.app:id/btn_cancel", "text": "取消", "bounds": "[50,800][150,850]"},
        {"resource_id": "com.app:id/btn_submit", "text": "确定", "bounds": "[200,800][350,850]"},
    ]

    result = heal_and_locate_element(
        {"resource_id": "com.app:id/btn_submit", "text": "确定"},
        ax_elements=ax_elements,
    )

    assert result.success is True
    assert result.matched_strategy == "exact_dom"
    assert result.confidence_score == 1.0
    assert result.healed is False
    assert result.click_coordinates == (275, 825)
    assert result.target_element is not None


def test_tier2_fuzzy_ax_tree_self_healing():
    # Target resource_id was originally "btn_submit_abc123"
    # But in new release, frontend changed it to "com.app:id/btn_submit_v2" with text "立即确定"
    ax_elements = [
        {"resource_id": "com.app:id/btn_cancel", "text": "取消", "bounds": "[50,800][150,850]"},
        {"resource_id": "com.app:id/btn_submit_v2", "text": "立即确定", "bounds": "[200,800][400,860]"},
    ]

    result = heal_and_locate_element(
        {"resource_id": "btn_submit_abc123", "text": "确定"},
        ax_elements=ax_elements,
    )

    assert result.success is True
    assert result.matched_strategy == "fuzzy_ax_tree"
    assert result.healed is True
    assert result.confidence_score >= 0.70
    assert result.click_coordinates == (300, 830)
    assert "模糊评分自愈" in str(result.healing_details)


def test_tier3_visual_ocr_self_healing():
    # Accessibility tree has no matching element (e.g. Flutter/Unity canvas view)
    ax_elements = [
        {"resource_id": "flutter_root", "text": "", "bounds": "[0,0][1080,1920]"},
    ]

    # Screenshot OCR detected text blocks on screen
    ocr_blocks = [
        {"text": "商品小计", "bounds": [100, 400, 300, 450], "confidence": 0.95},
        {"text": "确认支付", "bounds": [200, 1600, 880, 1720], "confidence": 0.98},
    ]

    result = heal_and_locate_element(
        {"text": "确认支付", "resource_id": "non_existent_dom_id"},
        ax_elements=ax_elements,
        ocr_blocks=ocr_blocks,
    )

    assert result.success is True
    assert result.matched_strategy == "visual_ocr"
    assert result.healed is True
    assert result.confidence_score >= 0.90
    # Expected center of [200, 1600, 880, 1720] -> ( (200+880)/2, (1600+1720)/2 ) = (540, 1660)
    assert result.click_coordinates == (540, 1660)
    assert "视觉 OCR 识别命中" in str(result.healing_details)


def test_tier4_locator_failure():
    ax_elements = [
        {"resource_id": "icon_avatar", "text": "", "bounds": "[10,10][50,50]"},
    ]
    ocr_blocks = [
        {"text": "其他无关文字", "bounds": [100, 100, 300, 150]},
    ]

    result = heal_and_locate_element(
        {"text": "完全不存在的按钮", "resource_id": "unknown_id"},
        ax_elements=ax_elements,
        ocr_blocks=ocr_blocks,
    )

    assert result.success is False
    assert result.matched_strategy == "none"
    assert result.confidence_score == 0.0
    assert result.click_coordinates is None
