"""屏幕阅读器焦点流转与键盘全盲导航路径可达性验证器 (T3.2)。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class KeyboardDefectType(str, Enum):
    """键盘导航可达性缺陷类型。"""

    FOCUS_TRAP_DETECTED = "FOCUS_TRAP_DETECTED"  # 键盘死锁陷阱 (无法跳出容器)
    FOCUS_RING_INVISIBLE = "FOCUS_RING_INVISIBLE"  # 缺乏可见焦点外框 (outline: none)
    SKIP_TO_CONTENT_MISSING = "SKIP_TO_CONTENT_MISSING"  # 缺失跳过导航链接 (Skip Link)
    POSITIVE_TABINDEX_ABUSE = "POSITIVE_TABINDEX_ABUSE"  # 滥用正 tabindex 扰乱聚焦流
    UNREACHABLE_INTERACTIVE = "UNREACHABLE_INTERACTIVE"  # 关键交互控件带负 tabindex 无法键盘聚焦


class KeyboardDefectSeverity(str, Enum):
    """键盘可达性缺陷严重度。"""

    CRITICAL = "CRITICAL"  # 键盘死锁陷阱 (用户被困死无法退出)
    HIGH = "HIGH"  # 无可见聚焦环、关键按钮无法键盘聚焦
    MEDIUM = "MEDIUM"  # 滥用正 tabindex、缺少跳至正文链接
    LOW = "LOW"  # 次级顺序微调建议


@dataclass
class FocusTraversalStep:
    """焦点流转链路中的单步快照。"""

    step_order: int
    element_id: str
    tag_name: str
    tabindex: int
    has_visible_focus: bool
    container_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_order": self.step_order,
            "element_id": self.element_id,
            "tag_name": self.tag_name,
            "tabindex": self.tabindex,
            "has_visible_focus": self.has_visible_focus,
            "container_id": self.container_id,
        }


@dataclass
class KeyboardDefectItem:
    """单个键盘导航缺陷明细。"""

    defect_id: str
    defect_type: KeyboardDefectType
    severity: KeyboardDefectSeverity
    element_id: str
    description: str
    remediation_suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "defect_id": self.defect_id,
            "defect_type": self.defect_type.value,
            "severity": self.severity.value,
            "element_id": self.element_id,
            "description": self.description,
            "remediation_suggestion": self.remediation_suggestion,
        }


@dataclass
class KeyboardNavAuditReport:
    """键盘导航路径与可达性全景报告。"""

    report_id: str
    page_name: str
    total_focusable_elements: int
    total_defects_count: int
    has_focus_trap: bool
    keyboard_accessibility_score_pct: float
    is_fully_keyboard_accessible: bool
    traversal_path: list[FocusTraversalStep]
    defects: list[KeyboardDefectItem]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "page_name": self.page_name,
            "total_focusable_elements": self.total_focusable_elements,
            "total_defects_count": self.total_defects_count,
            "has_focus_trap": self.has_focus_trap,
            "keyboard_accessibility_score_pct": round(self.keyboard_accessibility_score_pct, 1),
            "is_fully_keyboard_accessible": self.is_fully_keyboard_accessible,
            "traversal_path": [s.to_dict() for s in self.traversal_path],
            "defects": [d.to_dict() for d in self.defects],
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告存储
_KEYBOARD_NAV_REPORTS: dict[str, KeyboardNavAuditReport] = {}


def clear_keyboard_nav_store() -> None:
    """清空键盘导航审计仓库 (单测专用)。"""
    _KEYBOARD_NAV_REPORTS.clear()


def simulate_keyboard_navigation(
    page_name: str,
    elements: list[dict[str, Any]],
) -> KeyboardNavAuditReport:
    """仿真 Tab 键序列化焦点流转，探测键盘陷阱、指示器缺失与正 tabindex 滥用。"""
    defects: list[KeyboardDefectItem] = []

    # 1. 过滤并分类可聚焦元素
    # 原生可聚焦标签: button, a[href], input, select, textarea 或显示声明 tabindex >= 0
    focusable_candidates: list[dict[str, Any]] = []
    has_skip_link = False

    for idx, el in enumerate(elements):
        eid = str(el.get("element_id") or f"el_{idx}")
        tag = (el.get("tag_name") or "div").lower().strip()
        ti = el.get("tabindex")
        ti_int = int(ti) if ti is not None else (0 if tag in ("button", "a", "input", "select", "textarea") else -1)

        # 检查是否为跳过导航链接 (Skip Link)
        text_lower = (el.get("text_content") or "").lower()
        if "skip" in text_lower or "跳过" in text_lower or "正文" in text_lower:
            has_skip_link = True

        # 检查关键交互控件被设置了负 tabindex (无法 Tab 访问)
        if tag in ("button", "a") and ti is not None and ti_int < 0:
            defects.append(
                KeyboardDefectItem(
                    defect_id=f"kb_{uuid.uuid4().hex[:6]}",
                    defect_type=KeyboardDefectType.UNREACHABLE_INTERACTIVE,
                    severity=KeyboardDefectSeverity.HIGH,
                    element_id=eid,
                    description=f"<{tag}> 按钮被赋予 tabindex='{ti_int}'，导致纯键盘用户无法移动焦点至该关键交互项。",
                    remediation_suggestion="移除负数 tabindex，或仅在由自定义脚本控制焦点的复合部件(如 roving tabindex)中使用。",
                )
            )

        # 检查正 tabindex 滥用 (破坏自然 DOM 流)
        if ti_int > 0:
            defects.append(
                KeyboardDefectItem(
                    defect_id=f"kb_{uuid.uuid4().hex[:6]}",
                    defect_type=KeyboardDefectType.POSITIVE_TABINDEX_ABUSE,
                    severity=KeyboardDefectSeverity.MEDIUM,
                    element_id=eid,
                    description=f"元素设置了正数 tabindex='{ti_int}'，打乱了全页自然的 DOM 读取与 Tab 流转顺序。",
                    remediation_suggestion="避免设置大于 0 的 tabindex；通过调整 DOM 结构次序控制逻辑焦点流。",
                )
            )

        if ti_int >= 0:
            focusable_candidates.append({**el, "element_id": eid, "tag_name": tag, "tabindex_int": ti_int})

    # 2. 检查页面是否缺失 Skip Link (当可聚焦元素超过 5 个且无跳过链接时报警)
    if len(focusable_candidates) >= 5 and not has_skip_link:
        defects.append(
            KeyboardDefectItem(
                defect_id=f"kb_{uuid.uuid4().hex[:6]}",
                defect_type=KeyboardDefectType.SKIP_TO_CONTENT_MISSING,
                severity=KeyboardDefectSeverity.MEDIUM,
                element_id="document_root",
                description="页面可交互项较多但缺少'跳至正文' (Skip to content) 链接，键盘用户需多次按 Tab 才能越过头部导航。",
                remediation_suggestion="在 <body> 开头添加隐藏但聚焦可见的 <a href='#main' class='skip-link'>跳至主要内容</a>。",
            )
        )

    # 3. 按照标准浏览器 Tab 顺序排序
    # 规则: 正 tabindex (从小到大) -> tabindex=0 的元素 (按 DOM 出现次序)
    positive_ti_elements = sorted(
        [e for e in focusable_candidates if e["tabindex_int"] > 0], key=lambda x: x["tabindex_int"]
    )
    zero_ti_elements = [e for e in focusable_candidates if e["tabindex_int"] == 0]
    ordered_elements = positive_ti_elements + zero_ti_elements

    # 4. 模拟 Tab 流转与焦点指示器检查
    traversal_path: list[FocusTraversalStep] = []
    has_focus_trap = False

    for order_idx, item in enumerate(ordered_elements, start=1):
        eid = item["element_id"]
        tag = item["tag_name"]
        has_visible_ring = bool(item.get("has_focus_ring", True))
        container_id = item.get("container_id")
        is_trapped = bool(item.get("is_focus_trapped", False))

        if is_trapped:
            has_focus_trap = True
            defects.append(
                KeyboardDefectItem(
                    defect_id=f"kb_{uuid.uuid4().hex[:6]}",
                    defect_type=KeyboardDefectType.FOCUS_TRAP_DETECTED,
                    severity=KeyboardDefectSeverity.CRITICAL,
                    element_id=eid,
                    description=f"容器 [{container_id or 'modal'}] 产生键盘死锁 (Focus Trap)，无 Escape 退出或循环外泄机制，键盘用户被困死。",
                    remediation_suggestion="在模态弹窗或抽屉中监听 Esc 键退出并恢复先前触发按钮的焦点，或提供显式关闭按钮。",
                )
            )

        if not has_visible_ring:
            defects.append(
                KeyboardDefectItem(
                    defect_id=f"kb_{uuid.uuid4().hex[:6]}",
                    defect_type=KeyboardDefectType.FOCUS_RING_INVISIBLE,
                    severity=KeyboardDefectSeverity.HIGH,
                    element_id=eid,
                    description=f"<{tag}> 元素剥离了焦点样式 (outline: 0/none) 且未配置 focus-visible，纯键盘用户无法感知当前焦点位置。",
                    remediation_suggestion="添加 :focus-visible { outline: 2px solid var(--c-primary); outline-offset: 2px; }。",
                )
            )

        traversal_path.append(
            FocusTraversalStep(
                step_order=order_idx,
                element_id=eid,
                tag_name=tag,
                tabindex=item["tabindex_int"],
                has_visible_focus=has_visible_ring,
                container_id=container_id,
            )
        )

    # 5. 计算键盘导航得分
    crit_c = sum(1 for d in defects if d.severity == KeyboardDefectSeverity.CRITICAL)
    high_c = sum(1 for d in defects if d.severity == KeyboardDefectSeverity.HIGH)
    med_c = sum(1 for d in defects if d.severity == KeyboardDefectSeverity.MEDIUM)
    low_c = sum(1 for d in defects if d.severity == KeyboardDefectSeverity.LOW)

    penalty = (crit_c * 35.0) + (high_c * 20.0) + (med_c * 8.0) + (low_c * 2.0)
    score = max(0.0, min(100.0, 100.0 - penalty))

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", page_name)[:16]
    report_id = f"kb_nav_{safe_name}_{int(now.timestamp())}"

    report = KeyboardNavAuditReport(
        report_id=report_id,
        page_name=page_name,
        total_focusable_elements=len(ordered_elements),
        total_defects_count=len(defects),
        has_focus_trap=has_focus_trap,
        keyboard_accessibility_score_pct=score,
        is_fully_keyboard_accessible=(crit_c == 0 and high_c == 0),
        traversal_path=traversal_path,
        defects=defects,
        created_at=now,
    )

    _KEYBOARD_NAV_REPORTS[report_id] = report
    return report


def get_keyboard_nav_report(report_id: str) -> KeyboardNavAuditReport | None:
    """按 ID 查询单次键盘导航报告。"""
    return _KEYBOARD_NAV_REPORTS.get(report_id)


def list_keyboard_nav_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史键盘导航报告列表。"""
    reports = list(reversed(list(_KEYBOARD_NAV_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
