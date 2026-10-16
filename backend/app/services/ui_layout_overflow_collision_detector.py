"""跨视口文本截断、元素重叠与布局溢出碰撞检测器 (T2.2)。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class LayoutDefectType(str, Enum):
    """布局排版缺陷分类。"""

    ELEMENT_COLLISION_OVERLAP = "ELEMENT_COLLISION_OVERLAP"  # 元素空间碰撞重叠
    VIEWPORT_HORIZONTAL_OVERFLOW = "VIEWPORT_HORIZONTAL_OVERFLOW"  # 视口水平横向溢出
    TEXT_TRUNCATION_OVERFLOW = "TEXT_TRUNCATION_OVERFLOW"  # 文本截断溢出
    CONTAINER_COLLAPSE = "CONTAINER_COLLAPSE"  # 高度塌陷


class LayoutDefectSeverity(str, Enum):
    """缺陷严重度等级。"""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class ElementBox:
    """页面元素空间几何盒模型。"""

    element_id: str
    tag_name: str
    x: float
    y: float
    width: float
    height: float
    scroll_width: float | None = None
    scroll_height: float | None = None
    text_content: str = ""
    z_index: int = 0
    parent_id: str | None = None

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass
class LayoutDefectItem:
    """单个检测到的布局缺陷。"""

    defect_id: str
    defect_type: LayoutDefectType
    severity: LayoutDefectSeverity
    element_id: str
    target_element_id: str | None  # 发生碰撞的目标元素 (若有)
    bounding_box: dict[str, float]
    violation_message: str
    remediation_suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "defect_id": self.defect_id,
            "defect_type": self.defect_type.value,
            "severity": self.severity.value,
            "element_id": self.element_id,
            "target_element_id": self.target_element_id,
            "bounding_box": self.bounding_box,
            "violation_message": self.violation_message,
            "remediation_suggestion": self.remediation_suggestion,
        }


@dataclass
class LayoutDefectReport:
    """布局与碰撞检测审计报告。"""

    report_id: str
    page_name: str
    viewport_width: int
    viewport_height: int
    total_elements_checked: int
    total_defects_count: int
    collision_count: int
    overflow_count: int
    truncation_count: int
    layout_integrity_score_pct: float
    defects: list[LayoutDefectItem]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "page_name": self.page_name,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "total_elements_checked": self.total_elements_checked,
            "total_defects_count": self.total_defects_count,
            "collision_count": self.collision_count,
            "overflow_count": self.overflow_count,
            "truncation_count": self.truncation_count,
            "layout_integrity_score_pct": round(self.layout_integrity_score_pct, 1),
            "defects": [d.to_dict() for d in self.defects],
            "created_at": self.created_at.isoformat(),
        }


# 全局布局报告仓库
_LAYOUT_REPORTS: dict[str, LayoutDefectReport] = {}


def clear_layout_defect_store() -> None:
    """清空布局检测报告仓库（单测专用）。"""
    _LAYOUT_REPORTS.clear()


def detect_layout_defects(
    page_name: str,
    viewport_width: int,
    viewport_height: int,
    elements: list[dict[str, Any]],
) -> LayoutDefectReport:
    """执行 AABB 空间重叠碰撞、横向视口溢出与文本截断检测。"""
    boxes = []
    for e in elements:
        w = float(e.get("width", 0.0))
        h = float(e.get("height", 0.0))
        sw = e.get("scroll_width")
        sh = e.get("scroll_height")
        boxes.append(
            ElementBox(
                element_id=e["element_id"],
                tag_name=e.get("tag_name", "div"),
                x=float(e.get("x", 0.0)),
                y=float(e.get("y", 0.0)),
                width=w,
                height=h,
                scroll_width=float(sw) if sw is not None else w,
                scroll_height=float(sh) if sh is not None else h,
                text_content=e.get("text_content", ""),
                z_index=int(e.get("z_index", 0)),
                parent_id=e.get("parent_id"),
            )
        )

    defects: list[LayoutDefectItem] = []
    collision_c = 0
    overflow_c = 0
    truncation_c = 0

    # 1. 检查视口水平溢出与文本截断
    for b in boxes:
        # 水平溢出: 右边界超出视口宽度 2px 以上
        if b.right > viewport_width + 2.0:
            overflow_c += 1
            overflow_px = round(b.right - viewport_width, 1)
            defects.append(
                LayoutDefectItem(
                    defect_id=f"overflow_{uuid.uuid4().hex[:6]}",
                    defect_type=LayoutDefectType.VIEWPORT_HORIZONTAL_OVERFLOW,
                    severity=LayoutDefectSeverity.HIGH,
                    element_id=b.element_id,
                    target_element_id=None,
                    bounding_box={"x": b.x, "y": b.y, "width": b.width, "height": b.height},
                    violation_message=f"元素 [{b.element_id}] 右边界超出屏幕视口宽度 {overflow_px}px，引发移动端横向滚动条。",
                    remediation_suggestion="为容器添加 max-width: 100% 或设置 overflow-x: hidden / flex-wrap: wrap。",
                )
            )

        # 文本截断: scroll_width 显著大于 client width 且包含文字
        if b.scroll_width and b.scroll_width > b.width + 4.0 and len(b.text_content) > 0:
            truncation_c += 1
            defects.append(
                LayoutDefectItem(
                    defect_id=f"trunc_{uuid.uuid4().hex[:6]}",
                    defect_type=LayoutDefectType.TEXT_TRUNCATION_OVERFLOW,
                    severity=LayoutDefectSeverity.MEDIUM,
                    element_id=b.element_id,
                    target_element_id=None,
                    bounding_box={"x": b.x, "y": b.y, "width": b.width, "height": b.height},
                    violation_message=f"文本元素 [{b.element_id}] 文本溢出容器 ({b.scroll_width}px > {b.width}px)，关键业务文本可能被截断。",
                    remediation_suggestion="配置 word-break: break-all 或为重要文字容器预留自适应伸缩宽度。",
                )
            )

    # 2. 检查两两 AABB 碰撞重叠 (排除父子包含关系)
    n = len(boxes)
    for i in range(n):
        for j in range(i + 1, n):
            b1 = boxes[i]
            b2 = boxes[j]

            # 若二者存在父子关系，跳过包含型重合
            if b1.parent_id == b2.element_id or b2.parent_id == b1.element_id:
                continue

            # AABB 相交判断
            inter_left = max(b1.x, b2.x)
            inter_top = max(b1.y, b2.y)
            inter_right = min(b1.right, b2.right)
            inter_bottom = min(b1.bottom, b2.bottom)

            if inter_right > inter_left + 2.0 and inter_bottom > inter_top + 2.0:
                inter_w = inter_right - inter_left
                inter_h = inter_bottom - inter_top
                inter_area = inter_w * inter_h
                min_area = min(b1.width * b1.height, b2.width * b2.height)

                # 重叠面积占比超过 15%，判定为严重重叠碰撞
                if min_area > 0 and (inter_area / min_area) > 0.15:
                    collision_c += 1
                    sev = (
                        LayoutDefectSeverity.CRITICAL
                        if b1.tag_name in ("button", "a", "input") or b2.tag_name in ("button", "a", "input")
                        else LayoutDefectSeverity.HIGH
                    )
                    defects.append(
                        LayoutDefectItem(
                            defect_id=f"collision_{uuid.uuid4().hex[:6]}",
                            defect_type=LayoutDefectType.ELEMENT_COLLISION_OVERLAP,
                            severity=sev,
                            element_id=b1.element_id,
                            target_element_id=b2.element_id,
                            bounding_box={"x": inter_left, "y": inter_top, "width": inter_w, "height": inter_h},
                            violation_message=f"元素 [{b1.element_id}] 与元素 [{b2.element_id}] 发生空间碰撞重叠，重叠面积 {round(inter_area, 1)}px²。",
                            remediation_suggestion="调整组件绝对定位 (position: absolute) 坐标、添加 margin 间距或配置 Flex/Grid 布局流。",
                        )
                    )

    # 扣分模型
    crit_c = sum(1 for d in defects if d.severity == LayoutDefectSeverity.CRITICAL)
    high_c = sum(1 for d in defects if d.severity == LayoutDefectSeverity.HIGH)
    med_c = sum(1 for d in defects if d.severity == LayoutDefectSeverity.MEDIUM)

    penalty = (crit_c * 25.0) + (high_c * 15.0) + (med_c * 8.0)
    score = max(0.0, min(100.0, 100.0 - penalty))

    now = datetime.now(timezone.utc)
    report_id = f"layout_{page_name[:12]}_{viewport_width}_{int(now.timestamp())}"
    report = LayoutDefectReport(
        report_id=report_id,
        page_name=page_name,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        total_elements_checked=len(boxes),
        total_defects_count=len(defects),
        collision_count=collision_c,
        overflow_count=overflow_c,
        truncation_count=truncation_c,
        layout_integrity_score_pct=score,
        defects=defects,
        created_at=now,
    )
    _LAYOUT_REPORTS[report_id] = report
    return report


def get_layout_defect_report(report_id: str) -> LayoutDefectReport | None:
    """按 ID 查询布局检测报告。"""
    return _LAYOUT_REPORTS.get(report_id)


def list_layout_defect_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史布局检测报告列表。"""
    reports = list(reversed(list(_LAYOUT_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
