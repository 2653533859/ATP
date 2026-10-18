"""大模型幻觉率统计与事实一致性校验器服务 (T1.2)

基于自然语言事实比对、数值一致性与否定极性检验，精确度量大模型生成内容的幻觉偏离:
1. 幻觉类型与严重等级分类 (FABRICATED_ENTITY, NUMERICAL_CONFLICT, LOGICAL_CONTRADICTION);
2. 细粒度断言事实比对算法 (数值冲突检出、否定词极性反转检出、未登记虚构实体检出);
3. 事实一致性得分与幻觉率精算 (hallucination_rate_pct = 幻觉断言数 / 总断言数);
4. 结构化幻觉审计报告输出 (HallucinationAuditReport & HallucinationFinding)。
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class HallucinationType(str, enum.Enum):
    FABRICATED_ENTITY = "FABRICATED_ENTITY"  # 虚假实体捏造 (不存在的接口/表名/配置)
    NUMERICAL_CONFLICT = "NUMERICAL_CONFLICT"  # 关键数值冲突 (阈值/时间/百分比矛盾)
    LOGICAL_CONTRADICTION = "LOGICAL_CONTRADICTION"  # 逻辑断言反转 (如“严禁”被说成“可以”)
    UNGROUNDED_EXTRAPOLATION = "UNGROUNDED_EXTRAPOLATION"  # 脱离基准的无根外推


class HallucinationSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"  # 致命幻觉 (可能引发系统故障或安全漏洞)
    MAJOR = "MAJOR"  # 严重幻觉 (核心业务参数或结论错误)
    MINOR = "MINOR"  # 轻微幻觉 (细节偏离，不影响主要判断)


class HallucinationVerdict(str, enum.Enum):
    FACTUAL_PASS = "FACTUAL_PASS"  # 事实一致，无明显幻觉
    SUSPICIOUS_DRIFT = "SUSPICIOUS_DRIFT"  # 存在可疑外推或轻微细节偏差
    CRITICAL_HALLUCINATION = "CRITICAL_HALLUCINATION"  # 检出严重或致命事实幻觉！


@dataclass
class HallucinationFinding:
    finding_id: str
    claim_sentence: str
    hallucination_type: HallucinationType
    severity: HallucinationSeverity
    conflict_detail: str
    golden_reference: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "claim_sentence": self.claim_sentence,
            "hallucination_type": self.hallucination_type.value,
            "severity": self.severity.value,
            "conflict_detail": self.conflict_detail,
            "golden_reference": self.golden_reference,
        }


@dataclass
class HallucinationAuditReport:
    audit_id: str
    model_name: str
    query: str
    answer: str
    total_claims_count: int
    hallucinated_claims_count: int
    hallucination_rate_pct: float  # 0.0 ~ 100.0%
    factual_consistency_score: float  # 0.0 ~ 100.0
    verdict: HallucinationVerdict
    findings: List[HallucinationFinding]
    summary: str
    audited_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "model_name": self.model_name,
            "query": self.query,
            "answer": self.answer,
            "total_claims_count": self.total_claims_count,
            "hallucinated_claims_count": self.hallucinated_claims_count,
            "hallucination_rate_pct": round(self.hallucination_rate_pct, 1),
            "factual_consistency_score": round(self.factual_consistency_score, 1),
            "verdict": self.verdict.value,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "audited_at": self.audited_at,
        }


# 常见的否定词与极性词
POLARITY_OPPOSITES = [
    ("严禁", "可以"),
    ("禁止", "允许"),
    ("支持", "不支持"),
    ("启用", "禁用"),
    ("开启", "关闭"),
    ("通过", "失败"),
    ("是", "不是"),
]


def _extract_numbers(text: str) -> List[str]:
    """提取文本中的所有关键数字与百分比"""
    return re.findall(r"\d+(?:\.\d+)?%?", text)


def _split_into_sentences(text: str) -> List[str]:
    """切分文本为独立句子"""
    raw = re.split(r"[。！？\n；;!?]+", text.strip())
    return [s.strip() for s in raw if len(s.strip()) > 3]


def _extract_ngrams(text: str, n: int = 2) -> set[str]:
    ch_text = re.sub(r"[^\u4e00-\u9fa5]", "", text)
    if len(ch_text) < n:
        return set()
    return set(ch_text[i : i + n] for i in range(len(ch_text) - n + 1))


def _check_numerical_conflicts(claim: str, golden_facts_str: str) -> Optional[Tuple[str, str]]:
    """检测断言句子中是否存在与黄金事实直接冲突的数字/阈值"""
    claim_nums = _extract_numbers(claim)
    if not claim_nums:
        return None

    golden_nums = set(_extract_numbers(golden_facts_str))
    for num in claim_nums:
        if num not in golden_nums and len(num) >= 2:
            return num, f"断言提及数值 [{num}]，但黄金事实中仅记录数值集合: {sorted(golden_nums)}"
    return None


def _check_polarity_conflicts(claim: str, golden_facts_str: str) -> Optional[Tuple[str, str]]:
    """检测断言是否存在极性反转或矛盾（如'严禁写入'被模型说成'可以写入'）"""
    g_claim = _extract_ngrams(claim)
    g_golden = _extract_ngrams(golden_facts_str)
    common_ngrams = g_claim & g_golden
    is_topically_related = len(common_ngrams) >= 3

    for pos, neg in POLARITY_OPPOSITES:
        if is_topically_related:
            if pos in claim and neg in golden_facts_str:
                return (
                    f"极性反转: 断言包含 [{pos}]，而黄金事实声明 [{neg}]",
                    f"相关事实焦点重叠度: {len(common_ngrams)} 处词元",
                )
            elif neg in claim and pos in golden_facts_str:
                return (
                    f"极性反转: 断言包含 [{neg}]，而黄金事实声明 [{pos}]",
                    f"相关事实焦点重叠度: {len(common_ngrams)} 处词元",
                )
    return None


def detect_llm_hallucinations(
    query: str,
    answer: str,
    golden_facts: List[str],
    model_name: str = "qwen-2.5-72b",
) -> HallucinationAuditReport:
    """大模型回答事实一致性与幻觉深度审计分析引擎"""
    audit_id = f"hal_aud_{uuid.uuid4().hex[:10]}"
    claims = _split_into_sentences(answer)
    golden_combined = " ".join(golden_facts)

    findings: List[HallucinationFinding] = []

    for i, cl in enumerate(claims):
        fid = f"find_{i+1:02d}"

        # 1. 检验逻辑与极性反转 (Logical Contradiction)
        pol_conflict = _check_polarity_conflicts(cl, golden_combined)
        if pol_conflict:
            findings.append(
                HallucinationFinding(
                    finding_id=fid,
                    claim_sentence=cl,
                    hallucination_type=HallucinationType.LOGICAL_CONTRADICTION,
                    severity=HallucinationSeverity.CRITICAL,
                    conflict_detail=pol_conflict[0],
                    golden_reference=pol_conflict[1],
                )
            )
            continue

        # 2. 检验关键数值与阈值冲突 (Numerical Conflict)
        num_conflict = _check_numerical_conflicts(cl, golden_combined)
        if num_conflict:
            findings.append(
                HallucinationFinding(
                    finding_id=fid,
                    claim_sentence=cl,
                    hallucination_type=HallucinationType.NUMERICAL_CONFLICT,
                    severity=HallucinationSeverity.MAJOR,
                    conflict_detail=num_conflict[1],
                    golden_reference=golden_combined[:120] + "...",
                )
            )
            continue

        # 3. 检验无根实体虚构 (Fabricated Entity)
        # 查找被单双引号括起或 CamelCase / snake_case 英文实体
        entities = re.findall(r"`([^`]+)`|'([^']+)'|([a-zA-Z0-9_]{5,}\b)", cl)
        found_fab = False
        for g1, g2, g3 in entities:
            ent = g1 or g2 or g3
            if ent.lower() not in golden_combined.lower() and not ent.isdigit():
                findings.append(
                    HallucinationFinding(
                        finding_id=fid,
                        claim_sentence=cl,
                        hallucination_type=HallucinationType.FABRICATED_ENTITY,
                        severity=HallucinationSeverity.MAJOR,
                        conflict_detail=f"实体 [{ent}] 未在黄金知识事实库中登记，疑似模型捏造虚假实体",
                        golden_reference="黄金事实库无匹配记录",
                    )
                )
                found_fab = True
                break
        if found_fab:
            continue

    total_claims = max(1, len(claims))
    hallucinated_claims = len(findings)
    hallucination_rate = (hallucinated_claims / total_claims) * 100.0
    consistency_score = max(0.0, 100.0 - hallucination_rate)

    has_critical = any(f.severity == HallucinationSeverity.CRITICAL for f in findings)
    if has_critical or hallucination_rate > 35.0:
        verdict = HallucinationVerdict.CRITICAL_HALLUCINATION
    elif hallucinated_claims > 0:
        verdict = HallucinationVerdict.SUSPICIOUS_DRIFT
    else:
        verdict = HallucinationVerdict.FACTUAL_PASS

    summary = (
        f"模型 [{model_name}] 事实一致性审计结论为 [{verdict.value}]: "
        f"检测 {len(claims)} 个断言事实，发现 {hallucinated_claims} 处幻觉偏离 "
        f"(幻觉率: {hallucination_rate:.1f}%, 事实一致性得分: {consistency_score:.1f}分)。"
    )

    return HallucinationAuditReport(
        audit_id=audit_id,
        model_name=model_name,
        query=query,
        answer=answer,
        total_claims_count=len(claims),
        hallucinated_claims_count=hallucinated_claims,
        hallucination_rate_pct=hallucination_rate,
        factual_consistency_score=consistency_score,
        verdict=verdict,
        findings=findings,
        summary=summary,
    )
