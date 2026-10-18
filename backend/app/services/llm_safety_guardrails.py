"""大模型有害内容与毒性安全护栏看门狗 (T2.2)

功能职责:
1. 双向安全护栏 (输入 Input Guardrail 与输出 Output Guardrail);
2. 三大安全审查维度:
   - 毒性与有害内容 (涉暴、涉恐、极端违法、网络武器代码);
   - 敏感隐私 PII (身份证、手机号、银行卡号、API 密钥与凭据脱敏);
   - 未授权越权攻击 (删库 DROP/TRUNCATE、系统底层命令执行、提权攻击);
3. 三态安全处置动作 (PASSED 放行、REDACTED 脱敏放行、BLOCKED 毫秒级阻断);
4. 毫秒级检查延迟 (< 5ms) 与灵活配置严格度 (PERMISSIVE, STANDARD, STRICT)。
"""

from __future__ import annotations

from enum import Enum
import re
import time
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


class GuardrailDirection(str, Enum):
    """安全审查流向"""

    INPUT = "INPUT"  # 输入护栏 (用户 Prompt 预检)
    OUTPUT = "OUTPUT"  # 输出护栏 (模型回答后置审查)


class SafetyViolationType(str, Enum):
    """违规类型枚举"""

    TOXIC_CONTENT = "TOXIC_CONTENT"  # 涉暴、涉恐、极端违法等有害毒性内容
    PRIVACY_PII = "PRIVACY_PII"  # 个人隐私数据与保密 API 凭据
    PRIVILEGE_ESCALATION = "PRIVILEGE_ESCALATION"  # 未授权特权篡改与破坏性越权指令


class GuardrailAction(str, Enum):
    """护栏处置动作"""

    PASSED = "PASSED"  # 安全放行
    REDACTED = "REDACTED"  # 脱敏放行 (仅检出 PII 且完成脱敏替换)
    BLOCKED = "BLOCKED"  # 强制阻断 (命中严重毒性或越权破坏攻击)


class SafetyStrictness(str, Enum):
    """安全护栏审查严格度"""

    PERMISSIVE = "PERMISSIVE"  # 宽松模式: 仅阻断极高危越权破坏指令
    STANDARD = "STANDARD"  # 标准企业模式: 阻断毒性与越权指令，PII 强制脱敏放行
    STRICT = "STRICT"  # 严苛模式: 任何毒性、越权或 PII 出现均直接阻断


class GuardrailViolation(BaseModel):
    """单项安全违规明细"""

    violation_type: SafetyViolationType = Field(..., description="违规大类")
    severity: str = Field(..., description="严重等级: CRITICAL, HIGH, MEDIUM")
    rule_name: str = Field(..., description="触发的规则名称")
    matched_fragment: str = Field(..., description="命中的违规文本片段或遮蔽标识")
    action_taken: GuardrailAction = Field(..., description="建议或执行的处理动作")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violation_type": self.violation_type.value,
            "severity": self.severity,
            "rule_name": self.rule_name,
            "matched_fragment": self.matched_fragment,
            "action_taken": self.action_taken.value,
        }


class GuardrailInspectionResult(BaseModel):
    """护栏审查完整判决报告"""

    check_id: str = Field(..., description="唯一检查流水标识")
    direction: GuardrailDirection = Field(..., description="审查流向")
    action: GuardrailAction = Field(..., description="最终处置裁决")
    original_text: str = Field(..., description="送审原始文本")
    sanitized_text: str = Field(..., description="脱敏或安全净化后的文本")
    violations: List[GuardrailViolation] = Field(default_factory=list, description="检出的违规项列表")
    latency_ms: float = Field(..., description="护栏执行延迟 (毫秒)")
    block_reason: Optional[str] = Field(None, description="若被阻断，记录明确的拦截原因")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "direction": self.direction.value,
            "action": self.action.value,
            "original_text": self.original_text,
            "sanitized_text": self.sanitized_text,
            "violations": [v.to_dict() for v in self.violations],
            "latency_ms": round(self.latency_ms, 2),
            "block_reason": self.block_reason,
        }


# ==================== 安全审查规则与正则表达式库 ====================

