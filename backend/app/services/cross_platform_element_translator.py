"""跨端控件模糊语义匹配与转换器服务 (T1.2)

基于多维特征（文本同义词、标识符分词、语义角色、空间相对位置）模糊推导目标平台最优对应控件:
1. 业务文本同义词语义归一化与相似度计算 (Semantic Synonym Normalization);
2. 控件标识符驼峰/下划线分词分词匹配 (Identifier Token Jaccard Similarity);
3. 空间拓扑与控件角色兼容性加权比对 (Multi-Factor Scoring Matrix);
4. 候选控件 Top-K 推荐与置信度裁决。
"""

from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone


# 业务常用同义词归一化映射表
SYNONYM_GROUPS: List[Set[str]] = [
    {"支付", "付款", "结算", "买单", "立即支付", "去支付", "pay", "checkout", "purchase"},
    {"确定", "确认", "提交", "完成", "立即提交", "ok", "confirm", "submit", "done"},
    {"搜索", "查找", "查询", "搜一搜", "search", "find", "query"},
    {"登录", "登陆", "登入", "立即登录", "login", "signin", "sign in"},
    {"注册", "立即注册", "创建账号", "register", "signup", "sign up"},
    {"取消", "关闭", "返回", "后退", "cancel", "close", "back"},
    {"加购", "加入购物车", "加购物车", "add to cart", "cart", "addcart"},
    {"删除", "移除", "清空", "delete", "remove", "clear"},
    {"分享", "转发", "share", "forward"},
    {"设置", "偏好设置", "系统设置", "settings", "setting", "preference"},
]


@dataclass
class SemanticElementDescriptor:
    element_id: str
    element_type: str  # button | input | label | tab | link | image | dialog
    platform: str  # web | ios | android
    text: Optional[str] = None
    identifier: Optional[str] = None  # id | name | resource_id | accessibility_id
    bounding_box: Optional[List[int]] = None  # [x, y, width, height]
    role: Optional[str] = None
    extra_attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ElementMatchResult:
    source_element_id: str
    matched_element: Optional[SemanticElementDescriptor]
    total_score: float  # 0.0 ~ 1.0
    text_score: float
    identifier_score: float
    role_score: float
    position_score: float
    match_strategy: str  # EXACT_TEXT | SYNONYM_TEXT | TOKEN_SIMILARITY | COMPOSITE_BEST | NONE
    is_confident: bool  # >= threshold
    analyzed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.matched_element:
            d["matched_element"] = self.matched_element.to_dict()
        return d


def tokenize_identifier(identifier: Optional[str]) -> Set[str]:
    """对控件 ID、resource_id 或 accessibility_id 进行驼峰与下划线分词"""
    if not identifier:
        return set()

    # 剔除 Android 包名前缀 (如 com.shop.app:id/btn_checkout)
    clean_id = identifier.split("/")[-1] if "/" in identifier else identifier
    clean_id = clean_id.lstrip("#.")

    # 拆分驼峰与下划线/中划线
    tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", clean_id)
    return {t.lower() for t in tokens if len(t) > 1}


def are_synonyms(text1: str, text2: str) -> bool:
    """检查两个文本是否属于同一业务同义词组"""
    t1 = text1.strip().lower()
    t2 = text2.strip().lower()
    if t1 == t2:
        return True

    for group in SYNONYM_GROUPS:
        # 如果包含词组中的词
        match1 = any(kw in t1 for kw in group)
        match2 = any(kw in t2 for kw in group)
        if match1 and match2:
            return True

    return False


def compute_text_similarity(text1: Optional[str], text2: Optional[str]) -> float:
    """计算文本相似度（支持精确匹配、同义词匹配与编辑距离）"""
    if not text1 or not text2:
        return 0.0

    t1 = text1.strip().lower()
    t2 = text2.strip().lower()

    if t1 == t2:
        return 1.0

    if are_synonyms(t1, t2):
        return 0.92

    # 基于 SequenceMatcher 计算字符相似度
    ratio = difflib.SequenceMatcher(None, t1, t2).ratio()
    return round(ratio, 4)


