"""页面内存泄漏与 DOM 节点脱落幽灵引用智能探测器 (T4.2)。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MemoryLeakType(str, Enum):
    """内存泄露与幽灵引用缺陷分类。"""

    DETACHED_DOM_TREE_LEAK = "DETACHED_DOM_TREE_LEAK"  # 游离脱落的 DOM 树幽灵引用未释放
    UNRELEASED_EVENT_LISTENER_LEAK = "UNRELEASED_EVENT_LISTENER_LEAK"  # 组件卸载后残留全局事件监听器
    PROGRESSIVE_HEAP_LEAK = "PROGRESSIVE_HEAP_LEAK"  # JS 堆内存经 GC 后持续单调攀升
    UNFINISHED_INTERVAL_TIMER = "UNFINISHED_INTERVAL_TIMER"  # 未 clearInterval 的死循环轮询定时器


class MemoryLeakSeverity(str, Enum):
    """内存泄露风险严重度。"""

    CRITICAL = "CRITICAL"  # 阶梯式堆泄露 (长时间运行必将 OOM 崩溃)
    HIGH = "HIGH"  # 大量脱落 DOM 树或监听器未清理
    MEDIUM = "MEDIUM"  # 少量游离节点，存在闭包缓存风险
    LOW = "LOW"  # 微量抖动，处于安全容差内


@dataclass
class DetachedDomLeakItem:
    """脱落的 DOM 节点泄漏明细。"""

    node_id: str
    tag_name: str
    retained_size_bytes: int
    retaining_closure_or_symbol: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "tag_name": self.tag_name,
            "retained_size_bytes": self.retained_size_bytes,
            "retaining_closure_or_symbol": self.retaining_closure_or_symbol,
            "description": self.description,
        }


@dataclass
class MemoryLeakFinding:
    """单个内存缺陷诊断。"""

    finding_id: str
    leak_type: MemoryLeakType
    severity: MemoryLeakSeverity
    title: str
    impact_description: str
    remediation_suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "leak_type": self.leak_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "impact_description": self.impact_description,
            "remediation_suggestion": self.remediation_suggestion,
        }


@dataclass
class MemoryLeakAuditReport:
    """内存泄漏与 DOM 幽灵引用全景审计报告。"""

    report_id: str
    page_or_scenario: str
    initial_heap_bytes: int
    final_heap_bytes: int
    heap_growth_percentage: float
    total_detached_dom_count: int
    total_unreleased_listeners_count: int
    has_critical_leak: bool
    memory_health_score_pct: float
    findings: list[MemoryLeakFinding]
    detached_nodes_sample: list[DetachedDomLeakItem]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "page_or_scenario": self.page_or_scenario,
            "initial_heap_bytes": self.initial_heap_bytes,
            "final_heap_bytes": self.final_heap_bytes,
            "heap_growth_percentage": round(self.heap_growth_percentage, 1),
            "total_detached_dom_count": self.total_detached_dom_count,
            "total_unreleased_listeners_count": self.total_unreleased_listeners_count,
            "has_critical_leak": self.has_critical_leak,
            "memory_health_score_pct": round(self.memory_health_score_pct, 1),
            "findings": [f.to_dict() for f in self.findings],
            "detached_nodes_sample": [d.to_dict() for d in self.detached_nodes_sample],
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告存储
_MEMORY_LEAK_REPORTS: dict[str, MemoryLeakAuditReport] = {}


def clear_memory_leak_store() -> None:
    """清空内存泄漏报告仓库 (单测专用)。"""
    _MEMORY_LEAK_REPORTS.clear()


def diagnose_memory_leak_and_detachment(
    page_or_scenario: str,
    snapshots: list[dict[str, Any]],
    detached_nodes: list[dict[str, Any]] | None = None,
) -> MemoryLeakAuditReport:
    """分析时序快照序列，深度探测堆增长曲线、未解绑事件与 Detached DOM 脱落节点。"""
    detached_nodes = detached_nodes or []
    findings: list[MemoryLeakFinding] = []
    detached_sample: list[DetachedDomLeakItem] = []

    if not snapshots:
        snapshots = [{"js_heap_used_bytes": 10485760, "event_listener_count": 10, "detached_dom_node_count": 0}]

    initial_heap = int(snapshots[0].get("js_heap_used_bytes", 0))
    final_heap = int(snapshots[-1].get("js_heap_used_bytes", initial_heap))

    # 计算堆增长百分比
    if initial_heap > 0:
        heap_growth_pct = ((final_heap - initial_heap) / initial_heap) * 100.0
    else:
        heap_growth_pct = 0.0

    # 1. 检查堆内存阶梯式持续攀升 (经过多次循环操作后增长 > 20%)
    if len(snapshots) >= 3:
        heaps = [int(s.get("js_heap_used_bytes", 0)) for s in snapshots]
        is_strictly_growing = all(heaps[i] <= heaps[i + 1] for i in range(len(heaps) - 1))
        if is_strictly_growing and heap_growth_pct >= 20.0:
            findings.append(
                MemoryLeakFinding(
                    finding_id=f"leak_{uuid.uuid4().hex[:6]}",
                    leak_type=MemoryLeakType.PROGRESSIVE_HEAP_LEAK,
                    severity=MemoryLeakSeverity.CRITICAL,
                    title="JS 堆内存单调递增泄露 (Progressive Heap Leak)",
                    impact_description=(
                        f"在 {len(snapshots)} 次周期快照期间，JS Heap 从 {initial_heap / 1024 / 1024:.1f}MB "
                        f"持续攀升至 {final_heap / 1024 / 1024:.1f}MB (+{heap_growth_pct:.1f}%)，无回落迹象。"
                    ),
                    remediation_suggestion="排查全局缓存对象 (如未清理的 Map/Set)、长寿命闭包引用或未销毁的 ECharts 实例。",
                )
            )

    # 2. 检查脱落的 DOM 树幽灵引用 (Detached DOM Nodes)
    total_detached = int(snapshots[-1].get("detached_dom_node_count", len(detached_nodes)))
    if total_detached > 0 or len(detached_nodes) > 0:
        eff_detached = max(total_detached, len(detached_nodes))
        sev = MemoryLeakSeverity.HIGH if eff_detached >= 10 else MemoryLeakSeverity.MEDIUM
        findings.append(
            MemoryLeakFinding(
                finding_id=f"leak_{uuid.uuid4().hex[:6]}",
                leak_type=MemoryLeakType.DETACHED_DOM_TREE_LEAK,
                severity=sev,
                title=f"检测到 {eff_detached} 个脱落游离 DOM 树节点幽灵引用",
                impact_description="DOM 节点已从文档树中被 removeChild 或 v-if 卸载，但因 JavaScript 引用导致无法被垃圾回收。",
                remediation_suggestion="在组件 unmounted 生命周期中调用 echartsInstance.dispose()，并将保存 DOM 的 ref/闭包变量置为 null。",
            )
        )

        for d in detached_nodes[:10]:
            detached_sample.append(
                DetachedDomLeakItem(
                    node_id=str(d.get("node_id", f"node_{uuid.uuid4().hex[:4]}")),
                    tag_name=str(d.get("tag_name", "div")),
                    retained_size_bytes=int(d.get("retained_size_bytes", 4096)),
                    retaining_closure_or_symbol=str(d.get("retaining_closure", "window.__cache")),
                    description=str(d.get("description", "Detached HTMLDivElement referenced by closure")),
                )
            )

    # 3. 检查未解绑的事件监听器 (Unreleased Event Listeners)
    initial_listeners = int(snapshots[0].get("event_listener_count", 0))
    final_listeners = int(snapshots[-1].get("event_listener_count", initial_listeners))
    listener_delta = final_listeners - initial_listeners
    if listener_delta >= 5:
        findings.append(
            MemoryLeakFinding(
                finding_id=f"leak_{uuid.uuid4().hex[:6]}",
                leak_type=MemoryLeakType.UNRELEASED_EVENT_LISTENER_LEAK,
                severity=MemoryLeakSeverity.HIGH,
                title=f"未释放全局事件监听器残留 (+{listener_delta} listeners)",
                impact_description=f"在页面进出期间，全局监听器数量由 {initial_listeners} 净增至 {final_listeners}，存在卸载遗漏。",
                remediation_suggestion="检查 window.addEventListener('resize') 或 EventBus.$on，确保在 onUnmounted 中对称注销。",
            )
        )

    # 计算内存健康评分 (100 分制)
    crit_c = sum(1 for f in findings if f.severity == MemoryLeakSeverity.CRITICAL)
    high_c = sum(1 for f in findings if f.severity == MemoryLeakSeverity.HIGH)
    med_c = sum(1 for f in findings if f.severity == MemoryLeakSeverity.MEDIUM)

    penalty = (crit_c * 40.0) + (high_c * 20.0) + (med_c * 10.0)
    score = max(0.0, min(100.0, 100.0 - penalty))

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", page_or_scenario)[:16]
    report_id = f"mem_leak_{safe_name}_{int(now.timestamp())}"

    report = MemoryLeakAuditReport(
        report_id=report_id,
        page_or_scenario=page_or_scenario,
        initial_heap_bytes=initial_heap,
        final_heap_bytes=final_heap,
        heap_growth_percentage=heap_growth_pct,
        total_detached_dom_count=max(total_detached, len(detached_nodes)),
        total_unreleased_listeners_count=max(0, listener_delta),
        has_critical_leak=crit_c > 0,
        memory_health_score_pct=score,
        findings=findings,
        detached_nodes_sample=detached_sample,
        created_at=now,
    )

    _MEMORY_LEAK_REPORTS[report_id] = report
    return report


def get_memory_leak_report(report_id: str) -> MemoryLeakAuditReport | None:
    """按 ID 查询单次内存泄漏报告。"""
    return _MEMORY_LEAK_REPORTS.get(report_id)


def list_memory_leak_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史内存审计报告列表。"""
    reports = list(reversed(list(_MEMORY_LEAK_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