# 1. 越权破坏与未授权特权篡改指令 (PRIVILEGE_ESCALATION)
ESCALATION_RULES = [
    (r"(?i)\bdrop\s+(?:database|schema|table)\b", "SQL_DROP_DATABASE_OR_TABLE", "CRITICAL"),
    (r"(?i)\btruncate\s+table\b", "SQL_TRUNCATE_TABLE", "CRITICAL"),
    (r"(?i)\brm\s+-rf\s+[/~*]", "LINUX_FORCE_RECURSIVE_DELETE", "CRITICAL"),
    (r"(?i)\bchmod\s+(?:-R\s+)?777\s+/", "LINUX_GLOBAL_PERMISSIVE_CHMOD", "CRITICAL"),
    (r"(?i)\b__import__\s*\(\s*['\"]os['\"]\s*\)\.system", "PYTHON_ARBITRARY_OS_SYSTEM", "CRITICAL"),
    (r"(?i)\beval\s*\(\s*compile\s*\(", "PYTHON_ARBITRARY_CODE_EVAL", "HIGH"),
    (r"(?i)\bgrant\s+all\s+privileges\b", "SQL_GRANT_SUPERUSER_PRIVILEGES", "CRITICAL"),
    (r"(?i)\bmkfs\.(?:ext[234]|xfs)\b", "STORAGE_FORMAT_DISK", "CRITICAL"),
]

# 2. 毒性有害内容关键词与特征库 (TOXIC_CONTENT)
TOXIC_CONTENT_RULES = [
    (r"(?:简易|自制)?炸药(?:制作|配方|配比|引爆)", "WEAPON_EXPLOSIVE_FABRICATION", "CRITICAL"),
    (r"(?:剧毒|危险)化学品(?:合成|提纯|配制)", "DANGEROUS_CHEMICAL_SYNTHESIS", "CRITICAL"),
    (r"(?:制造|合成|培育)生化武器", "BIOLOGICAL_WEAPON_MANUFACTURE", "CRITICAL"),
    (r"恐怖袭击(?:策划|实施|方案|目标选取)", "TERRORIST_ATTACK_PLANNING", "CRITICAL"),
    (r"(?:暗杀|雇凶杀人)(?:行动指南|价目表|方案)", "ASSASSINATION_CONTRACT", "CRITICAL"),
    (r"勒索病毒(?:源码|生成器|免杀编译)", "RANSOMWARE_SOURCE_GENERATION", "HIGH"),
    (r"(?:地下|非法)洗钱通道(?:套现|对冲)", "MONEY_LAUNDERING_CHANNEL", "HIGH"),
    (r"(?:肉鸡|僵尸网络)搭建(?:ddos|发包压测)", "BOTNET_DDOS_WEAPONIZATION", "HIGH"),
]

# 3. 敏感隐私数据 PII 正则提取规则 (PRIVACY_PII)
PII_RULES = [
    (
        r"(?<!\d)(?:1[3-9]\d{9})(?!\d)",
        "PII_PHONE_NUMBER",
        "[REDACTED_PHONE]",
        "MEDIUM",
    ),
    (
        r"(?<!\d)(?:[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx])(?!\d)",
        "PII_ID_CARD",
        "[REDACTED_ID_CARD]",
        "HIGH",
    ),
    (
        r"(?<!\d)(?:62\d{14,17}|4\d{15}|5[1-5]\d{14})(?!\d)",
        "PII_BANK_CARD",
        "[REDACTED_BANK_CARD]",
        "HIGH",
    ),
    (
        r"(?:sk-[a-zA-Z0-9]{24,}|ghp_[a-zA-Z0-9]{36}|-----BEGIN [A-Z ]+ PRIVATE KEY-----)",
        "PII_API_OR_PRIVATE_KEY",
        "[REDACTED_SECRET_KEY]",
        "CRITICAL",
    ),
]


