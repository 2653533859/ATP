"""历史已知缺陷向量指纹特征相似度匹配与知识检索引擎 (T3.2)。

对自动化测试执行中捕获的异常信息与堆栈：
1. 提取抗噪声归一化语义指纹向量 (Tokenized Error Fingerprint)；
2. 依据余弦与 Jaccard 双重加权相似度在已知缺陷知识库中快速检索比对；
3. 输出历史已验证解决方案、关联工单 (Jira/GitHub Issue) 与修复建议。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import math
import re
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class MatchTier(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"  # 精确匹配 (>= 0.85)
    HIGH_SIMILARITY = "HIGH_SIMILARITY"  # 高度相似 (>= 0.65)
    MEDIUM_SIMILARITY = "MEDIUM_SIMILARITY"  # 中度相似 (>= 0.45)
    LOW_SIMILARITY = "LOW_SIMILARITY"  # 低相似度 (< 0.45)


@dataclass
class IncidentKnowledgeItem:
    incident_id: str
    title: str
    category: str
    service_name: str
    error_pattern: str
    signature_tokens: list[str]
    root_cause_explanation: str
    verified_resolution: str
    external_ticket_ref: str = ""
    occurrences_count: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "category": self.category,
            "service_name": self.service_name,
            "error_pattern": self.error_pattern,
            "signature_tokens": self.signature_tokens,
            "root_cause_explanation": self.root_cause_explanation,
            "verified_resolution": self.verified_resolution,
            "external_ticket_ref": self.external_ticket_ref,
            "occurrences_count": self.occurrences_count,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class FingerprintMatchResult:
    incident: IncidentKnowledgeItem
    similarity_score: float  # 0.0 ~ 1.0
    match_tier: MatchTier
    matched_tokens: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident": self.incident.to_dict(),
            "similarity_score": round(self.similarity_score, 2),
            "match_tier": self.match_tier.value,
            "matched_tokens": self.matched_tokens,
        }


@dataclass
class IncidentMatchReport:
    query_fingerprint_tokens: list[str]
    matches_count: int
    matches: list[FingerprintMatchResult]
    best_match_resolution: str | None
    recommendation_summary: str
    matched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_fingerprint_tokens": self.query_fingerprint_tokens,
            "matches_count": self.matches_count,
            "matches": [m.to_dict() for m in self.matches],
            "best_match_resolution": self.best_match_resolution,
            "recommendation_summary": self.recommendation_summary,
            "matched_at": self.matched_at.isoformat(),
        }


# 全局已知缺陷知识库: incident_id -> IncidentKnowledgeItem
_INCIDENT_STORE: dict[str, IncidentKnowledgeItem] = {}


def extract_error_fingerprint(
    error_message: str,
    stack_trace: str = "",
    service_name: str = "",
) -> list[str]:
    """提取归一化异常指纹向量，清洗掉易变化的行号、内存地址、UUID与时间戳噪声。"""
    raw_text = f"{service_name} {error_message} {stack_trace}".lower()

    # 清洗 0x 开头的内存地址与 16 进制数字
    cleaned = re.sub(r"0x[0-9a-fA-F]+", " ", raw_text)
    # 清洗 UUID / GUID
    cleaned = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", " ", cleaned)
    # 清洗纯数字 (时间戳、行号等)
    cleaned = re.sub(r"\b\d+\b", " ", cleaned)
    # 提取英文与下划线单词 (长度 >= 3)
    tokens = re.findall(r"[a-z_][a-z0-9_]{2,}", cleaned)

    # 停用词表过滤
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "file",
        "line",
        "most",
        "recent",
        "call",
        "last",
        "traceback",
        "none",
        "true",
        "false",
    }
    filtered = [t for t in tokens if t not in stop_words]

    # 去重保留顺序
    seen = set()
    result = []
    for t in filtered:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _calculate_cosine_and_jaccard_similarity(
    tokens1: list[str],
    tokens2: list[str],
) -> tuple[float, list[str]]:
    """计算两组指纹向量的加权相似度得分与共同交集 Token。"""
    s1 = set(tokens1)
    s2 = set(tokens2)
    intersection = s1 & s2

    if not s1 or not s2:
        return 0.0, []

    overlap = len(intersection) / min(len(s1), len(s2))
    jaccard = len(intersection) / len(s1 | s2)
    cosine = len(intersection) / math.sqrt(len(s1) * len(s2))

    # 综合得分: 50% 核心重叠度 (Simpson Overlap) + 30% 余弦 + 20% Jaccard
    score = 0.5 * overlap + 0.3 * cosine + 0.2 * jaccard
    return min(1.0, max(0.0, score)), sorted(list(intersection))


def register_known_incident(
    title: str,
    category: str,
    service_name: str,
    error_pattern: str,
    root_cause_explanation: str,
    verified_resolution: str,
    external_ticket_ref: str = "",
    incident_id: str | None = None,
) -> IncidentKnowledgeItem:
    """录入或更新一条已知缺陷经验知识库条目。"""
    iid = incident_id or f"inc_{uuid.uuid4().hex[:8]}"
    tokens = extract_error_fingerprint(
        error_message=error_pattern,
        stack_trace=root_cause_explanation,
        service_name=service_name,
    )

    item = IncidentKnowledgeItem(
        incident_id=iid,
        title=title,
        category=category,
        service_name=service_name,
        error_pattern=error_pattern,
        signature_tokens=tokens,
        root_cause_explanation=root_cause_explanation,
        verified_resolution=verified_resolution,
        external_ticket_ref=external_ticket_ref,
    )
    _INCIDENT_STORE[iid] = item
    return item


def match_incident_fingerprint(
    error_message: str,
    stack_trace: str = "",
    service_name: str = "",
    min_similarity: float = 0.55,
    limit: int = 5,
) -> IncidentMatchReport:
    """在已知缺陷知识库中执行指纹向量相似度模糊检索与处置推荐。"""
    query_tokens = extract_error_fingerprint(
        error_message=error_message,
        stack_trace=stack_trace,
        service_name=service_name,
    )

    matches: list[FingerprintMatchResult] = []

    for incident in _INCIDENT_STORE.values():
        score, common_tokens = _calculate_cosine_and_jaccard_similarity(query_tokens, incident.signature_tokens)
        if score >= min_similarity:
            if score >= 0.85:
                tier = MatchTier.EXACT_MATCH
            elif score >= 0.65:
                tier = MatchTier.HIGH_SIMILARITY
            elif score >= 0.45:
                tier = MatchTier.MEDIUM_SIMILARITY
            else:
                tier = MatchTier.LOW_SIMILARITY

            matches.append(
                FingerprintMatchResult(
                    incident=incident,
                    similarity_score=score,
                    match_tier=tier,
                    matched_tokens=common_tokens,
                )
            )

    # 按相似度降序排序
    matches.sort(key=lambda m: m.similarity_score, reverse=True)
    top_matches = matches[:limit]

    best_res = None
    summary = ""

    if top_matches:
        top = top_matches[0]
        best_res = top.incident.verified_resolution
        summary = (
            f"成功匹配到 {len(top_matches)} 条历史相似缺陷！最高相似度达到 {round(top.similarity_score * 100, 1)}% "
            f"({top.match_tier.value})，对应历史问题 [{top.incident.title}]"
            f"{f' ({top.incident.external_ticket_ref})' if top.incident.external_ticket_ref else ''}。"
        )
    else:
        summary = "在知识库中未检索到高度相似的历史缺陷，可能属于新引入问题或环境孤立异常。"

    return IncidentMatchReport(
        query_fingerprint_tokens=query_tokens,
        matches_count=len(top_matches),
        matches=top_matches,
        best_match_resolution=best_res,
        recommendation_summary=summary,
    )


def list_known_incidents() -> list[IncidentKnowledgeItem]:
    """查询已知缺陷知识库条目列表。"""
    return list(_INCIDENT_STORE.values())


def delete_known_incident(incident_id: str) -> bool:
    """删除知识库条目。"""
    if incident_id in _INCIDENT_STORE:
        del _INCIDENT_STORE[incident_id]
        return True
    return False


def clear_incident_knowledge_base() -> int:
    """清空缺陷知识库。"""
    c = len(_INCIDENT_STORE)
    _INCIDENT_STORE.clear()
    return c