def compute_token_similarity(id1: Optional[str], id2: Optional[str]) -> float:
    """计算控件标识符分词 Jaccard 相似度"""
    tokens1 = tokenize_identifier(id1)
    tokens2 = tokenize_identifier(id2)

    if not tokens1 or not tokens2:
        return 0.0

    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    if not union:
        return 0.0

    return round(len(intersection) / len(union), 4)


def compute_role_compatibility(role1: Optional[str], role2: Optional[str]) -> float:
    """计算两个控件语义角色兼容度"""
    if not role1 or not role2:
        return 0.5

    r1 = role1.lower()
    r2 = role2.lower()

    if r1 == r2:
        return 1.0

    # 兼容角色组
    compatible_groups = [
        {"button", "link", "tab"},
        {"input", "textarea", "edittext", "textfield"},
        {"label", "text", "textview"},
    ]

    for g in compatible_groups:
        if r1 in g and r2 in g:
            return 0.85

    return 0.2


def compute_position_proximity(box1: Optional[List[int]], box2: Optional[List[int]]) -> float:
    """计算相对屏幕区域的粗粒度空间接近度"""
    if not box1 or not box2 or len(box1) < 4 or len(box2) < 4:
        return 0.5  # 无法比对时给出中立得分

    # box: [x, y, w, h]
    # 判断是否同在屏幕上半部分或下半部分 (y > 300)
    y1 = box1[1]
    y2 = box2[1]

    same_vertical_half = (y1 < 400 and y2 < 400) or (y1 >= 400 and y2 >= 400)
    return 0.85 if same_vertical_half else 0.4


def translate_element(
    source_element: SemanticElementDescriptor,
    candidate_elements: List[SemanticElementDescriptor],
    confidence_threshold: float = 0.65,
) -> ElementMatchResult:
    """在目标平台的候选控件集合中模糊推导最佳匹配的对应控件"""
    if not candidate_elements:
        return ElementMatchResult(
            source_element_id=source_element.element_id,
            matched_element=None,
            total_score=0.0,
            text_score=0.0,
            identifier_score=0.0,
            role_score=0.0,
            position_score=0.0,
            match_strategy="NONE",
            is_confident=False,
        )

    best_match: Optional[SemanticElementDescriptor] = None
    best_score = 0.0
    best_sub_scores = (0.0, 0.0, 0.0, 0.0)
    best_strategy = "NONE"

    for cand in candidate_elements:
        t_score = compute_text_similarity(source_element.text, cand.text)
        id_score = compute_token_similarity(source_element.identifier, cand.identifier)
        r_score = compute_role_compatibility(source_element.element_type, cand.element_type)
        pos_score = compute_position_proximity(source_element.bounding_box, cand.bounding_box)

        # 权重配比: 文本 45% + 标识符 30% + 角色 15% + 位置 10%
        composite = t_score * 0.45 + id_score * 0.30 + r_score * 0.15 + pos_score * 0.10

        # 特例加速策略
        strategy = "COMPOSITE_BEST"
        if t_score == 1.0:
            strategy = "EXACT_TEXT"
            composite = max(composite, 0.95)
        elif t_score >= 0.90 and are_synonyms(source_element.text or "", cand.text or ""):
            strategy = "SYNONYM_TEXT"
            composite = max(composite, 0.90)
        elif id_score >= 0.80:
            strategy = "TOKEN_SIMILARITY"

        if composite > best_score:
            best_score = composite
            best_match = cand
            best_sub_scores = (t_score, id_score, r_score, pos_score)
            best_strategy = strategy

    is_confident = best_score >= confidence_threshold

    return ElementMatchResult(
        source_element_id=source_element.element_id,
        matched_element=best_match,
        total_score=round(best_score, 4),
        text_score=round(best_sub_scores[0], 4),
        identifier_score=round(best_sub_scores[1], 4),
        role_score=round(best_sub_scores[2], 4),
        position_score=round(best_sub_scores[3], 4),
        match_strategy=best_strategy,
        is_confident=is_confident,
    )


def batch_translate_elements(
    source_elements: List[SemanticElementDescriptor],
    candidate_elements: List[SemanticElementDescriptor],
    confidence_threshold: float = 0.65,
) -> List[ElementMatchResult]:
    """批量推导源端控件列表在目标端中的对应匹配"""
    return [translate_element(src, candidate_elements, confidence_threshold) for src in source_elements]
