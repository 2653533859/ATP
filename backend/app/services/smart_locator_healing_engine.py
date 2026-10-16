"""基于 DOM / UI 树差分与语义特征匹配的多模态失效选择器自愈引擎 (D2.1).

当 Web / 移动端用例因前端重构导致元素定位器（XPath / CSS Selector / ID）失效时，
自动对当前实时页面 DOM / UI 树结构进行多维指纹特征差分与加权打分，自动生成高置信度自愈定位器。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class LocatorType(str, Enum):
    XPATH = "xpath"
    CSS_SELECTOR = "css_selector"
    ACCESSIBILITY_ID = "accessibility_id"
    ID = "id"
    NAME = "name"
    TEST_ID = "test_id"
    TEXT = "text"


@dataclass
class ElementFingerprint:
    tag_name: str
    text_content: str | None = None
    element_id: str | None = None
    class_names: list[str] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    parent_tag: str | None = None
    xpath: str | None = None
    bounding_box: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag_name": self.tag_name,
            "text_content": self.text_content,
            "element_id": self.element_id,
            "class_names": self.class_names,
            "attributes": self.attributes,
            "parent_tag": self.parent_tag,
            "xpath": self.xpath,
            "bounding_box": self.bounding_box,
        }


@dataclass
class BrokenLocatorContext:
    original_locator: str
    locator_type: LocatorType = LocatorType.XPATH
    last_known_fingerprint: ElementFingerprint | None = None
    error_message: str = "NoSuchElementException"

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_locator": self.original_locator,
            "locator_type": self.locator_type.value,
            "last_known_fingerprint": self.last_known_fingerprint.to_dict() if self.last_known_fingerprint else None,
            "error_message": self.error_message,
        }


@dataclass
class HealedLocatorProposal:
    proposal_id: str
    healed_locator: str
    locator_type: LocatorType
    confidence_score: float
    match_strategy: str
    matched_element: ElementFingerprint
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "healed_locator": self.healed_locator,
            "locator_type": self.locator_type.value,
            "confidence_score": round(self.confidence_score, 4),
            "match_strategy": self.match_strategy,
            "matched_element": self.matched_element.to_dict(),
            "reason": self.reason,
        }


@dataclass
class LocatorHealingResult:
    success: bool
    original_locator: str
    best_proposal: HealedLocatorProposal | None
    all_proposals: list[HealedLocatorProposal]
    elements_scanned_count: int
    healed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    audit_id: str = field(default_factory=lambda: f"heal_audit_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "success": self.success,
            "original_locator": self.original_locator,
            "best_proposal": self.best_proposal.to_dict() if self.best_proposal else None,
            "all_proposals": [p.to_dict() for p in self.all_proposals],
            "elements_scanned_count": self.elements_scanned_count,
            "healed_at": self.healed_at.isoformat(),
        }


# 内存自愈审计历史
_LOCATOR_HEALING_HISTORY: list[LocatorHealingResult] = []


def _calculate_element_similarity(
    target: ElementFingerprint,
    candidate: ElementFingerprint,
) -> tuple[float, str]:
    """计算单个候选元素与历史已知指纹的多维加权相似度得分。

    权重体系：
    - 精准标识 (data-testid / id): 0.35
    - 文本语义 (text_content): 0.25
    - 标签与拓扑结构 (tag_name / parent_tag): 0.20
    - 核心业务属性 (placeholder / aria-label / name / type): 0.20
    """
    score = 0.0
    matched_features: list[str] = []

    # 1. 精准标识 (35%)
    target_testid = target.attributes.get("data-testid") or target.attributes.get("test-id")
    cand_testid = candidate.attributes.get("data-testid") or candidate.attributes.get("test-id")
    if target_testid and cand_testid and target_testid == cand_testid:
        score += 0.35
        matched_features.append(f"data-testid='{cand_testid}' (35%)")
    elif target.element_id and candidate.element_id and target.element_id == candidate.element_id:
        score += 0.35
        matched_features.append(f"id='{candidate.element_id}' (35%)")

    # 2. 文本语义 (25%)
    if target.text_content and candidate.text_content:
        t_clean = target.text_content.strip().lower()
        c_clean = candidate.text_content.strip().lower()
        if t_clean == c_clean:
            score += 0.25
            matched_features.append(f"文本完全匹配='{candidate.text_content}' (25%)")
        elif t_clean in c_clean or c_clean in t_clean:
            score += 0.15
            matched_features.append(f"文本子串包含='{candidate.text_content}' (15%)")

    # 3. 标签与拓扑 (20%)
    if target.tag_name.lower() == candidate.tag_name.lower():
        score += 0.12
        matched_features.append(f"tag='<{candidate.tag_name}>' (12%)")
    if target.parent_tag and candidate.parent_tag and target.parent_tag.lower() == candidate.parent_tag.lower():
        score += 0.08
        matched_features.append(f"parent='<{candidate.parent_tag}>' (8%)")

    # 4. 业务属性 (20%)
    common_attrs = ["placeholder", "aria-label", "name", "type", "role", "title"]
    attr_matches = 0
    attr_total = 0
    for attr in common_attrs:
        t_val = target.attributes.get(attr)
        c_val = candidate.attributes.get(attr)
        if t_val:
            attr_total += 1
            if c_val and t_val.strip().lower() == c_val.strip().lower():
                attr_matches += 1

    if attr_total > 0:
        ratio = attr_matches / float(attr_total)
        attr_score = ratio * 0.20
        score += attr_score
        if attr_matches > 0:
            matched_features.append(f"业务属性命中 {attr_matches}/{attr_total} ({attr_score*100:.1f}%)")

    # 归一化限制至 [0.0, 1.0]
    final_score = min(1.0, max(0.0, score))
    reason = "；".join(matched_features) if matched_features else "无显著特征重合"
    return final_score, reason


def _generate_candidate_locator(element: ElementFingerprint) -> tuple[str, LocatorType, str]:
    """为目标候选元素生成最稳固、可读性最好的自愈定位表达式。"""
    # 优先使用 data-testid
    testid = element.attributes.get("data-testid") or element.attributes.get("test-id")
    if testid:
        return f"//*[@data-testid='{testid}']", LocatorType.TEST_ID, "优先使用高保真 data-testid 稳定属性"

    # 其次使用唯一 ID
    if element.element_id:
        return f"#{element.element_id}", LocatorType.ID, "使用元素 ID 稳固锚定"

    # 再次使用特定 name 属性
    name = element.attributes.get("name")
    if name:
        return f"{element.tag_name}[name='{name}']", LocatorType.CSS_SELECTOR, "使用标签与 name 属性复合锚定"

    # 再次使用包含精确文本的 XPath
    if element.text_content and len(element.text_content.strip()) > 0:
        clean_text = element.text_content.strip()
        return f"//{element.tag_name}[text()='{clean_text}']", LocatorType.XPATH, "使用标签与文本内容唯一锚定"

    # 兜底使用已有 XPath 或复合类选择器
    if element.class_names:
        first_class = element.class_names[0]
        return f"{element.tag_name}.{first_class}", LocatorType.CSS_SELECTOR, "使用标签与主样式类选择器"

    if element.xpath:
        return element.xpath, LocatorType.XPATH, "使用元素绝对拓扑路径"

    return f"//{element.tag_name}", LocatorType.XPATH, "使用标签泛化兜底"


def heal_broken_locator(
    context: BrokenLocatorContext,
    live_elements: list[ElementFingerprint],
    min_confidence: float = 0.50,
) -> LocatorHealingResult:
    """核心自愈决策函数：遍历当前页面元素指纹，加权匹配并生成自愈定位器清单。"""
    if not context.last_known_fingerprint:
        # 如果未传入历史指纹，则从原始选择器中推断基础指纹
        inferred_tag = (
            "button"
            if "button" in context.original_locator.lower()
            else "input"
            if "input" in context.original_locator.lower()
            else "div"
        )
        context.last_known_fingerprint = ElementFingerprint(tag_name=inferred_tag)

    target_fingerprint = context.last_known_fingerprint
    proposals: list[HealedLocatorProposal] = []

    for elem in live_elements:
        sim_score, reason = _calculate_element_similarity(target_fingerprint, elem)
        if sim_score >= min_confidence:
            healed_loc, loc_type, strategy_desc = _generate_candidate_locator(elem)
            proposal = HealedLocatorProposal(
                proposal_id=f"prop_{uuid.uuid4().hex[:8]}",
                healed_locator=healed_loc,
                locator_type=loc_type,
                confidence_score=sim_score,
                match_strategy=strategy_desc,
                matched_element=elem,
                reason=reason,
            )
            proposals.append(proposal)

    # 按置信度由高到低降序排序
    proposals.sort(key=lambda p: p.confidence_score, reverse=True)
    best = proposals[0] if proposals else None
    is_success = best is not None

    result = LocatorHealingResult(
        success=is_success,
        original_locator=context.original_locator,
        best_proposal=best,
        all_proposals=proposals,
        elements_scanned_count=len(live_elements),
    )

    _LOCATOR_HEALING_HISTORY.append(result)
    logger.info(
        "Executed locator healing original=%s success=%s proposals=%s best_score=%s",
        context.original_locator,
        is_success,
        len(proposals),
        best.confidence_score if best else 0.0,
    )
    return result


def parse_dom_elements_snapshot(snapshot_data: list[dict[str, Any]]) -> list[ElementFingerprint]:
    """将从前端或 Playwright/UIAutomator 抓取到的 DOM 节点 JSON 批量解析为指纹对象列表。"""
    elements: list[ElementFingerprint] = []
    for item in snapshot_data:
        elem = ElementFingerprint(
            tag_name=str(item.get("tag_name", "div")),
            text_content=item.get("text_content"),
            element_id=item.get("element_id"),
            class_names=item.get("class_names") or [],
            attributes=item.get("attributes") or {},
            parent_tag=item.get("parent_tag"),
            xpath=item.get("xpath"),
            bounding_box=item.get("bounding_box"),
        )
        elements.append(elem)
    return elements


def list_healing_history() -> list[LocatorHealingResult]:
    """查询选择器自愈评估审计历史。"""
    return list(_LOCATOR_HEALING_HISTORY)


def reset_locator_healing_registry() -> None:
    """仅供单元测试清理状态使用。"""
    _LOCATOR_HEALING_HISTORY.clear()
