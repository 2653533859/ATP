"""自愈补丁防篡改与安全围栏看门狗服务 (T4.1)

严防 AI 自愈与断言演进中的恶意越权、虚假真值弱化 (Tautology) 与破坏性注入攻击:
1. 断言恒真恒等于 (assert True, 1==1) 与危险内置调用检测 (AST-based Tautology & Injection Detector);
2. 破坏性选择器 (*, body, //*) 与脚本注入防范 (Malicious & Overly Broad Locator Guard);
3. 自愈补丁全流程安全防伪审查与阻断判定 (SafetyGuardAuditReport)。
"""

from __future__ import annotations

import ast
import enum
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


class SafetyVerdict(str, enum.Enum):
    ALLOW = "ALLOW"  # 安全合规，允许采纳
    BLOCK = "BLOCK"  # 存在高危违规，阻断并拦截自动合流


class ViolationSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"  # 严重：恒真弱化、代码注入或破坏性定位器
    HIGH = "HIGH"  # 高危：过宽无特异性定位器
    MEDIUM = "MEDIUM"  # 中度：缺少边界限制或潜在隐患


class RuleCode(str, enum.Enum):
    TAUTOLOGY_ASSERTION_DETECTED = "TAUTOLOGY_ASSERTION_DETECTED"  # 恒真断言 (如 assert True)
    CODE_INJECTION_DETECTED = "CODE_INJECTION_DETECTED"  # 危险调用与注入 (如 eval, exec, os)
    OVERLY_BROAD_LOCATOR = "OVERLY_BROAD_LOCATOR"  # 过宽破坏性定位器 (如 *, body, //*)
    MALICIOUS_INJECTION_LOCATOR = "MALICIOUS_INJECTION_LOCATOR"  # 脚本/指令注入定位器
    EMPTY_ASSERTION_BODY = "EMPTY_ASSERTION_BODY"  # 空断言体或无断言语句


@dataclass
class SafetyViolationItem:
    rule_code: RuleCode
    severity: ViolationSeverity
    message: str
    offending_snippet: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_code": self.rule_code.value,
            "severity": self.severity.value,
            "message": self.message,
            "offending_snippet": self.offending_snippet,
        }


@dataclass
class SafetyGuardAuditReport:
    report_id: str
    verdict: SafetyVerdict
    violations: List[SafetyViolationItem]
    inspected_target_type: str  # "ASSERTION" | "LOCATOR" | "PATCH"
    inspected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "verdict": self.verdict.value,
            "violations": [v.to_dict() for v in self.violations],
            "inspected_target_type": self.inspected_target_type,
            "inspected_at": self.inspected_at,
        }


# 危险内置或敏感函数黑名单
_DANGEROUS_CALL_NAMES: Set[str] = {
    "eval",
    "exec",
    "open",
    "system",
    "popen",
    "spawn",
    "subprocess",
    "unlink",
    "remove",
    "rmdir",
    "__import__",
}

# 过宽/破坏性全屏定位器黑名单
_OVERLY_BROAD_LOCATORS: Set[str] = {
    "*",
    "body",
    "html",
    ":root",
    "//*",
    "//body",
    "//html",
    "/html/body",
    "div",
    "span",
}

# 恶意注入特征正则
_MALICIOUS_LOCATOR_PATTERNS = [
    re.compile(r"<script.*?>", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r";\s*rm\s+-rf", re.IGNORECASE),
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),
    re.compile(r"UNION\s+SELECT", re.IGNORECASE),
]


