"""色盲/色弱多模态视觉感知模拟与低视力辅助缺陷分类器 (T3.3)。"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ColorBlindnessType(str, Enum):
    """色盲与色弱缺陷类型。"""

    PROTANOPIA = "PROTANOPIA"  # 红色盲 (缺乏长波锥体细胞)
    DEUTERANOPIA = "DEUTERANOPIA"  # 绿色盲 (缺乏中波锥体细胞, 最常见)
    TRITANOPIA = "TRITANOPIA"  # 蓝色盲 (缺乏短波锥体细胞)
    ACHROMATOPSIA = "ACHROMATOPSIA"  # 全色盲 (完全无彩色, 仅灰度)


class CvdViolationType(str, Enum):
    """CVD 无障碍缺陷分类。"""

    SOLE_COLOR_INDICATOR = "SOLE_COLOR_INDICATOR"  # 违背 WCAG 1.4.1: 仅依赖颜色传达关键状态
    SIMULATED_CONTRAST_FAIL = "SIMULATED_CONTRAST_FAIL"  # 色盲视角下前背景色彩混淆/对比度归零
    STATUS_CONFUSION = "STATUS_CONFUSION"  # 成功与失败状态在色盲视角下无法区分


class CvdSeverity(str, Enum):
    """缺陷严重度。"""

    CRITICAL = "CRITICAL"  # 成功/失败等生死状态完全混淆且无文本图标辅助
    HIGH = "HIGH"  # 单色指示缺少语义
    MEDIUM = "MEDIUM"  # 对比度在色弱下显著衰减
    LOW = "LOW"  # 次要装饰色彩微差


@dataclass
class CvdViolationItem:
    """单个色盲缺陷明细。"""

    violation_id: str
    element_id: str
    violation_type: CvdViolationType
    severity: CvdSeverity
    blindness_type: ColorBlindnessType
    issue_description: str
    remediation_suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "element_id": self.element_id,
            "violation_type": self.violation_type.value,
            "severity": self.severity.value,
            "blindness_type": self.blindness_type.value,
            "issue_description": self.issue_description,
            "remediation_suggestion": self.remediation_suggestion,
        }


@dataclass
class ColorSimulationResult:
    """单个颜色在各类色盲视角下的仿真色值。"""

    original_hex: str
    protanopia_hex: str
    deuteranopia_hex: str
    tritanopia_hex: str
    achromatopsia_hex: str

    def to_dict(self) -> dict[str, str]:
        return {
            "original_hex": self.original_hex,
            "protanopia_hex": self.protanopia_hex,
            "deuteranopia_hex": self.deuteranopia_hex,
            "tritanopia_hex": self.tritanopia_hex,
            "achromatopsia_hex": self.achromatopsia_hex,
        }


@dataclass
class ColorBlindnessAuditReport:
    """色盲与低视力多模态审计全景报告。"""

    report_id: str
    component_or_page: str
    total_indicators_checked: int
    total_violations_count: int
    critical_count: int
    is_wcag_1_4_1_compliant: bool
    cvd_accessibility_score_pct: float
    violations: list[CvdViolationItem]
    simulations: list[ColorSimulationResult]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "component_or_page": self.component_or_page,
            "total_indicators_checked": self.total_indicators_checked,
            "total_violations_count": self.total_violations_count,
            "critical_count": self.critical_count,
            "is_wcag_1_4_1_compliant": self.is_wcag_1_4_1_compliant,
            "cvd_accessibility_score_pct": round(self.cvd_accessibility_score_pct, 1),
            "violations": [v.to_dict() for v in self.violations],
            "simulations": [s.to_dict() for s in self.simulations],
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告仓库
_CVD_AUDIT_REPORTS: dict[str, ColorBlindnessAuditReport] = {}


def clear_cvd_report_store() -> None:
    """清空 CVD 报告仓库 (单测专用)。"""
    _CVD_AUDIT_REPORTS.clear()


def parse_hex_color(hex_str: str) -> tuple[int, int, int]:
    """将 HEX 颜色转为标准 (r, g, b)。"""
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(ch * 2 for ch in clean)
    if len(clean) != 6 or not re.match(r"^[0-9a-fA-F]{6}$", clean):
        return (128, 128, 128)
    return (int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))


def rgb_to_hex(r: float, g: float, b: float) -> str:
    """将 RGB 转为 #RRGGBB。"""
    cr = max(0, min(255, int(round(r))))
    cg = max(0, min(255, int(round(g))))
    cb = max(0, min(255, int(round(b))))
    return f"#{cr:02X}{cg:02X}{cb:02X}"


def simulate_color_vision_deficiency(hex_color: str) -> ColorSimulationResult:
    """使用 Brettel/Vienot 经典感知映射矩阵，将 RGB 投影到 4 种色盲色彩空间。"""
    r, g, b = parse_hex_color(hex_color)

    # 1. 红色盲 Protanopia 矩阵变换
    p_r = 0.56667 * r + 0.43333 * g + 0.0 * b
    p_g = 0.55833 * r + 0.44167 * g + 0.0 * b
    p_b = 0.0 * r + 0.24167 * g + 0.75833 * b

    # 2. 绿色盲 Deuteranopia 矩阵变换 (红绿互混)
    d_r = 0.625 * r + 0.375 * g + 0.0 * b
    d_g = 0.700 * r + 0.300 * g + 0.0 * b
    d_b = 0.0 * r + 0.300 * g + 0.700 * b

    # 3. 蓝色盲 Tritanopia 矩阵变换 (蓝黄混淆)
    t_r = 0.950 * r + 0.050 * g + 0.0 * b
    t_g = 0.0 * r + 0.43333 * g + 0.56667 * b
    t_b = 0.0 * r + 0.47500 * g + 0.52500 * b

    # 4. 全色盲 Achromatopsia (纯亮度灰度 ITU-R BT.709)
    gray = 0.2126 * r + 0.7152 * g + 0.0722 * b

    return ColorSimulationResult(
        original_hex=hex_color.upper(),
        protanopia_hex=rgb_to_hex(p_r, p_g, p_b),
        deuteranopia_hex=rgb_to_hex(d_r, d_g, d_b),
        tritanopia_hex=rgb_to_hex(t_r, t_g, t_b),
        achromatopsia_hex=rgb_to_hex(gray, gray, gray),
    )


