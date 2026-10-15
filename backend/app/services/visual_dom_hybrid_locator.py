"""Visual and Accessibility Tree Hybrid Intelligent Locator with Self-Healing (T2.2).

Provides:
1. Multi-tier hybrid element localization:
   - Tier 1: Exact DOM / Accessibility Tree matching
   - Tier 2: Fuzzy Accessibility Tree heuristic matching with multi-attribute scoring
   - Tier 3: Visual Screenshot OCR bounding-box matching (canvas / Unity / custom views)
2. Normalized text similarity calculation using pure-Python SequenceMatcher.
3. Automated coordinate derivation and self-healing action compensation.
4. Detailed healing diagnostics and confidence score evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

FUZZY_MATCH_THRESHOLD = 0.65
OCR_CONFIDENCE_THRESHOLD = 0.60


@dataclass
class HybridLocatorResult:
    success: bool
    matched_strategy: str  # "exact_dom" | "fuzzy_ax_tree" | "visual_ocr" | "none"
    confidence_score: float  # 0.0 ~ 1.0
    healed: bool = False
    click_coordinates: tuple[int, int] | None = None
    target_element: dict[str, Any] | None = None
    healing_details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "matched_strategy": self.matched_strategy,
            "confidence_score": round(self.confidence_score, 3),
            "healed": self.healed,
            "click_coordinates": self.click_coordinates,
            "target_element": self.target_element,
            "healing_details": self.healing_details,
        }


def compute_text_similarity(str1: str, str2: str) -> float:
    """Compute string similarity ratio between 0.0 and 1.0."""
    s1 = (str1 or "").strip().lower()
    s2 = (str2 or "").strip().lower()
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    if s1 in s2 or s2 in s1:
        # Boost substring match
        len_ratio = min(len(s1), len(s2)) / max(len(s1), len(s2))
        return max(0.80, len_ratio)
    return SequenceMatcher(None, s1, s2).ratio()


def parse_bounds(bounds_str: str) -> tuple[int, int, int, int] | None:
    """Parse Android/iOS bounding box string like '[100,200][300,400]' into (x1, y1, x2, y2)."""
    m = re.findall(r"\d+", str(bounds_str))
    if len(m) >= 4:
        x1, y1, x2, y2 = map(int, m[:4])
        return x1, y1, x2, y2
    return None


def get_center_coordinates(bounds: tuple[int, int, int, int]) -> tuple[int, int]:
    x1, y1, x2, y2 = bounds
    return (x1 + x2) // 2, (y1 + y2) // 2


def locate_with_exact_dom(
    target_params: dict[str, Any],
    ax_elements: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Tier 1: Locate element through exact resource_id, text, or accessibility_id."""
    target_res_id = target_params.get("resource_id") or target_params.get("resourceId")
    target_text = target_params.get("text")
    target_ax_id = target_params.get("accessibility_id")

    for el in ax_elements:
        if not isinstance(el, dict):
            continue
        el_res_id = el.get("resource_id") or el.get("resourceId")
        el_text = el.get("text")
        el_ax_id = el.get("accessibility_id") or el.get("content_desc")

        if target_res_id and el_res_id and target_res_id == el_res_id:
            return el
        if target_ax_id and el_ax_id and target_ax_id == el_ax_id:
            return el
        if target_text and el_text and target_text.strip() == el_text.strip():
            return el

    return None


def locate_with_fuzzy_ax_tree(
    target_params: dict[str, Any],
    ax_elements: list[dict[str, Any]],
    threshold: float = FUZZY_MATCH_THRESHOLD,
) -> tuple[dict[str, Any] | None, float, str]:
    """Tier 2: Fuzzy matching over accessibility tree nodes using multi-attribute heuristic score."""
    target_text = str(target_params.get("text") or target_params.get("label") or "")
    target_res_id = str(target_params.get("resource_id") or "")
    stem_res_id = re.sub(r"[_\-][0-9a-fA-F]+$", "", target_res_id).lower() if target_res_id else ""

    best_element: dict[str, Any] | None = None
    best_score = 0.0
    best_reason = ""

    for el in ax_elements:
        if not isinstance(el, dict):
            continue
        el_text = str(el.get("text") or el.get("content_desc") or "")
        el_res_id = str(el.get("resource_id") or "").lower()

        score = 0.0
        reason_parts: list[str] = []

        # 1. Text similarity
        if target_text and el_text:
            text_sim = compute_text_similarity(target_text, el_text)
            if text_sim >= 0.70:
                score += text_sim * 0.75
                reason_parts.append(f"文本相似度 {text_sim:.2f} ('{target_text}' ~ '{el_text}')")

        # 2. Resource ID stem similarity
        if stem_res_id and el_res_id and stem_res_id in el_res_id:
            score += 0.35
            reason_parts.append(f"组件 ID 前缀命中 '{stem_res_id}'")

        if score > best_score:
            best_score = score
            best_element = el
            best_reason = " | ".join(reason_parts)

    if best_score >= threshold:
        return best_element, min(1.0, best_score), best_reason

    return None, 0.0, ""


