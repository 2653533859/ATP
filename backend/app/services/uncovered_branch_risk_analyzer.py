"""未覆盖高危分支路径漏洞挖掘器服务 (T2.1)

结合源码 AST 与红黄未覆盖行号，深度挖掘未覆盖代码中的高危业务分支:
1. 分支高危业务语义识别 (支付资金、权限鉴权、事务回滚、降级熔断、常规分支);
2. 缺陷隐患与严重度智能定级 (P0_BLOCKING 阻塞级、P1_CRITICAL 严重级、P2_MAJOR 一般级);
3. 触发条件表达式与未测后果推演 (condition_expr & consequence_summary);
4. 综合高危分支风险报告输出 (UncoveredBranchAnalysisReport)。
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.diff_coverage_staining_engine import DiffCoverageReport


class UncoveredBranchCategory(str, enum.Enum):
    PAYMENT_FINANCIAL = "PAYMENT_FINANCIAL"  # 资金支付/结算/计费逻辑 (极高危)
    AUTH_SECURITY = "AUTH_SECURITY"  # 安全鉴权/令牌校验/越权防护 (极高危)
    EXCEPTION_ROLLBACK = "EXCEPTION_ROLLBACK"  # 异常抛错/事务回滚/数据完整性 (高危)
    CIRCUIT_BREAKER_FALLBACK = "CIRCUIT_BREAKER_FALLBACK"  # 熔断降级/重试兜底 (高危)
    GENERAL_BUSINESS = "GENERAL_BUSINESS"  # 常规业务分支逻辑 (中危)


class BranchRiskSeverity(str, enum.Enum):
    P0_BLOCKING = "P0_BLOCKING"  # 核心资损或安全漏洞，发布强阻断
    P1_CRITICAL = "P1_CRITICAL"  # 严重异常或降级缺失，必须在下一迭代补齐
    P2_MAJOR = "P2_MAJOR"  # 一般业务分支


@dataclass
class UncoveredBranchItem:
    branch_id: str
    file_path: str
    line_start: int
    line_end: int
    code_snippet: str
    category: UncoveredBranchCategory
    severity: BranchRiskSeverity
    reason: str
    condition_expr: str
    consequence_summary: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["severity"] = self.severity.value
        return d


@dataclass
class UncoveredBranchAnalysisReport:
    report_id: str
    diff_report_id: str
    total_uncovered_branches: int
    p0_count: int
    p1_count: int
    p2_count: int
    branches: List[UncoveredBranchItem]
    is_release_blocked: bool
    analyzed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "diff_report_id": self.diff_report_id,
            "total_uncovered_branches": self.total_uncovered_branches,
            "p0_count": self.p0_count,
            "p1_count": self.p1_count,
            "p2_count": self.p2_count,
            "is_release_blocked": self.is_release_blocked,
            "branches": [b.to_dict() for b in self.branches],
            "analyzed_at": self.analyzed_at,
        }


# 模式特征匹配规则
PAYMENT_KEYWORDS = [
    r"pay",
    r"payment",
    r"charge",
    r"refund",
    r"amount",
    r"balance",
    r"fee",
    r"price",
    r"currency",
    r"wallet",
    r"order_total",
    r"discount",
]
AUTH_KEYWORDS = [
    r"auth",
    r"token",
    r"permission",
    r"role",
    r"credential",
    r"secret",
    r"signature",
    r"jwt",
    r"forbidden",
    r"unauthorized",
    r"access_denied",
]
EXCEPTION_KEYWORDS = [
    r"raise\s+",
    r"throw\s+",
    r"rollback",
    r"except\s+",
    r"catch\s+",
    r"abort\(",
    r"exception",
    r"error_handler",
]
FALLBACK_KEYWORDS = [r"fallback", r"circuit", r"retry", r"timeout", r"cache_get", r"degrade"]


def _match_category_and_severity(
    code_snippet: str,
    condition_expr: str,
) -> tuple[UncoveredBranchCategory, BranchRiskSeverity, str, str]:
    """通过代码语义特征判定未覆盖分支的业务分类与风险等级"""
    snip_lower = code_snippet.lower()
    text = f"{code_snippet}\n{condition_expr}".lower()

    # 1. 优先判定代码片段自身是否明确包含异常抛错或事务回滚
    for kw in EXCEPTION_KEYWORDS:
        if re.search(kw, snip_lower):
            return (
                UncoveredBranchCategory.EXCEPTION_ROLLBACK,
                BranchRiskSeverity.P1_CRITICAL,
                f"命中异常控制关键字 [{kw}]，该分支包含事务回滚或主动中断逻辑",
                "异常处理路径未经验证，在生产异常崩溃时可能引发脏数据残留或未受管异常外溢",
            )

    # 2. 资金支付相关判定
    for kw in PAYMENT_KEYWORDS:
        if re.search(r"\b" + kw + r"\b", text):
            return (
                UncoveredBranchCategory.PAYMENT_FINANCIAL,
                BranchRiskSeverity.P0_BLOCKING,
                f"命中资金敏感关键字 [{kw}]，该代码分支涉及核心财务、支付计费或订单金额核算",
                "若在生产环境触发该未测异常或扣款分支，极可能造成资损、重复扣款或结算对账不平",
            )

    # 3. 安全鉴权相关判定
    for kw in AUTH_KEYWORDS:
        if re.search(r"\b" + kw + r"\b", text):
            return (
                UncoveredBranchCategory.AUTH_SECURITY,
                BranchRiskSeverity.P0_BLOCKING,
                f"命中权限鉴权关键字 [{kw}]，该分支涉及身份验证或访问控制拦截",
                "若该鉴权分支存在未测漏洞，攻击者可能越权调用敏感接口或绕过访问控制",
            )

    # 4. 降级重试与熔断兜底判定
    for kw in FALLBACK_KEYWORDS:
        if re.search(r"\b" + kw + r"\b", text):
            return (
                UncoveredBranchCategory.CIRCUIT_BREAKER_FALLBACK,
                BranchRiskSeverity.P1_CRITICAL,
                f"命中容灾降级关键字 [{kw}]，该分支包含旁路容灾兜底逻辑",
                "降级与重试机制未被测试覆盖，下游超时时无法确保旁路能安全接管",
            )

    # 5. 普通业务分支
    return (
        UncoveredBranchCategory.GENERAL_BUSINESS,
        BranchRiskSeverity.P2_MAJOR,
        "普通业务条件分支逻辑",
        "可能存在未测边界条件导致特定边缘业务场景展现异常",
    )


def analyze_uncovered_branch_risks(
    diff_report: DiffCoverageReport,
    source_files: Optional[Dict[str, str]] = None,
) -> UncoveredBranchAnalysisReport:
    """深度挖掘未覆盖代码行中的高危业务分支与潜在缺陷风险"""
    report_id = f"ubr_{uuid.uuid4().hex[:10]}"
    sources = source_files or {}
    uncovered_items: List[UncoveredBranchItem] = []

    for file_path, file_staining in diff_report.files.items():
        # 提取红色未覆盖与黄色部分覆盖行号
        target_lines = sorted(set(file_staining.red_uncovered_lines + file_staining.yellow_partial_lines))
        if not target_lines:
            continue

        file_code = sources.get(file_path, "")
        code_lines = file_code.splitlines() if file_code else []

        # 将相邻或连续的未覆盖行合并为连续分支块
        blocks: List[List[int]] = []
        cur_block: List[int] = []

        for ln in target_lines:
            if not cur_block:
                cur_block.append(ln)
            elif ln == cur_block[-1] + 1:
                cur_block.append(ln)
            else:
                blocks.append(cur_block)
                cur_block = [ln]
        if cur_block:
            blocks.append(cur_block)

        for blk in blocks:
            start_ln = blk[0]
            end_ln = blk[-1]

            # 提取代码片段
            if code_lines and start_ln <= len(code_lines):
                snippet_lines = code_lines[start_ln - 1 : min(end_ln, len(code_lines))]
                snippet = "\n".join(snippet_lines)
            else:
                snippet = f"Line {start_ln} ~ {end_ln} (uncovered execution block)"

            # 探测当前行或向上回溯上层条件语句
            condition_expr = ""
            if code_lines and start_ln <= len(code_lines):
                cur_l = code_lines[start_ln - 1].strip()
                if cur_l.startswith(("if ", "elif ", "while ", "case ", "switch ", "except ", "except:", "try:")):
                    condition_expr = cur_l
                elif start_ln > 1:
                    for lookback in range(start_ln - 2, max(-1, start_ln - 8), -1):
                        raw_l = code_lines[lookback].strip()
                        if raw_l.startswith(
                            ("if ", "elif ", "while ", "case ", "switch ", "except ", "except:", "try:")
                        ):
                            condition_expr = raw_l
                            break

            cat, sev, reason, consequence = _match_category_and_severity(snippet, condition_expr)

            uncovered_items.append(
                UncoveredBranchItem(
                    branch_id=f"br_{uuid.uuid4().hex[:8]}",
                    file_path=file_path,
                    line_start=start_ln,
                    line_end=end_ln,
                    code_snippet=snippet,
                    category=cat,
                    severity=sev,
                    reason=reason,
                    condition_expr=condition_expr or "Direct conditional or statement block",
                    consequence_summary=consequence,
                )
            )

    p0 = sum(1 for b in uncovered_items if b.severity == BranchRiskSeverity.P0_BLOCKING)
    p1 = sum(1 for b in uncovered_items if b.severity == BranchRiskSeverity.P1_CRITICAL)
    p2 = sum(1 for b in uncovered_items if b.severity == BranchRiskSeverity.P2_MAJOR)

    # 存在 P0 级别高危分支未覆盖即触发发布强阻断
    is_blocked = p0 > 0

    return UncoveredBranchAnalysisReport(
        report_id=report_id,
        diff_report_id=diff_report.diff_report_id,
        total_uncovered_branches=len(uncovered_items),
        p0_count=p0,
        p1_count=p1,
        p2_count=p2,
        branches=uncovered_items,
        is_release_blocked=is_blocked,
    )