def audit_assertion_safety(
    assertion_code: str,
    _original_code: Optional[str] = None,
) -> SafetyGuardAuditReport:
    """静态审计演进断言代码，严防恒真弱化、代码注入与无意义断言"""
    report_id = f"sec_ast_{uuid.uuid4().hex[:10]}"
    violations: List[SafetyViolationItem] = []

    clean_code = assertion_code.strip()
    if not clean_code:
        violations.append(
            SafetyViolationItem(
                rule_code=RuleCode.EMPTY_ASSERTION_BODY,
                severity=ViolationSeverity.CRITICAL,
                message="断言代码为空，无法提供任何质量保障",
                offending_snippet="",
            )
        )
        return SafetyGuardAuditReport(
            report_id=report_id,
            verdict=SafetyVerdict.BLOCK,
            violations=violations,
            inspected_target_type="ASSERTION",
        )

    try:
        tree = ast.parse(clean_code)
    except SyntaxError as e:
        violations.append(
            SafetyViolationItem(
                rule_code=RuleCode.EMPTY_ASSERTION_BODY,
                severity=ViolationSeverity.CRITICAL,
                message=f"代码存在语法错误无法解析: {str(e)}",
                offending_snippet=clean_code,
            )
        )
        return SafetyGuardAuditReport(
            report_id=report_id,
            verdict=SafetyVerdict.BLOCK,
            violations=violations,
            inspected_target_type="ASSERTION",
        )

    has_assert_stmt = False

    for node in ast.walk(tree):
        # 1. 检查是否存在危险调用注入
        if isinstance(node, ast.Call):
            call_name = ""
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                call_name = node.func.attr

            if call_name in _DANGEROUS_CALL_NAMES:
                violations.append(
                    SafetyViolationItem(
                        rule_code=RuleCode.CODE_INJECTION_DETECTED,
                        severity=ViolationSeverity.CRITICAL,
                        message=f"检测到高危函数调用 '{call_name}'，阻断恶意代码执行",
                        offending_snippet=call_name,
                    )
                )

        # 2. 检查断言语句
        if isinstance(node, ast.Assert):
            has_assert_stmt = True
            # 模式 A: 直接 assert True 或 assert 1
            if isinstance(node.test, ast.Constant):
                if node.test.value is True or node.test.value == 1:
                    violations.append(
                        SafetyViolationItem(
                            rule_code=RuleCode.TAUTOLOGY_ASSERTION_DETECTED,
                            severity=ViolationSeverity.CRITICAL,
                            message="严禁将断言篡改为恒真表达式 (如 assert True / assert 1)",
                            offending_snippet=ast.unparse(node),
                        )
                    )

            # 模式 B: assert 1 == 1 或同常量比较
            elif isinstance(node.test, ast.Compare):
                if isinstance(node.test.left, ast.Constant):
                    for comp in node.test.comparators:
                        if isinstance(comp, ast.Constant) and comp.value == node.test.left.value:
                            violations.append(
                                SafetyViolationItem(
                                    rule_code=RuleCode.TAUTOLOGY_ASSERTION_DETECTED,
                                    severity=ViolationSeverity.CRITICAL,
                                    message=f"检测到同值比较的恒真断言: '{ast.unparse(node.test)}'",
                                    offending_snippet=ast.unparse(node),
                                )
                            )

    if not has_assert_stmt:
        violations.append(
            SafetyViolationItem(
                rule_code=RuleCode.EMPTY_ASSERTION_BODY,
                severity=ViolationSeverity.HIGH,
                message="代码中缺少明确的 assert 断言语句",
                offending_snippet=clean_code,
            )
        )

    verdict = (
        SafetyVerdict.BLOCK
        if any(v.severity in (ViolationSeverity.CRITICAL, ViolationSeverity.HIGH) for v in violations)
        else SafetyVerdict.ALLOW
    )

    return SafetyGuardAuditReport(
        report_id=report_id,
        verdict=verdict,
        violations=violations,
        inspected_target_type="ASSERTION",
    )


def audit_locator_safety(
    _locator_type: str,
    locator_value: str,
) -> SafetyGuardAuditReport:
    """审计自愈推荐定位器，防范过宽全屏捕获与恶意脚本注入"""
    report_id = f"sec_loc_{uuid.uuid4().hex[:10]}"
    violations: List[SafetyViolationItem] = []

    clean_val = locator_value.strip()

    # 1. 检查过宽破坏性选择器
    if clean_val.lower() in _OVERLY_BROAD_LOCATORS:
        violations.append(
            SafetyViolationItem(
                rule_code=RuleCode.OVERLY_BROAD_LOCATOR,
                severity=ViolationSeverity.CRITICAL,
                message=f"定位器 '{clean_val}' 作用域过宽，会误命中全局无特异性元素并导致雪崩",
                offending_snippet=clean_val,
            )
        )

    # 2. 检查恶意注入特征
    for pattern in _MALICIOUS_LOCATOR_PATTERNS:
        if pattern.search(clean_val):
            violations.append(
                SafetyViolationItem(
                    rule_code=RuleCode.MALICIOUS_INJECTION_LOCATOR,
                    severity=ViolationSeverity.CRITICAL,
                    message="定位器中包含疑似脚本注入、SQL注入或系统命令破坏性模式",
                    offending_snippet=clean_val,
                )
            )

    verdict = SafetyVerdict.BLOCK if len(violations) > 0 else SafetyVerdict.ALLOW

    return SafetyGuardAuditReport(
        report_id=report_id,
        verdict=verdict,
        violations=violations,
        inspected_target_type="LOCATOR",
    )


def audit_self_healing_patch_safety(patch_record: Dict[str, Any]) -> SafetyGuardAuditReport:
    """对完整自愈补丁对象进行综合安全审查"""
    report_id = f"sec_patch_{uuid.uuid4().hex[:10]}"
    violations: List[SafetyViolationItem] = []

    # 1. 检查推荐定位器
    best_cand = patch_record.get("best_candidate") or {}
    rec_type = best_cand.get("recommended_locator_type", "css")
    rec_val = best_cand.get("recommended_locator_value", "")
    if rec_val:
        loc_report = audit_locator_safety(rec_type, rec_val)
        violations.extend(loc_report.violations)

    verdict = (
        SafetyVerdict.BLOCK
        if any(v.severity in (ViolationSeverity.CRITICAL, ViolationSeverity.HIGH) for v in violations)
        else SafetyVerdict.ALLOW
    )

    return SafetyGuardAuditReport(
        report_id=report_id,
        verdict=verdict,
        violations=violations,
        inspected_target_type="PATCH",
    )
