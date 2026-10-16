"""跨服务调用关键路径时延分析与火焰图性能瓶颈定位引擎 (T1.2)。

针对微服务高并发、异步并行调用与级联依赖链：
1. 识别分布式 Trace 的关键执行路径 (Critical Path，决定端到端总时延的最长时序依赖链)；
2. 计算各 Span 的独占耗时 (Self-Time) 与关键路径贡献占比 (Critical Path Ratio)；
3. 智能定位耗时首要瓶颈 (DATABASE_SLOW_QUERY / EXTERNAL_HTTP_LATENCY / INTERNAL_COMPUTATION / QUEUE_LAG)；
4. 输出符合现代前端可视化规范的标准分层火焰图数据结构 (Flamegraph Structure)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any

from app.services.distributed_trace_telemetry_relay import (
    reconstruct_trace_tree,
)

logger = logging.getLogger(__name__)


class BottleneckCategory(str, Enum):
    DATABASE_SLOW_QUERY = "DATABASE_SLOW_QUERY"  # 数据库慢查询/锁等待
    EXTERNAL_HTTP_LATENCY = "EXTERNAL_HTTP_LATENCY"  # 外部第三方依赖服务高时延
    INTERNAL_COMPUTATION = "INTERNAL_COMPUTATION"  # 业务内部密集计算或死循环
    QUEUE_LAG = "QUEUE_LAG"  # 消息队列投递或消费滞后
    NONE = "NONE"


@dataclass
class CriticalPathSpan:
    span_id: str
    parent_span_id: str | None
    name: str
    service_name: str
    duration_ms: float
    self_time_ms: float
    critical_path_ratio_pct: float
    is_bottleneck: bool
    bottleneck_category: BottleneckCategory

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "service_name": self.service_name,
            "duration_ms": round(self.duration_ms, 2),
            "self_time_ms": round(self.self_time_ms, 2),
            "critical_path_ratio_pct": round(self.critical_path_ratio_pct, 2),
            "is_bottleneck": self.is_bottleneck,
            "bottleneck_category": self.bottleneck_category.value,
        }


@dataclass
class FlamegraphNode:
    name: str
    value: float  # 总耗时 ms
    self_value: float  # 独占自身耗时 ms
    service_name: str
    span_id: str
    is_critical_path: bool = False
    is_bottleneck: bool = False
    bottleneck_category: BottleneckCategory = BottleneckCategory.NONE
    children: list[FlamegraphNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 2),
            "self_value": round(self.self_value, 2),
            "service_name": self.service_name,
            "span_id": self.span_id,
            "is_critical_path": self.is_critical_path,
            "is_bottleneck": self.is_bottleneck,
            "bottleneck_category": self.bottleneck_category.value,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class CriticalPathProfileReport:
    trace_id: str
    total_trace_duration_ms: float
    critical_path_duration_ms: float
    critical_path_spans_count: int
    critical_path: list[CriticalPathSpan]
    primary_bottleneck: CriticalPathSpan | None
    flamegraph_root: FlamegraphNode
    diagnosis_summary: str
    profiled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "total_trace_duration_ms": round(self.total_trace_duration_ms, 2),
            "critical_path_duration_ms": round(self.critical_path_duration_ms, 2),
            "critical_path_spans_count": self.critical_path_spans_count,
            "critical_path": [s.to_dict() for s in self.critical_path],
            "primary_bottleneck": self.primary_bottleneck.to_dict() if self.primary_bottleneck else None,
            "flamegraph_root": self.flamegraph_root.to_dict(),
            "diagnosis_summary": self.diagnosis_summary,
            "profiled_at": self.profiled_at.isoformat(),
        }


def _detect_bottleneck_category(span: dict[str, Any], self_time_ms: float) -> BottleneckCategory:
    """根据 Span 属性与耗时特征判定瓶颈类型。"""
    attrs = span.get("attributes", {})
    kind = str(span.get("kind", "")).upper()

    # 1. 数据库
    if "db.system" in attrs or "db.statement" in attrs or "sql" in span.get("name", "").lower():
        if self_time_ms >= 50.0:
            return BottleneckCategory.DATABASE_SLOW_QUERY

    # 2. 外部 HTTP/RPC 客户端调用
    if kind == "CLIENT" or "http.url" in attrs or "http.status_code" in attrs:
        if self_time_ms >= 100.0 or float(span.get("duration_ms", 0)) >= 200.0:
            return BottleneckCategory.EXTERNAL_HTTP_LATENCY

    # 3. 消息队列
    if kind in ("PRODUCER", "CONSUMER") or "messaging.system" in attrs:
        return BottleneckCategory.QUEUE_LAG

    # 4. 内部计算
    if self_time_ms >= 80.0:
        return BottleneckCategory.INTERNAL_COMPUTATION

    return BottleneckCategory.NONE


def profile_spans_critical_path(
    trace_id: str,
    spans: list[dict[str, Any]],
) -> CriticalPathProfileReport:
    """对一组 Span 执行关键路径推导、瓶颈识别与火焰图结构生成。"""
    if not spans:
        empty_node = FlamegraphNode(
            name="empty",
            value=0.0,
            self_value=0.0,
            service_name="none",
            span_id="",
        )
        return CriticalPathProfileReport(
            trace_id=trace_id,
            total_trace_duration_ms=0.0,
            critical_path_duration_ms=0.0,
            critical_path_spans_count=0,
            critical_path=[],
            primary_bottleneck=None,
            flamegraph_root=empty_node,
            diagnosis_summary="链路无 Span 数据",
        )

    span_map: dict[str, dict[str, Any]] = {}
    children_map: dict[str, list[str]] = {}

    for s in spans:
        sid = str(s.get("span_id", "")).lower()
        span_map[sid] = s
        children_map[sid] = []

    roots: list[str] = []
    for sid, s in span_map.items():
        pid = s.get("parent_span_id")
        if pid and str(pid).lower() in span_map:
            children_map[str(pid).lower()].append(sid)
        else:
            roots.append(sid)

    # 1. 计算各 Span 的 self_time (自身耗时 = duration - 所有子节点 duration 之和)
    self_time_map: dict[str, float] = {}
    for sid, s in span_map.items():
        dur = float(s.get("duration_ms", 0.0))
        children_dur_sum = sum(float(span_map[c].get("duration_ms", 0.0)) for c in children_map.get(sid, []))
        self_time = max(0.0, dur - children_dur_sum)
        self_time_map[sid] = self_time

    # 2. 动态规划寻找关键路径 (Critical Path: 从根到叶子使时延最大的路径)
    # 递归备忘录: memo[sid] -> (path_duration, [list_of_sids])
    memo: dict[str, tuple[float, list[str]]] = {}

    def _find_longest_path(sid: str) -> tuple[float, list[str]]:
        if sid in memo:
            return memo[sid]

        children = children_map.get(sid, [])
        cur_dur = float(span_map[sid].get("duration_ms", 0.0))

        if not children:
            res = (cur_dur, [sid])
            memo[sid] = res
            return res

        best_child_dur = 0.0
        best_child_path: list[str] = []

        for cid in children:
            c_dur, c_path = _find_longest_path(cid)
            if c_dur > best_child_dur:
                best_child_dur = c_dur
                best_child_path = c_path

        # 关键路径总长 = 当前 span 的 self_time + 最长子路径
        total_p_dur = self_time_map.get(sid, 0.0) + best_child_dur
        res = (total_p_dur, [sid] + best_child_path)
        memo[sid] = res
        return res

    # 选取时延最长的根节点
    best_overall_dur = 0.0
    best_critical_sids: list[str] = []

    for r_sid in roots:
        r_dur, r_path = _find_longest_path(r_sid)
        if r_dur > best_overall_dur:
            best_overall_dur = r_dur
            best_critical_sids = r_path

    if not best_critical_sids and roots:
        best_critical_sids = [roots[0]]
        best_overall_dur = float(span_map[roots[0]].get("duration_ms", 0.0))

    critical_set = set(best_critical_sids)

    # 3. 寻找关键路径上的最主要瓶颈 (Primary Bottleneck)
    critical_path_spans: list[CriticalPathSpan] = []
    primary_bottleneck: CriticalPathSpan | None = None
    max_bottleneck_impact = -1.0

    for sid in best_critical_sids:
        s = span_map[sid]
        self_t = self_time_map.get(sid, 0.0)
        dur = float(s.get("duration_ms", 0.0))
        ratio = (self_t / best_overall_dur * 100.0) if best_overall_dur > 0 else 0.0

        category = _detect_bottleneck_category(s, self_t)

        if self_t > max_bottleneck_impact:
            max_bottleneck_impact = self_t

        cp_span = CriticalPathSpan(
            span_id=sid,
            parent_span_id=s.get("parent_span_id"),
            name=str(s.get("name", "")),
            service_name=str(s.get("service_name", "")),
            duration_ms=dur,
            self_time_ms=self_t,
            critical_path_ratio_pct=ratio,
            is_bottleneck=False,  # 稍后标记唯一首要瓶颈
            bottleneck_category=category,
        )
        critical_path_spans.append(cp_span)

    # 标记唯一首要瓶颈
    if critical_path_spans:
        # 自身耗时最长者为瓶颈
        bottleneck_target = max(critical_path_spans, key=lambda x: x.self_time_ms)
        bottleneck_target.is_bottleneck = True
        primary_bottleneck = bottleneck_target

    # 4. 构建分层火焰图树 (FlamegraphNode)
    def _build_flamegraph_node(sid: str) -> FlamegraphNode:
        s = span_map[sid]
        dur = float(s.get("duration_ms", 0.0))
        self_t = self_time_map.get(sid, 0.0)
        is_cp = sid in critical_set
        is_bn = primary_bottleneck is not None and sid == primary_bottleneck.span_id
        cat = (
            primary_bottleneck.bottleneck_category
            if (is_bn and primary_bottleneck)
            else _detect_bottleneck_category(s, self_t)
        )

        node = FlamegraphNode(
            name=str(s.get("name", "")),
            value=dur,
            self_value=self_t,
            service_name=str(s.get("service_name", "")),
            span_id=sid,
            is_critical_path=is_cp,
            is_bottleneck=is_bn,
            bottleneck_category=cat,
        )

        for cid in children_map.get(sid, []):
            node.children.append(_build_flamegraph_node(cid))

        return node

    # 如果有多个根，用虚拟根包裹
    if len(roots) == 1:
        flamegraph_root = _build_flamegraph_node(roots[0])
    else:
        root_nodes = [_build_flamegraph_node(r) for r in roots]
        total_root_dur = sum(r.value for r in root_nodes)
        flamegraph_root = FlamegraphNode(
            name="root",
            value=total_root_dur,
            self_value=0.0,
            service_name="multi-root",
            span_id="virtual_root",
            is_critical_path=True,
            children=root_nodes,
        )

    # 诊断总结
    if primary_bottleneck and primary_bottleneck.self_time_ms > 0:
        diagnosis = (
            f"关键路径共 {len(best_critical_sids)} 个 Span，总时延 {round(best_overall_dur, 2)}ms。"
            f"首要瓶颈为 [{primary_bottleneck.service_name}] 的 [{primary_bottleneck.name}]，"
            f"自身独占耗时 {round(primary_bottleneck.self_time_ms, 2)}ms (占比 {round(primary_bottleneck.critical_path_ratio_pct, 1)}%)，"
            f"判定类型为: {primary_bottleneck.bottleneck_category.value}。"
        )
    else:
        diagnosis = f"关键路径共 {len(best_critical_sids)} 个 Span，各环节时延分布平缓，无显著单点瓶颈。"

    return CriticalPathProfileReport(
        trace_id=trace_id,
        total_trace_duration_ms=round(best_overall_dur, 2),
        critical_path_duration_ms=round(best_overall_dur, 2),
        critical_path_spans_count=len(best_critical_sids),
        critical_path=critical_path_spans,
        primary_bottleneck=primary_bottleneck,
        flamegraph_root=flamegraph_root,
        diagnosis_summary=diagnosis,
    )


def profile_trace_critical_path_by_id(trace_id: str) -> CriticalPathProfileReport | None:
    """根据 TraceId 从已采集的链路数据中直接执行关键路径与火焰图分析。"""
    tree = reconstruct_trace_tree(trace_id)
    if not tree:
        return None

    # 从 tree 中提取所有扁平 Span
    spans: list[dict[str, Any]] = []

    def _collect(node: Any) -> None:
        spans.append(node.span.to_dict())
        for child in node.children:
            _collect(child)

    for r in tree.root_nodes:
        _collect(r)

    return profile_spans_critical_path(trace_id, spans)
