"""基于 WCAG 2.2 标准的无障碍可访问性 DOM 深度扫描器 (T3.1)。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class WcagRuleId(str, Enum):
    """WCAG 2.2 核心合规准则项枚举。"""

    NON_TEXT_CONTENT = "1.1.1"  # 非文本内容 (缺少 alt)
    INFO_AND_RELATIONSHIPS = "1.3.1"  # 信息与层级关系 (表单无关联 label)
    LINK_PURPOSE_IN_CONTEXT = "2.4.4"  # 链接/按钮无文本语义
    TARGET_SIZE_MINIMUM = "2.5.8"  # 目标尺寸最小标准 (WCAG 2.2 新增 >= 24x24px)
    NAME_ROLE_VALUE = "4.1.2"  # 命名、角色、状态与无效 ARIA
    DUPLICATE_ELEMENT_ID = "4.1.1"  # 存在重复 DOM ID 破坏屏幕阅读器索引


class A11yDefectSeverity(str, Enum):
    """无障碍缺陷严重度评级。"""

    CRITICAL = "CRITICAL"  # 严重阻断视障或纯键盘用户操作 (如表单无标签、不可达交互)
    HIGH = "HIGH"  # 核心语义缺失 (图片缺 alt、链接空文本)
    MEDIUM = "MEDIUM"  # 触控面积不足、无效 ARIA 属性
    LOW = "LOW"  # 次要建议与格式偏差


@dataclass
class A11yViolation:
    """单个 WCAG 2.2 无障碍违规项。"""

    violation_id: str
    rule_id: WcagRuleId
    rule_name: str
    severity: A11yDefectSeverity
    element_id: str
    tag_name: str
    selector: str
    issue_description: str
    remediation_suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "rule_id": self.rule_id.value,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "element_id": self.element_id,
            "tag_name": self.tag_name,
            "selector": self.selector,
            "issue_description": self.issue_description,
            "remediation_suggestion": self.remediation_suggestion,
        }


@dataclass
class WcagAccessibilityReport:
    """WCAG 2.2 可访问性审计全景报告。"""

    report_id: str
    page_url_or_name: str
    total_elements_scanned: int
    total_violations_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    compliance_score_pct: float
    is_wcag_aa_compliant: bool
    violations: list[A11yViolation]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "page_url_or_name": self.page_url_or_name,
            "total_elements_scanned": self.total_elements_scanned,
            "total_violations_count": self.total_violations_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "compliance_score_pct": round(self.compliance_score_pct, 1),
            "is_wcag_aa_compliant": self.is_wcag_aa_compliant,
            "violations": [v.to_dict() for v in self.violations],
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告存储
_WCAG_REPORTS: dict[str, WcagAccessibilityReport] = {}

# 标准 W3C ARIA 属性白名单
VALID_ARIA_ATTRIBUTES = {
    "aria-label",
    "aria-labelledby",
    "aria-describedby",
    "aria-hidden",
    "aria-expanded",
    "aria-disabled",
    "aria-checked",
    "aria-selected",
    "aria-live",
    "aria-atomic",
    "aria-relevant",
    "aria-busy",
    "aria-controls",
    "aria-current",
    "aria-details",
    "aria-haspopup",
    "aria-invalid",
    "aria-modal",
    "aria-multiselectable",
    "aria-orientation",
    "aria-owns",
    "aria-placeholder",
    "aria-posinset",
    "aria-pressed",
    "aria-readonly",
    "aria-required",
    "aria-roledescription",
    "aria-setsize",
    "aria-sort",
    "aria-valuemax",
    "aria-valuemin",
    "aria-valuenow",
    "aria-valuetext",
}


def clear_wcag_report_store() -> None:
    """清空 WCAG 审计报告仓库 (单测专用)。"""
    _WCAG_REPORTS.clear()


def scan_dom_accessibility(
    page_url_or_name: str,
    elements: list[dict[str, Any]],
) -> WcagAccessibilityReport:
    """对传入的 DOM 元素结构执行 WCAG 2.2 深度无障碍规范扫描。"""
    violations: list[A11yViolation] = []
    seen_ids: set[str] = set()

    for idx, el in enumerate(elements):
        eid = str(el.get("element_id") or f"node_{idx}")
        tag = (el.get("tag_name") or "div").lower().strip()
        attrs: dict[str, Any] = el.get("attributes") or {}
        text_content = (el.get("text_content") or "").strip()
        raw_w = el.get("width")
        raw_h = el.get("height")
        width = float(raw_w) if raw_w is not None else 0.0
        height = float(raw_h) if raw_h is not None else 0.0
        selector = el.get("selector") or f"{tag}#{eid}"

        # 1. 检查重复 DOM id (WCAG 4.1.1)
        dom_id = attrs.get("id") or el.get("id")
        if dom_id:
            if dom_id in seen_ids:
                violations.append(
                    A11yViolation(
                        violation_id=f"a11y_{uuid.uuid4().hex[:6]}",
                        rule_id=WcagRuleId.DUPLICATE_ELEMENT_ID,
                        rule_name="Duplicate Element ID (重复 ID)",
                        severity=A11yDefectSeverity.HIGH,
                        element_id=eid,
                        tag_name=tag,
                        selector=selector,
                        issue_description=f"DOM 树中存在重复的 id='{dom_id}'，导致辅助技术与屏幕阅读器寻址错乱。",
                        remediation_suggestion=f"确保页面所有 id 全局唯一，或将 id='{dom_id}' 替换为 class 类名。",
                    )
                )
            else:
                seen_ids.add(dom_id)

        # 2. 检查 <img> 或 role='img' 缺少 alt 描述文本 (WCAG 1.1.1 Non-text Content)
        if tag == "img" or attrs.get("role") == "img":
            alt = attrs.get("alt")
            aria_label = attrs.get("aria-label") or attrs.get("aria-labelledby")
            # 必须具有 alt 属性(即使纯装饰性也需显式声明 alt="" 或 aria-hidden="true")
            if alt is None and not aria_label and attrs.get("aria-hidden") != "true":
                violations.append(
                    A11yViolation(
                        violation_id=f"a11y_{uuid.uuid4().hex[:6]}",
                        rule_id=WcagRuleId.NON_TEXT_CONTENT,
                        rule_name="Non-text Content (缺少 alt 文本)",
                        severity=A11yDefectSeverity.HIGH,
                        element_id=eid,
                        tag_name=tag,
                        selector=selector,
                        issue_description="图像元素缺少 alt 属性或无障碍文本描述，盲人用户无法理解图片含义。",
                        remediation_suggestion="添加有意义的 alt 属性(如 alt='用户头像')；若为装饰图请标记 alt='' 或 aria-hidden='true'。",
                    )
                )

        # 3. 检查表单输入控件缺少关联 label (WCAG 1.3.1 Info and Relationships)
        if tag in ("input", "select", "textarea"):
            input_type = (attrs.get("type") or "text").lower()
            if input_type not in ("hidden", "submit", "reset", "button", "image"):
                has_label = bool(
                    attrs.get("aria-label")
                    or attrs.get("aria-labelledby")
                    or el.get("has_associated_label")
                    or el.get("label_text")
                )
                if not has_label:
                    violations.append(
                        A11yViolation(
                            violation_id=f"a11y_{uuid.uuid4().hex[:6]}",
                            rule_id=WcagRuleId.INFO_AND_RELATIONSHIPS,
                            rule_name="Form Field Missing Label (表单缺少关联标签)",
                            severity=A11yDefectSeverity.CRITICAL,
                            element_id=eid,
                            tag_name=tag,
                            selector=selector,
                            issue_description=f"<{tag} type='{input_type}'> 缺少关联的 <label> 或 aria-label，无法获知输入意图。",
                            remediation_suggestion="使用 <label for='id'> 绑定该输入框，或显式添加 aria-label='用户名' 属性。",
                        )
                    )

        # 4. 检查交互按钮或链接缺少可读文本 (WCAG 2.4.4 Link Purpose in Context)
        if tag in ("button", "a") or attrs.get("role") in ("button", "link"):
            has_accessible_name = bool(
                text_content or attrs.get("aria-label") or attrs.get("aria-labelledby") or attrs.get("title")
            )
            if not has_accessible_name:
                violations.append(
                    A11yViolation(
                        violation_id=f"a11y_{uuid.uuid4().hex[:6]}",
                        rule_id=WcagRuleId.LINK_PURPOSE_IN_CONTEXT,
                        rule_name="Empty Interactive Element (交互控件无语义文字)",
                        severity=A11yDefectSeverity.HIGH,
                        element_id=eid,
                        tag_name=tag,
                        selector=selector,
                        issue_description=f"<{tag}> 按钮或链接内为空，且未设置 aria-label 或 title，屏幕阅读器仅能朗读'未命名按钮'。",
                        remediation_suggestion="在纯图标按钮上添加 aria-label='关闭' 或 title='刷新'，明确交互语义。",
                    )
                )

        # 5. 检查非法或拼写错误的 ARIA 属性 (WCAG 4.1.2 Name, Role, Value)
        for attr_key in attrs.keys():
            if attr_key.startswith("aria-") and attr_key not in VALID_ARIA_ATTRIBUTES:
                violations.append(
                    A11yViolation(
                        violation_id=f"a11y_{uuid.uuid4().hex[:6]}",
                        rule_id=WcagRuleId.NAME_ROLE_VALUE,
                        rule_name="Invalid ARIA Attribute (非标准 ARIA 属性)",
                        severity=A11yDefectSeverity.MEDIUM,
                        element_id=eid,
                        tag_name=tag,
                        selector=selector,
                        issue_description=f"发现无效或非标准属性 '{attr_key}'，辅助技术无法识别其状态。",
                        remediation_suggestion=f"检查并修正 ARIA 属性拼写，例如更正为有效的 aria-label、aria-hidden 等。",
                    )
                )

        # 6. 检查触控/点击交互目标尺寸过小 (WCAG 2.2 准则 2.5.8 Target Size Minimum >= 24x24px)
        is_interactive = tag in ("button", "a", "input", "select") or attrs.get("role") in ("button", "link")
        if is_interactive and width > 0 and height > 0:
            if width < 24.0 or height < 24.0:
                violations.append(
                    A11yViolation(
                        violation_id=f"a11y_{uuid.uuid4().hex[:6]}",
                        rule_id=WcagRuleId.TARGET_SIZE_MINIMUM,
                        rule_name="Target Size Minimum (点击目标尺寸过小)",
                        severity=A11yDefectSeverity.MEDIUM,
                        element_id=eid,
                        tag_name=tag,
                        selector=selector,
                        issue_description=f"交互控件实际渲染尺寸为 {width:.1f}x{height:.1f}px，低于 WCAG 2.2 规定的 24x24px 最低触控面积。",
                        remediation_suggestion="增加 min-width: 24px; min-height: 24px 或通过外围透明 padding 扩充热区。",
                    )
                )

    # 统计严重度分布
    crit = sum(1 for v in violations if v.severity == A11yDefectSeverity.CRITICAL)
    high = sum(1 for v in violations if v.severity == A11yDefectSeverity.HIGH)
    med = sum(1 for v in violations if v.severity == A11yDefectSeverity.MEDIUM)
    low = sum(1 for v in violations if v.severity == A11yDefectSeverity.LOW)

    # 评分计算 (100 分制，扣减扣分)
    penalty = (crit * 25.0) + (high * 15.0) + (med * 6.0) + (low * 2.0)
    score = max(0.0, min(100.0, 100.0 - penalty))

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", page_url_or_name)[:16]
    report_id = f"wcag_scan_{safe_name}_{int(now.timestamp())}"

    report = WcagAccessibilityReport(
        report_id=report_id,
        page_url_or_name=page_url_or_name,
        total_elements_scanned=len(elements),
        total_violations_count=len(violations),
        critical_count=crit,
        high_count=high,
        medium_count=med,
        low_count=low,
        compliance_score_pct=score,
        is_wcag_aa_compliant=(crit == 0 and high == 0),
        violations=violations,
        created_at=now,
    )

    _WCAG_REPORTS[report_id] = report
    return report


def get_wcag_report(report_id: str) -> WcagAccessibilityReport | None:
    """按 ID 获取单次 WCAG 审计报告。"""
    return _WCAG_REPORTS.get(report_id)


def list_wcag_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史 WCAG 报告列表。"""
    reports = list(reversed(list(_WCAG_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
