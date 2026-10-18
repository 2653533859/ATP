"""RAG 知识检索召回与上下文相关度精算器服务 (T1.1)

实现业界标准的 RAG Triad (检索增强生成三元组) 质量评估模型:
1. 上下文相关度 (Context Relevance): 衡量检索召回片段与用户 Query 的覆盖与匹配度;
2. 知识忠实度 (Groundedness / Faithfulness): 拆解模型回答断言，校验是否严格由检索知识库事实支撑 (消灭无根事实);
3. 答案准确度 (Answer Relevance): 衡量最终回答是否完整对齐并准确解答了用户的问题意图;
4. 综合三元组评分精算与可解释引用溯源 (RagTriadEvaluationReport: EXCELLENT | GOOD | MARGINAL | POOR)。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class RagChunkItem:
    chunk_id: str
    content: str
    relevance_score: float  # 0.0 ~ 1.0
    source_doc: str = "kb_doc_default"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "relevance_score": round(self.relevance_score, 3),
            "source_doc": self.source_doc,
        }


@dataclass
class ClaimAttribution:
    claim_text: str  # 回答中提炼的断言事实
    is_grounded: bool  # 是否有检索事实明确支撑
    supporting_chunk_id: Optional[str]
    evidence_snippet: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RagTriadEvaluationReport:
    evaluation_id: str
    query: str
    answer: str
    context_relevance: float  # 0.0 ~ 1.0 上下文相关度
    groundedness: float  # 0.0 ~ 1.0 知识忠实度 (无幻觉比率)
    answer_relevance: float  # 0.0 ~ 1.0 答案相关度
    composite_score: float  # 0.0 ~ 100.0 三元组综合得分
    grade: str  # EXCELLENT | GOOD | MARGINAL | POOR
    chunks: List[RagChunkItem]
    claim_attributions: List[ClaimAttribution]
    summary: str
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "query": self.query,
            "answer": self.answer,
            "context_relevance": round(self.context_relevance, 3),
            "groundedness": round(self.groundedness, 3),
            "answer_relevance": round(self.answer_relevance, 3),
            "composite_score": round(self.composite_score, 1),
            "grade": self.grade,
            "chunks": [c.to_dict() for c in self.chunks],
            "claim_attributions": [ca.to_dict() for ca in self.claim_attributions],
            "summary": self.summary,
            "evaluated_at": self.evaluated_at,
        }


def _tokenize_terms(text: str) -> List[str]:
    """提取中英文与符号关键词词元"""
    cleaned = re.sub(r"[^\w\u4e00-\u9fa5]+", " ", text.lower()).strip()
    # 拆分英文单词与中文单字
    tokens: List[str] = []
    for part in cleaned.split():
        if re.search(r"[\u4e00-\u9fa5]", part):
            # 中文按字切分
            tokens.extend(list(part))
        else:
            tokens.append(part)
    return [t for t in tokens if len(t) > 0]


def _calculate_overlap_ratio(source_terms: List[str], target_terms: List[str]) -> float:
    """计算源词元集合在目标词元集合中的覆盖率"""
    if not source_terms or not target_terms:
        return 0.0
    set_target = set(target_terms)
    matches = sum(1 for t in source_terms if t in set_target)
    return min(1.0, matches / max(1, len(set(source_terms))))


def _split_into_claims(answer: str) -> List[str]:
    """将模型回答切分为独立断言事实句"""
    raw_sentences = re.split(r"[。！？\n；;!?]+", answer.strip())
    return [s.strip() for s in raw_sentences if len(s.strip()) > 3]


# 常见停用词与疑问词过滤
INTERROGATIVES = {
    "如",
    "何",
    "保",
    "证",
    "怎",
    "么",
    "样",
    "哪",
    "些",
    "什",
    "谁",
    "几",
    "多",
    "少",
    "吗",
    "呢",
    "吧",
    "的",
    "了",
    "在",
    "与",
    "和",
    "为",
    "执",
    "行",
    "进",
    "以",
    "及",
    "等",
}


def evaluate_rag_triad(
    query: str,
    contexts: List[str],
    answer: str,
    source_docs: Optional[List[str]] = None,
) -> RagTriadEvaluationReport:
    """RAG 核心三元组质量评测引擎"""
    eval_id = f"rag_eval_{uuid.uuid4().hex[:10]}"
    q_tokens = _tokenize_terms(query)
    q_content = [t for t in q_tokens if t not in INTERROGATIVES]
    if not q_content:
        q_content = q_tokens

    ans_tokens = _tokenize_terms(answer)
    docs = source_docs or [f"doc_chunk_{i+1}" for i in range(len(contexts))]

    # 1. 计算上下文相关度 (Context Relevance)
    chunk_items: List[RagChunkItem] = []
    chunk_scores: List[float] = []

    for i, c_text in enumerate(contexts):
        cid = f"chk_{i+1:02d}"
        c_tokens = _tokenize_terms(c_text)
        relevance = _calculate_overlap_ratio(q_content, c_tokens)
        chunk_scores.append(relevance)
        chunk_items.append(
            RagChunkItem(
                chunk_id=cid,
                content=c_text,
                relevance_score=relevance,
                source_doc=docs[i] if i < len(docs) else "doc_default",
            )
        )

    all_context_tokens = _tokenize_terms(" ".join(contexts))
    union_relevance = _calculate_overlap_ratio(q_content, all_context_tokens)
    max_chunk_relevance = max(chunk_scores) if chunk_scores else 0.0
    context_relevance = 0.5 * union_relevance + 0.5 * max_chunk_relevance

    # 2. 计算知识忠实度 (Groundedness / Faithfulness)
    claims = _split_into_claims(answer)
    claim_attributions: List[ClaimAttribution] = []
    grounded_count = 0

    for cl in claims:
        cl_tokens = _tokenize_terms(cl)
        # 寻找匹配最佳的支撑 Chunk
        best_chunk_id: Optional[str] = None
        best_overlap = 0.0
        for chk in chunk_items:
            ov = _calculate_overlap_ratio(cl_tokens, _tokenize_terms(chk.content))
            if ov > best_overlap:
                best_overlap = ov
                best_chunk_id = chk.chunk_id

        # 只要该断言与上下文有 30% 以上实质重叠，或包含的核心命名实体全命中且重叠 >= 20%
        key_entities = [t for t in cl_tokens if len(t) >= 3 and not t.isdigit()]
        has_key_entity = bool(
            key_entities and all(e in all_context_tokens for e in key_entities) and best_overlap >= 0.20
        )
        is_grounded = best_overlap >= 0.30 or has_key_entity

        if is_grounded:
            grounded_count += 1
            snippet = f"匹配片段 {best_chunk_id} (重合度 {best_overlap:.0%})"
        else:
            snippet = "无检索上下文事实依据 (疑似模型无根幻觉/自带常识)"

        claim_attributions.append(
            ClaimAttribution(
                claim_text=cl,
                is_grounded=is_grounded,
                supporting_chunk_id=best_chunk_id if is_grounded else None,
                evidence_snippet=snippet,
            )
        )

    groundedness = grounded_count / max(1, len(claims)) if claims else 1.0

    # 3. 计算答案相关度 (Answer Relevance)
    direct_overlap = _calculate_overlap_ratio(q_content, ans_tokens)
    context_bridge = 0.5 * context_relevance + 0.5 * _calculate_overlap_ratio(ans_tokens, all_context_tokens)
    answer_relevance = max(direct_overlap, context_bridge)

    # 4. 精算 RAG 三元组综合得分 (满分 100)
    # 权重配比: 上下文相关度 35%, 忠实度 35%, 答案相关度 30%
    composite = (context_relevance * 0.35 + groundedness * 0.35 + answer_relevance * 0.30) * 100.0
    composite = max(0.0, min(100.0, composite))

    if composite >= 90.0:
        grade = "EXCELLENT"
    elif composite >= 75.0:
        grade = "GOOD"
    elif composite >= 60.0:
        grade = "MARGINAL"
    else:
        grade = "POOR"

    summary = (
        f"RAG 三元组综合评测得出 {composite:.1f} 分 ({grade}): "
        f"上下文相关度 {context_relevance:.1%} (召回 {len(contexts)} 个 Chunk), "
        f"知识忠实度 {groundedness:.1%} ({grounded_count}/{len(claims)} 个断言事实溯源), "
        f"回答针对性 {answer_relevance:.1%}。"
    )

    return RagTriadEvaluationReport(
        evaluation_id=eval_id,
        query=query,
        answer=answer,
        context_relevance=context_relevance,
        groundedness=groundedness,
        answer_relevance=answer_relevance,
        composite_score=composite,
        grade=grade,
        chunks=chunk_items,
        claim_attributions=claim_attributions,
        summary=summary,
    )