def locate_with_visual_ocr(
    target_params: dict[str, Any],
    ocr_blocks: list[dict[str, Any]],
    threshold: float = OCR_CONFIDENCE_THRESHOLD,
) -> tuple[tuple[int, int] | None, float, str]:
    """Tier 3: Locate target text bounding-box from screenshot OCR blocks and compute center click coordinates."""
    target_text = str(target_params.get("text") or target_params.get("label") or "")
    if not target_text or not ocr_blocks:
        return None, 0.0, ""

    best_coords: tuple[int, int] | None = None
    best_score = 0.0
    best_matched_text = ""

    for block in ocr_blocks:
        if not isinstance(block, dict):
            continue
        block_text = str(block.get("text", ""))
        bounds = block.get("bounds")  # [x1, y1, x2, y2]
        confidence = float(block.get("confidence", 1.0))

        sim = compute_text_similarity(target_text, block_text)
        total_score = sim * confidence

        if total_score > best_score and bounds and len(bounds) >= 4:
            best_score = total_score
            best_coords = get_center_coordinates(tuple(bounds[:4]))  # type: ignore[arg-type]
            best_matched_text = block_text

    if best_score >= threshold and best_coords:
        reason = f"视觉 OCR 识别命中 '{best_matched_text}' (相似度: {best_score:.2f})，补偿点击物理坐标: {best_coords}"
        return best_coords, min(1.0, best_score), reason

    return None, 0.0, ""


def heal_and_locate_element(
    target_params: dict[str, Any],
    *,
    ax_elements: list[dict[str, Any]] | None = None,
    ocr_blocks: list[dict[str, Any]] | None = None,
) -> HybridLocatorResult:
    """Execute multi-tier hybrid element localization and automated self-healing."""
    ax_list = ax_elements or []
    ocr_list = ocr_blocks or []

    # 1. Tier 1: Exact DOM / AX Matching
    exact = locate_with_exact_dom(target_params, ax_list)
    if exact:
        coords = None
        if "bounds" in exact:
            parsed = parse_bounds(str(exact["bounds"]))
            if parsed:
                coords = get_center_coordinates(parsed)
        return HybridLocatorResult(
            success=True,
            matched_strategy="exact_dom",
            confidence_score=1.0,
            healed=False,
            click_coordinates=coords,
            target_element=exact,
            healing_details="精准命中 DOM/无障碍树节点",
        )

    # 2. Tier 2: Fuzzy Accessibility Tree Matching (DOM 自愈)
    fuzzy_el, fuzzy_score, fuzzy_reason = locate_with_fuzzy_ax_tree(target_params, ax_list)
    if fuzzy_el:
        coords = None
        if "bounds" in fuzzy_el:
            parsed = parse_bounds(str(fuzzy_el["bounds"]))
            if parsed:
                coords = get_center_coordinates(parsed)
        return HybridLocatorResult(
            success=True,
            matched_strategy="fuzzy_ax_tree",
            confidence_score=fuzzy_score,
            healed=True,
            click_coordinates=coords,
            target_element=fuzzy_el,
            healing_details=f"无障碍树模糊评分自愈: {fuzzy_reason}",
        )

    # 3. Tier 3: Visual Screenshot OCR Matching (视觉 OCR 自愈)
    ocr_coords, ocr_score, ocr_reason = locate_with_visual_ocr(target_params, ocr_list)
    if ocr_coords:
        return HybridLocatorResult(
            success=True,
            matched_strategy="visual_ocr",
            confidence_score=ocr_score,
            healed=True,
            click_coordinates=ocr_coords,
            target_element=None,
            healing_details=ocr_reason,
        )

    # 4. Fail - No match found across all 3 tiers
    return HybridLocatorResult(
        success=False,
        matched_strategy="none",
        confidence_score=0.0,
        healed=False,
        click_coordinates=None,
        target_element=None,
        healing_details="未在 DOM 树、无障碍树或视觉 OCR 中匹配到有效目标",
    )