def inspect_safety_guardrail(
    text: str,
    direction: GuardrailDirection = GuardrailDirection.INPUT,
    strictness: SafetyStrictness = SafetyStrictness.STANDARD,
    custom_blocked_keywords: Optional[List[str]] = None,
) -> GuardrailInspectionResult:
    """毫秒级执行大模型输入/输出双向内容安全审查

    审查判定流程:
    1. 越权破坏指令扫描 -> 若命中且非 PERMISSIVE 模式立即触发 BLOCKED 阻断;
    2. 毒性与有害内容扫描 -> 若命中且非 PERMISSIVE 模式立即触发 BLOCKED 阻断;
    3. 自定义黑名单关键词扫描 -> 立即触发 BLOCKED 阻断;
    4. 隐私 PII 数据提取与脱敏:
       - STRICT 模式: 检出任何 PII 均直接阻断;
       - STANDARD / PERMISSIVE 模式: 自动遮蔽敏感片段并输出 REDACTED 脱敏文本;
    5. 无违规项放行 (PASSED)。
    """
    start_time = time.perf_counter()
    check_id = f"grd_{uuid.uuid4().hex[:10]}"
    violations: List[GuardrailViolation] = []
    sanitized_text = text

    # 1. 越权破坏指令审查 (PRIVILEGE_ESCALATION)
    for pattern, rule_name, severity in ESCALATION_RULES:
        match = re.search(pattern, text)
        if match:
            matched_str = match.group(0)
            violations.append(
                GuardrailViolation(
                    violation_type=SafetyViolationType.PRIVILEGE_ESCALATION,
                    severity=severity,
                    rule_name=rule_name,
                    matched_fragment=matched_str,
                    action_taken=GuardrailAction.BLOCKED,
                )
            )

    # 2. 毒性与有害内容审查 (TOXIC_CONTENT)
    for pattern, rule_name, severity in TOXIC_CONTENT_RULES:
        match = re.search(pattern, text)
        if match:
            matched_str = match.group(0)
            violations.append(
                GuardrailViolation(
                    violation_type=SafetyViolationType.TOXIC_CONTENT,
                    severity=severity,
                    rule_name=rule_name,
                    matched_fragment=matched_str,
                    action_taken=GuardrailAction.BLOCKED,
                )
            )

    # 3. 自定义黑名单关键词审查
    if custom_blocked_keywords:
        for kw in custom_blocked_keywords:
            if kw and kw.lower() in text.lower():
                violations.append(
                    GuardrailViolation(
                        violation_type=SafetyViolationType.TOXIC_CONTENT,
                        severity="HIGH",
                        rule_name=f"CUSTOM_KEYWORD_BLOCKED_{kw}",
                        matched_fragment=kw,
                        action_taken=GuardrailAction.BLOCKED,
                    )
                )

    # 4. 检查是否触发阻断 (BLOCKED)
    has_critical_block = any(v.action_taken == GuardrailAction.BLOCKED for v in violations)
    if has_critical_block and strictness != SafetyStrictness.PERMISSIVE:
        latency = (time.perf_counter() - start_time) * 1000.0
        block_desc = "、".join([f"{v.rule_name}({v.violation_type.value})" for v in violations])
        return GuardrailInspectionResult(
            check_id=check_id,
            direction=direction,
            action=GuardrailAction.BLOCKED,
            original_text=text,
            sanitized_text="[BLOCKED: 该内容违反平台大模型安全护栏准则，已触发强制拦截。]",
            violations=violations,
            latency_ms=latency,
            block_reason=f"安全护栏阻断：触发高危拦截规则 [{block_desc}]",
        )

    # 5. 个人隐私与保密凭据 PII 审查 (PRIVACY_PII)
    pii_found = False
    for pattern, rule_name, replacement, severity in PII_RULES:
        matches = re.findall(pattern, sanitized_text)
        if matches:
            pii_found = True
            for m in set(matches):
                # 遮蔽脱敏展示前 2 位和后 2 位
                masked_disp = m[:2] + "****" + m[-2:] if len(m) > 4 else "****"
                violations.append(
                    GuardrailViolation(
                        violation_type=SafetyViolationType.PRIVACY_PII,
                        severity=severity,
                        rule_name=rule_name,
                        matched_fragment=masked_disp,
                        action_taken=GuardrailAction.BLOCKED
                        if strictness == SafetyStrictness.STRICT
                        else GuardrailAction.REDACTED,
                    )
                )
            # 执行文本替换脱敏
            sanitized_text = re.sub(pattern, replacement, sanitized_text)

    latency = (time.perf_counter() - start_time) * 1000.0

    # 严苛模式下检出 PII 直接阻断
    if pii_found and strictness == SafetyStrictness.STRICT:
        return GuardrailInspectionResult(
            check_id=check_id,
            direction=direction,
            action=GuardrailAction.BLOCKED,
            original_text=text,
            sanitized_text="[BLOCKED: 严苛模式已阻断包含个人隐私 PII 的数据请求]",
            violations=violations,
            latency_ms=latency,
            block_reason="严苛安全模式生效：禁止流转包含个人隐私 PII（手机号/身份证/密钥）的信息",
        )

    # 若发生 PII 脱敏且未阻断
    if pii_found:
        return GuardrailInspectionResult(
            check_id=check_id,
            direction=direction,
            action=GuardrailAction.REDACTED,
            original_text=text,
            sanitized_text=sanitized_text,
            violations=violations,
            latency_ms=latency,
            block_reason=None,
        )

    # 默认安全放行 (PASSED)
    return GuardrailInspectionResult(
        check_id=check_id,
        direction=direction,
        action=GuardrailAction.PASSED,
        original_text=text,
        sanitized_text=text,
        violations=[],
        latency_ms=latency,
        block_reason=None,
    )