def color_distance(hex1: str, hex2: str) -> float:
    """计算两组 HEX 颜色在 sRGB 空间的几何欧氏距离。"""
    r1, g1, b1 = parse_hex_color(hex1)
    r2, g2, b2 = parse_hex_color(hex2)
    return math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2)


def audit_color_blindness_accessibility(
    component_or_page: str,
    status_indicators: list[dict[str, Any]],
) -> ColorBlindnessAuditReport:
    """执行 WCAG 1.4.1 (Use of Color) 与色盲多模态辨识度审计。"""
    violations: list[CvdViolationItem] = []
    simulations: list[ColorSimulationResult] = []

    for ind in status_indicators:
        eid = ind.get("element_id", "status_ind")
        color = ind.get("color_hex", "#1677FF")
        has_accompanying_text = bool(ind.get("has_text", False))
        has_accompanying_icon = bool(ind.get("has_icon", False))
        status_meaning = ind.get("status_meaning", "normal")  # success, failure, running, warning

        sim = simulate_color_vision_deficiency(color)
        simulations.append(sim)

        # 检查是否违背 WCAG 1.4.1: 仅依赖颜色传达关键状态 (无任何文字或区分图标)
        if not has_accompanying_text and not has_accompanying_icon:
            # 属于高危违规 (例如仅有一个红点或绿点)
            violations.append(
                CvdViolationItem(
                    violation_id=f"cvd_{uuid.uuid4().hex[:6]}",
                    element_id=eid,
                    violation_type=CvdViolationType.SOLE_COLOR_INDICATOR,
                    severity=CvdSeverity.CRITICAL,
                    blindness_type=ColorBlindnessType.DEUTERANOPIA,
                    issue_description=(
                        f"状态指示器 [{eid}] (含义: '{status_meaning}') 仅使用颜色 ({color}) 传达状态，"
                        f"缺少伴随文本或辅助图标，违背 WCAG 1.4.1 核心准则。"
                    ),
                    remediation_suggestion="在颜色指示旁添加文字标签(如'成功'、'失败')或形状不同的图标(如对勾 ✔、叉号 ✖)。",
                )
            )

    # 检查状态配对混淆 (例如成功绿与失败红在绿色盲空间下的辨识距离)
    # 如果同时存在 success 和 failure 指示器且未给全文字，检查红绿色盲空间下的相似度
    success_inds = [i for i in status_indicators if i.get("status_meaning") == "success"]
    failure_inds = [i for i in status_indicators if i.get("status_meaning") in ("failure", "danger", "error")]

    for s_ind in success_inds:
        for f_ind in failure_inds:
            s_sim = simulate_color_vision_deficiency(s_ind.get("color_hex", "#22C55E"))
            f_sim = simulate_color_vision_deficiency(f_ind.get("color_hex", "#EF4444"))

            # 绿色盲视角下的色差
            dist_deuter = color_distance(s_sim.deuteranopia_hex, f_sim.deuteranopia_hex)
            if dist_deuter < 40.0:  # 在红绿色盲视角下显著混淆
                if not (s_ind.get("has_text") and f_ind.get("has_text")):
                    violations.append(
                        CvdViolationItem(
                            violation_id=f"cvd_{uuid.uuid4().hex[:6]}",
                            element_id=f"{s_ind.get('element_id')} vs {f_ind.get('element_id')}",
                            violation_type=CvdViolationType.STATUS_CONFUSION,
                            severity=CvdSeverity.CRITICAL,
                            blindness_type=ColorBlindnessType.DEUTERANOPIA,
                            issue_description=(
                                f"成功状态 ({s_ind.get('color_hex')}) 与失败状态 ({f_ind.get('color_hex')}) "
                                f"在绿色盲视角下色差过小 (仅 {dist_deuter:.1f})，极易完全混淆。"
                            ),
                            remediation_suggestion="使用多重编码: 绿色成功配合勾选图标，红色失败配合感叹号或叉号，切勿仅凭红绿。",
                        )
                    )

    crit_count = sum(1 for v in violations if v.severity == CvdSeverity.CRITICAL)
    penalty = (crit_count * 25.0) + (len(violations) - crit_count) * 10.0
    score = max(0.0, min(100.0, 100.0 - penalty))

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", component_or_page)[:16]
    report_id = f"cvd_audit_{safe_name}_{int(now.timestamp())}"

    report = ColorBlindnessAuditReport(
        report_id=report_id,
        component_or_page=component_or_page,
        total_indicators_checked=len(status_indicators),
        total_violations_count=len(violations),
        critical_count=crit_count,
        is_wcag_1_4_1_compliant=(crit_count == 0),
        cvd_accessibility_score_pct=score,
        violations=violations,
        simulations=simulations,
        created_at=now,
    )

    _CVD_AUDIT_REPORTS[report_id] = report
    return report


def get_color_blindness_report(report_id: str) -> ColorBlindnessAuditReport | None:
    """按 ID 查询单次色盲审计报告。"""
    return _CVD_AUDIT_REPORTS.get(report_id)


def list_color_blindness_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史色盲审计报告列表。"""
    reports = list(reversed(list(_CVD_AUDIT_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
