"""接口服务全链路分布式追踪 TraceID 贯通与慢调用火焰图分析引擎 (D3.3).

兼容 OpenTelemetry / Jaeger 标准分布式调用链，
自动递归解析跨微服务调用的父子依赖树、独占耗时 (Self-Time) 与网络时延分布，
自动提取慢调用 (Slow Span) 并组装为标准多层级火焰图 (Flamegraph) 数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"
    INTERNAL = "INTERNAL"


class SpanStatus(str, Enum):
    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"


@dataclass
class DistributedSpan:
    span_id: str
    trace_id: str
    parent_span_id: str | None
    service_name: str
    operation_name: str
    kind: SpanKind
    start_time_us: int
    duration_us: int
    status: SpanStatus = SpanStatus.OK
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    is_slow: bool = False
    self_time_us: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "service_name": self.service_name,
            "operation_name": self.operation_name,
            "kind": self.kind.value,
            "start_time_us": self.start_time_us,
            "duration_us": self.duration_us,
            "duration_ms": round(self.duration_us / 1000.0, 2),
            "self_time_ms": round(self.self_time_us / 1000.0, 2),
            "status": self.status.value,
            "is_slow": self.is_slow,
            "attributes": self.attributes,
        }


@dataclass
class FlamegraphNode:
    name: str  # 展现文本: "service_name: operation_name"
    value: int  # 耗时数值 (微秒)
    span_id: str
    service_name: str
    duration_ms: float
    self_time_ms: float
    is_slow: bool
    status: str
    children: list[FlamegraphNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "span_id": self.span_id,
            "service_name": self.service_name,
            "duration_ms": self.duration_ms,
            "self_time_ms": self.self_time_ms,
            "is_slow": self.is_slow,
            "status": self.status,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class TraceTreeReport:
    trace_id: str
    root_service: str
    root_operation: str
    total_spans_count: int
    total_duration_ms: float
    services_involved: list[str]
    slow_spans_count: int
    slow_spans: list[dict[str, Any]]
    flamegraph_root: FlamegraphNode
    spans_flat: list[dict[str, Any]]
    bottleneck_summary: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "root_service": self.root_service,
            "root_operation": self.root_operation,
            "total_spans_count": self.total_spans_count,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "services_involved": self.services_involved,
            "slow_spans_count": self.slow_spans_count,
            "slow_spans": self.slow_spans,
            "flamegraph_root": self.flamegraph_root.to_dict(),
            "spans_flat": self.spans_flat,
            "bottleneck_summary": self.bottleneck_summary,
            "created_at": self.created_at.isoformat(),
        }


# 内存 Trace 存储仓库
_TRACE_REPORTS: dict[str, TraceTreeReport] = {}


def _build_node_recursive(
    span: DistributedSpan,
    children_map: dict[str, list[DistributedSpan]],
    slow_threshold_ms: float,
    slow_spans_acc: list[dict[str, Any]],
) -> FlamegraphNode:
    """递归构建火焰图节点并计算独占耗时与慢调用判定。"""
    children = children_map.get(span.span_id, [])
    # 按照开始时间先后对子调用排序
    children.sort(key=lambda c: c.start_time_us)

    children_duration_sum_us = sum(c.duration_us for c in children)
    # 独占耗时 = 自身耗时 - 子调用耗时之和 (不可小于0)
    self_time_us = max(0, span.duration_us - children_duration_sum_us)
    span.self_time_us = self_time_us

    duration_ms = round(span.duration_us / 1000.0, 2)
    self_time_ms = round(self_time_us / 1000.0, 2)

    # 判定慢调用规则：耗时绝对值突破慢阈值，或者自身独占耗时超过 50ms 且占自身总耗时 40% 以上
    if duration_ms >= slow_threshold_ms or (self_time_ms >= 50.0 and self_time_ms >= duration_ms * 0.4):
        span.is_slow = True
        slow_spans_acc.append(span.to_dict())

    child_nodes: list[FlamegraphNode] = []
    for child in children:
        c_node = _build_node_recursive(child, children_map, slow_threshold_ms, slow_spans_acc)
        child_nodes.append(c_node)

    node = FlamegraphNode(
        name=f"{span.service_name}::{span.operation_name}",
        value=span.duration_us,
        span_id=span.span_id,
        service_name=span.service_name,
        duration_ms=duration_ms,
        self_time_ms=self_time_ms,
        is_slow=span.is_slow,
        status=span.status.value,
        children=child_nodes,
    )
    return node


def build_trace_flamegraph(
    trace_id: str,
    raw_spans: list[dict[str, Any]],
    slow_span_threshold_ms: float = 100.0,
) -> TraceTreeReport:
    """对原始 Spans 集合执行拓扑构建、独占耗时计算并输出火焰图结构与性能瓶颈诊断。"""
    if not raw_spans:
        raise ValueError(f"Trace 数据为空，无法构建调用树: {trace_id}")

    spans: list[DistributedSpan] = []
    for r in raw_spans:
        try:
            kind_enum = SpanKind(str(r.get("kind", "INTERNAL")).upper())
        except ValueError:
            kind_enum = SpanKind.INTERNAL

        try:
            status_enum = SpanStatus(str(r.get("status", "OK")).upper())
        except ValueError:
            status_enum = SpanStatus.OK

        span = DistributedSpan(
            span_id=str(r.get("span_id", "")),
            trace_id=trace_id,
            parent_span_id=r.get("parent_span_id"),
            service_name=str(r.get("service_name", "unknown_service")),
            operation_name=str(r.get("operation_name", "unnamed_op")),
            kind=kind_enum,
            start_time_us=int(r.get("start_time_us", 0)),
            duration_us=int(r.get("duration_us", 0)),
            status=status_enum,
            attributes=r.get("attributes") or {},
            events=r.get("events") or [],
        )
        spans.append(span)

    # 建立映射
    span_dict = {s.span_id: s for s in spans}
    children_map: dict[str, list[DistributedSpan]] = {}
    for s in spans:
        if s.parent_span_id:
            children_map.setdefault(s.parent_span_id, []).append(s)

    # 寻找根节点 (parent_span_id 为空，或者其 parent 不在 spans 列表中)
    root_candidates = [s for s in spans if not s.parent_span_id or s.parent_span_id not in span_dict]
    if not root_candidates:
        root_candidates = spans  # 兜底
    root_candidates.sort(key=lambda s: s.start_time_us)
    root_span = root_candidates[0]

    slow_spans_acc: list[dict[str, Any]] = []
    flame_root = _build_node_recursive(root_span, children_map, slow_span_threshold_ms, slow_spans_acc)

    total_duration_ms = round(root_span.duration_us / 1000.0, 2)
    services_involved = sorted(list(set(s.service_name for s in spans)))

    # 瓶颈诊断提炼：找出自身独占耗时 (self_time) 最大的 Span
    max_self_time_span = max(spans, key=lambda s: s.self_time_us)
    max_self_ms = round(max_self_time_span.self_time_us / 1000.0, 2)
    bottleneck_summary = (
        f"全链路总时延 {total_duration_ms}ms，波及微服务 {len(services_involved)} 个。"
        f"核心独占耗时瓶颈位于 [{max_self_time_span.service_name}] 的 [{max_self_time_span.operation_name}]，"
        f"独占自身计算或排队时长达 {max_self_ms}ms (占比 {round(max_self_ms / max(0.001, total_duration_ms) * 100.0, 1)}%)。"
    )

    report = TraceTreeReport(
        trace_id=trace_id,
        root_service=root_span.service_name,
        root_operation=root_span.operation_name,
        total_spans_count=len(spans),
        total_duration_ms=total_duration_ms,
        services_involved=services_involved,
        slow_spans_count=len(slow_spans_acc),
        slow_spans=slow_spans_acc,
        flamegraph_root=flame_root,
        spans_flat=[s.to_dict() for s in spans],
        bottleneck_summary=bottleneck_summary,
    )

    _TRACE_REPORTS[trace_id] = report
    logger.info(
        "Built distributed trace flamegraph trace_id=%s duration=%.2fms spans=%s slow_spans=%s",
        trace_id,
        total_duration_ms,
        len(spans),
        len(slow_spans_acc),
    )
    return report


def get_trace_report(trace_id: str) -> TraceTreeReport | None:
    """查询指定 Trace ID 的火焰图分析报告。"""
    return _TRACE_REPORTS.get(trace_id)


def list_traces() -> list[TraceTreeReport]:
    """获取所有已录入的分布式 Trace 报告列表。"""
    return list(_TRACE_REPORTS.values())


def reset_trace_registry() -> None:
    """仅供单元测试清理状态使用。"""
    _TRACE_REPORTS.clear()
