"""Project-aware, bounded retrieval helpers used by Hermes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.knowledge import make_excerpt, redact_knowledge_tags, redact_knowledge_text, score_text


@dataclass(frozen=True, slots=True)
class HermesCandidate:
    source_type: str
    source_id: int
    project_id: int | None
    title: str
    body: str
    source_ref: str | None
    path: str
    tags: tuple[str, ...] = ()
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class HermesRankedSource:
    source_type: str
    source_id: int
    project_id: int | None
    title: str
    excerpt: str
    source_ref: str | None
    path: str
    match_terms: tuple[str, ...]
    match_score: int
    updated_at: datetime | None


def _timestamp(value: datetime | None) -> float:
    if value is None:
        return 0.0
    normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return normalized.timestamp()


def rank_candidates(query: str, candidates: list[HermesCandidate], limit: int) -> list[HermesRankedSource]:
    """Return only matching, redacted source summaries in a stable order."""
    ranked: list[HermesRankedSource] = []
    for candidate in candidates:
        safe_title = redact_knowledge_text(candidate.title, limit=256) or "未命名来源"
        safe_body = redact_knowledge_text(candidate.body, limit=50_000) or ""
        safe_tags = tuple(redact_knowledge_tags(list(candidate.tags)))
        score, terms = score_text(query, safe_title, safe_body, list(safe_tags))
        if score <= 0:
            continue
        ranked.append(
            HermesRankedSource(
                source_type=candidate.source_type,
                source_id=candidate.source_id,
                project_id=candidate.project_id,
                title=safe_title,
                excerpt=make_excerpt(safe_body, query),
                source_ref=redact_knowledge_text(candidate.source_ref, limit=512),
                path=candidate.path,
                match_terms=tuple(terms),
                match_score=score,
                updated_at=candidate.updated_at,
            )
        )
    ranked.sort(
        key=lambda item: (
            -item.match_score,
            -_timestamp(item.updated_at),
            item.source_type,
            item.source_id,
        )
    )
    return ranked[:limit]


def build_answer(sources: list[HermesRankedSource]) -> tuple[str, str]:
    """Build a safe explanation without echoing the user's query or source body."""
    if not sources:
        return (
            "当前项目没有找到匹配的需求、知识或用例来源。可以换用业务关键词，或先补充可检索的项目资产。",
            "no_results",
        )
    references = "；".join(
        f"[{source.source_ref or f'{source.source_type}-{source.source_id}'}] {source.title}" for source in sources[:5]
    )
    return (
        f"已从当前项目检索到 {len(sources)} 条相关来源：{references}。结果是可追溯的检索摘要，打开来源可查看完整内容；Hermes 不会自动修改测试资产。",
        "project_retrieval",
    )
