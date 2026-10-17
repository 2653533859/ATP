"""增量筛选漏测风险动态防线看门狗服务 (T4.1)

严防增量精准测试中的过度裁剪导致核心业务缺陷逃逸与严重漏测风险:
1. 核心关键业务域 (支付/权限/结算/计费) 基线保底防线强校验;
2. 极端零用例推荐与高危符号签名改动安全熔断器 (Extreme Pruning Circuit Breaker);
3. 漏测风险多维健康度评分模型 (Leak Safety Scorer, 0~100);
4. 核心用例智能自动补偿注入与阻断裁决器 (RegressionLeakAuditReport)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.services.code_diff_symbol_extractor import (
    ChangedSymbolItem,
    SymbolChangeSeverity,
)
from app.services.symbol_call_graph_mapper import PrecisionImpactAnalysisResult


class LeakGuardVerdict(str, enum.Enum):
    ALLOW = "ALLOW"  # 安全合规，允许执行增量回归
    COMPENSATE_AND_ALLOW = "COMPENSATE_AND_ALLOW"  # 存在核心影响，已自动补充核心保底用例后放行
    BLOCK = "BLOCK"  # 存在严重漏测逃逸风险，强行阻断并回退全量/模块回归


class LeakRiskLevel(str, enum.Enum):
    SAFE = "SAFE"  # 低风险 (Score >= 85)
    WARN = "WARN"  # 中风险 (60 <= Score < 85)，需补偿
    CRITICAL = "CRITICAL"  # 严重漏测风险 (Score < 60)，禁止合流


# 核心业务关键词黑名单（触碰时必须强制执行核心基线）
_CRITICAL_DOMAIN_KEYWORDS: Set[str] = {
    "pay",
    "payment",
    "checkout",
    "billing",
    "auth",
    "login",
    "token",
    "permission",
    "refund",
}

# 核心领域预置保底兜底用例集合
_CRITICAL_BASELINE_COMPENSATION_CASES: Dict[str, List[str]] = {
    "pay": ["case_order_checkout_flow"],
    "payment": ["case_order_checkout_flow"],
    "checkout": ["case_order_checkout_flow"],
    "refund": ["case_order_checkout_flow"],
    "auth": ["case_user_login_success"],
    "login": ["case_user_login_success"],
    "token": ["case_user_login_success"],
    "permission": ["case_user_profile_query"],
}


@dataclass
class RegressionLeakAuditReport:
    report_id: str
    analysis_id: str
    verdict: LeakGuardVerdict
    safety_score: float  # 0.0 ~ 100.0
    risk_level: LeakRiskLevel
    original_recommended_cases: List[str]
    compensated_cases: List[str]
    final_approved_cases: List[str]
    violations: List[str]
    recommendations: List[str]
    audited_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "analysis_id": self.analysis_id,
            "verdict": self.verdict.value,
            "safety_score": round(self.safety_score, 1),
            "risk_level": self.risk_level.value,
            "original_recommended_cases": self.original_recommended_cases,
            "compensated_cases": self.compensated_cases,
            "final_approved_cases": self.final_approved_cases,
            "violations": self.violations,
            "recommendations": self.recommendations,
            "audited_at": self.audited_at,
        }


def audit_precision_regression_leak(
    recommend_result: PrecisionImpactAnalysisResult,
    changed_symbols: Optional[List[ChangedSymbolItem]] = None,
    enforce_critical_baseline: bool = True,
) -> RegressionLeakAuditReport:
    """严密审计增量用例推荐结果，防止过度裁剪造成高危缺陷逃逸"""
    report_id = f"sec_leak_{uuid.uuid4().hex[:10]}"
    base_score = 100.0

    violations: List[str] = []
    recommendations: List[str] = []
    compensated_cases: Set[str] = set()

    orig_cases = [c.case_id for c in recommend_result.impacted_cases]

    # 1. 极端裁剪熔断防御: 如果代码发生变动，但推荐用例为 0，且全量用例规模大于 10
    if len(recommend_result.changed_symbols) > 0 and len(orig_cases) == 0:
        if recommend_result.total_cases_in_suite > 10:
            violations.append(
                f"高危熔断: 探测到 {len(recommend_result.changed_symbols)} 处代码符号变更，但推荐用例数为 0，疑似调用链断裂或未收录测试血缘！"
            )
            base_score -= 60.0

    # 2. 检查是否有 CRITICAL 级别的签名变动未被覆盖
    if changed_symbols:
        critical_syms = [s for s in changed_symbols if s.severity == SymbolChangeSeverity.CRITICAL]
        if critical_syms and len(orig_cases) < len(critical_syms):
            violations.append(
                f"存在 {len(critical_syms)} 处函数入参签名核心变动，但推荐用例规模仅 {len(orig_cases)} 条，存在未覆盖的调用风险"
            )
            base_score -= 25.0

    # 3. 核心关键业务域基线保底强校验
    touched_critical_domains: Set[str] = set()
    for sym_name in recommend_result.changed_symbols:
        s_lower = sym_name.lower()
        for kw in _CRITICAL_DOMAIN_KEYWORDS:
            if kw in s_lower:
                touched_critical_domains.add(kw)

    for domain in touched_critical_domains:
        expected_cases = _CRITICAL_BASELINE_COMPENSATION_CASES.get(domain, [])
        # 检查推荐集合是否包含保底用例
        has_baseline = any(c in orig_cases for c in expected_cases)
        if not has_baseline:
            if enforce_critical_baseline:
                for c in expected_cases:
                    compensated_cases.add(c)
                recommendations.append(f"变更触碰核心关键域 [{domain}]，自动补充注入核心保底用例: {expected_cases}")
                base_score -= 10.0
            else:
                violations.append(f"代码触碰核心域 [{domain}]，但未纳入基线回归用例")
                base_score -= 20.0

    final_score = max(0.0, min(100.0, base_score))

    # 裁决判断
    if final_score < 60.0 or any("高危熔断" in v for v in violations):
        verdict = LeakGuardVerdict.BLOCK
        risk = LeakRiskLevel.CRITICAL
        recommendations.append("漏测风险极高，已强制阻断精准增量，建议回退至全量回归测试套件")
    elif len(compensated_cases) > 0 or final_score < 85.0:
        verdict = LeakGuardVerdict.COMPENSATE_AND_ALLOW
        risk = LeakRiskLevel.WARN
        recommendations.append("已激活核心基线保底防线，追加必要核心用例后允许放行")
    else:
        verdict = LeakGuardVerdict.ALLOW
        risk = LeakRiskLevel.SAFE
        recommendations.append("增量推荐用例集覆盖完整，防线评估安全合规，允许执行增量回归")

    final_cases = sorted(list(set(orig_cases) | compensated_cases))

    return RegressionLeakAuditReport(
        report_id=report_id,
        analysis_id=recommend_result.analysis_id,
        verdict=verdict,
        safety_score=final_score,
        risk_level=risk,
        original_recommended_cases=orig_cases,
        compensated_cases=sorted(list(compensated_cases)),
        final_approved_cases=final_cases,
        violations=violations,
        recommendations=recommendations,
    )
