"""品牌设计系统 (Design System Token) 与色彩对比度检查器 (T2.3)。"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ContrastLevel(str, Enum):
    """WCAG 色彩对比度合规等级。"""

    AAA = "AAA"  # >= 7.0:1 (极高对比度)
    AA = "AA"  # >= 4.5:1 (普通正文标准)
    AA_LARGE = "AA_LARGE"  # >= 3.0:1 (仅限大字号)
    FAIL = "FAIL"  # < 4.5:1 (低视力不合规)


class TokenViolationType(str, Enum):
    """规范违规分类。"""

    CONTRAST_RATIO_FAIL = "CONTRAST_RATIO_FAIL"  # 文本与背景色彩对比度不足
    FONT_SIZE_OFF_GRID = "FONT_SIZE_OFF_GRID"  # 字号未命中 Token
    SPACING_OFF_GRID = "SPACING_OFF_GRID"  # 间距未命中 Token (偏离网格)
    BORDER_RADIUS_OFF_GRID = "BORDER_RADIUS_OFF_GRID"  # 圆角未命中 Token


@dataclass
class TokenViolationItem:
    """单个设计规范违规明细。"""

    violation_id: str
    element_id: str
    violation_type: TokenViolationType
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    current_value: Any
    recommended_token: Any
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "element_id": self.element_id,
            "violation_type": self.violation_type.value,
            "severity": self.severity,
            "current_value": self.current_value,
            "recommended_token": self.recommended_token,
            "explanation": self.explanation,
        }


@dataclass
class DesignSystemAuditReport:
    """设计系统与色彩对比度审计全景报告。"""

    report_id: str
    target_name: str
    total_elements_checked: int
    total_violations_count: int
    contrast_fails_count: int
    token_discrepancies_count: int
    compliance_score_pct: float
    is_wcag_aa_compliant: bool
    violations: list[TokenViolationItem]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "target_name": self.target_name,
            "total_elements_checked": self.total_elements_checked,
            "total_violations_count": self.total_violations_count,
            "contrast_fails_count": self.contrast_fails_count,
            "token_discrepancies_count": self.token_discrepancies_count,
            "compliance_score_pct": round(self.compliance_score_pct, 1),
            "is_wcag_aa_compliant": self.is_wcag_aa_compliant,
            "violations": [v.to_dict() for v in self.violations],
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告存储
_DESIGN_AUDIT_REPORTS: dict[str, DesignSystemAuditReport] = {}

# 标准 Design System Token 白名单
STANDARD_FONT_SIZES = [10, 11, 12, 13, 14, 16, 18, 20, 24, 28, 32, 40]
STANDARD_SPACINGS = [0, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 32, 40, 48, 64]
STANDARD_BORDER_RADII = [0, 2, 4, 6, 8, 12, 16, 24, 9999]


def clear_design_audit_store() -> None:
    """清空设计系统审计仓库（单测专用）。"""
    _DESIGN_AUDIT_REPORTS.clear()


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """将 HEX 颜色 (#RGB 或 #RRGGBB) 转换为 (R, G, B)。"""
    c = hex_color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6 or not re.match(r"^[0-9a-fA-F]{6}$", c):
        return (0, 0, 0)
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def get_relative_luminance(r: int, g: int, b: int) -> float:
    """计算 sRGB 颜色分量的相对亮度 (W3C 规范算法)。"""

    def _srgb_to_lin(val: int) -> float:
        v = val / 255.0
        return v / 12.92 if v <= 0.03928 else math.pow((v + 0.055) / 1.055, 2.4)

    return 0.2126 * _srgb_to_lin(r) + 0.7152 * _srgb_to_lin(g) + 0.0722 * _srgb_to_lin(b)


def calculate_contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """计算两组 HEX 颜色之间的 WCAG 色彩对比度 (1.0 ~ 21.0)。"""
    r1, g1, b1 = hex_to_rgb(fg_hex)
    r2, g2, b2 = hex_to_rgb(bg_hex)

    l1 = get_relative_luminance(r1, g1, b1)
    l2 = get_relative_luminance(r2, g2, b2)

    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _find_closest_token(val: float, tokens: list[int]) -> int:
    """找到最接近的标准 Token 值。"""
    return min(tokens, key=lambda t: abs(t - val))


def audit_design_tokens_and_contrast(
    target_name: str,
    elements: list[dict[str, Any]],
) -> DesignSystemAuditReport:
    """全面审查各元素的 Token 规范符合度与 WCAG 色彩对比度。"""
    violations: list[TokenViolationItem] = []
    contrast_fails = 0
    token_discrepancies = 0

    for el in elements:
        eid = el.get("element_id", "el")
        fg = el.get("color")
        bg = el.get("background_color", "#FFFFFF")
        font_size = el.get("font_size")
        is_bold = el.get("is_bold", False)
        padding = el.get("padding")
        border_radius = el.get("border_radius")

        # 1. 色彩对比度审查
        if fg and bg:
            ratio = calculate_contrast_ratio(fg, bg)
            is_large_text = (font_size and font_size >= 18) or (font_size and font_size >= 14 and is_bold)
            min_required = 3.0 if is_large_text else 4.5

            if ratio < min_required:
                contrast_fails += 1
                sev = "CRITICAL" if ratio < 3.0 else "HIGH"
                violations.append(
                    TokenViolationItem(
                        violation_id=f"contrast_{uuid.uuid4().hex[:6]}",
                        element_id=eid,
                        violation_type=TokenViolationType.CONTRAST_RATIO_FAIL,
                        severity=sev,
                        current_value=f"前景色: {fg}, 背景色: {bg}, 对比度: {round(ratio, 2)}:1",
                        recommended_token=f"≥ {min_required}:1",
                        explanation=f"文本对比度 {round(ratio, 2)}:1 低于 WCAG AA 要求的 {min_required}:1，弱视及暗光下严重不可读。",
                    )
                )

        # 2. 字号 Token 审查
        if font_size is not None:
            int_fs = round(font_size)
            if int_fs not in STANDARD_FONT_SIZES or abs(font_size - int_fs) > 0.01:
                token_discrepancies += 1
                closest = _find_closest_token(font_size, STANDARD_FONT_SIZES)
                violations.append(
                    TokenViolationItem(
                        violation_id=f"token_fs_{uuid.uuid4().hex[:6]}",
                        element_id=eid,
                        violation_type=TokenViolationType.FONT_SIZE_OFF_GRID,
                        severity="MEDIUM",
                        current_value=f"{font_size}px",
                        recommended_token=f"{closest}px",
                        explanation=f"字号 ({font_size}px) 未遵循规范，建议对齐至标准字阶 Token ({closest}px)。",
                    )
                )

        # 3. 间距 Token 审查
        if padding is not None:
            int_pad = round(padding)
            if int_pad not in STANDARD_SPACINGS or abs(padding - int_pad) > 0.01:
                token_discrepancies += 1
                closest = _find_closest_token(padding, STANDARD_SPACINGS)
                violations.append(
                    TokenViolationItem(
                        violation_id=f"token_pad_{uuid.uuid4().hex[:6]}",
                        element_id=eid,
                        violation_type=TokenViolationType.SPACING_OFF_GRID,
                        severity="LOW",
                        current_value=f"{padding}px",
                        recommended_token=f"{closest}px",
                        explanation=f"内间距 ({padding}px) 未遵循 4px/2px 网格，建议对齐至 ({closest}px)。",
                    )
                )

        # 4. 圆角 Token 审查
        if border_radius is not None:
            int_r = round(border_radius)
            if int_r not in STANDARD_BORDER_RADII or abs(border_radius - int_r) > 0.01:
                token_discrepancies += 1
                closest = _find_closest_token(border_radius, STANDARD_BORDER_RADII)
                violations.append(
                    TokenViolationItem(
                        violation_id=f"token_rad_{uuid.uuid4().hex[:6]}",
                        element_id=eid,
                        violation_type=TokenViolationType.BORDER_RADIUS_OFF_GRID,
                        severity="LOW",
                        current_value=f"{border_radius}px",
                        recommended_token=f"{closest}px",
                        explanation=f"圆角 ({border_radius}px) 偏离规范体系，建议对齐至标准圆角 Token ({closest}px)。",
                    )
                )

    # 计算合规得分
    total_violations = len(violations)
    penalty = (contrast_fails * 20.0) + (token_discrepancies * 5.0)
    score = max(0.0, min(100.0, 100.0 - penalty))

    now = datetime.now(timezone.utc)
    report_id = f"token_audit_{target_name[:12]}_{int(now.timestamp())}"
    report = DesignSystemAuditReport(
        report_id=report_id,
        target_name=target_name,
        total_elements_checked=len(elements),
        total_violations_count=total_violations,
        contrast_fails_count=contrast_fails,
        token_discrepancies_count=token_discrepancies,
        compliance_score_pct=score,
        is_wcag_aa_compliant=contrast_fails == 0,
        violations=violations,
        created_at=now,
    )
    _DESIGN_AUDIT_REPORTS[report_id] = report
    return report


def get_design_system_report(report_id: str) -> DesignSystemAuditReport | None:
    """按 ID 查询设计系统审计报告。"""
    return _DESIGN_AUDIT_REPORTS.get(report_id)


def list_design_system_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史设计系统报告列表。"""
    reports = list(reversed(list(_DESIGN_AUDIT_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
