"""OpenTelemetry 全链路 Span 追踪采集中继与调用树重构引擎 (T1.1)。

遵循 W3C TraceContext (traceparent) 与 OpenTelemetry 规范：
1. 采集中继微服务调用链 Span，解析父子依赖关系 (parent_span_id)；
2. 依据时间戳与级联拓扑重构深度调用树 (Trace Hierarchy Tree)；
3. 提取服务名、操作名、耗时时延、错误状态码与异常堆栈。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import re
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"
    INTERNAL = "INTERNAL"


class SpanStatusCode(str, Enum):
    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"


_W3C_TRACEPARENT_REGEX = re.compile(r"^00-([0-9a-fA-F]{32})-([0-9a-fA-F]{16})-([0-9a-fA-F]{2})$")


def parse_w3c_traceparent(header_val: str) -> tuple[str, str, str] | None:
    """解析 W3C TraceContext traceparent 请求头 (00-{trace_id}-{parent_id}-{flags})。"""
    if not header_val:
        return None
    match = _W3C_TRACEPARENT_REGEX.match(header_val.strip())
    if not match:
        return None
    trace_id, parent_id, flags = match.groups()
    return trace_id.lower(), parent_id.lower(), flags


def format_w3c_traceparent(trace_id: str, span_id: str, flags: str = "01") -> str:
    """格式化生成标准 W3C TraceContext 请求头。"""
    tid = trace_id.lower().replace("-", "").zfill(32)[-32:]
    sid = span_id.lower().replace("-", "").zfill(16)[-16:]
    return f"00-{tid}-{sid}-{flags}"


@dataclass
class TelemetrySpan:
    trace_id: str
    span_id: str
    name: str
    service_name: str
    parent_span_id: str | None = None
    kind: SpanKind = SpanKind.SERVER
    start_time_us: int = 0
    end_time_us: int = 0
    duration_ms: float = 0.0
    status_code: SpanStatusCode = SpanStatusCode.OK
    status_message: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "service_name": self.service_name,
            "kind": self.kind.value,
            "start_time_us": self.start_time_us,
            "end_time_us": self.end_time_us,
            "duration_ms": round(self.duration_ms, 2),
            "status_code": self.status_code.value,
            "status_message": self.status_message,
            "attributes": self.attributes,
            "events": self.events,
        }


@dataclass
class SpanTreeNode:
    span: TelemetrySpan
    children: list[SpanTreeNode] = field(default_factory=list)
    depth: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.span.to_dict(),
            "depth": self.depth,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class TraceTreeReport:
    trace_id: str
    root_span_id: str
    total_spans_count: int
    total_duration_ms: float
    services_involved: list[str]
    has_error: bool
    root_nodes: list[SpanTreeNode]
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "root_span_id": self.root_span_id,
            "total_spans_count": self.total_spans_count,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "services_involved": self.services_involved,
            "has_error": self.has_error,
            "root_nodes": [r.to_dict() for r in self.root_nodes],
            "extracted_at": self.extracted_at.isoformat(),
        }


# 内存 Span 存储仓库: trace_id -> list[TelemetrySpan]
_SPAN_STORE: dict[str, list[TelemetrySpan]] = {}


def ingest_spans(spans_payload: list[dict[str, Any]]) -> dict[str, Any]:
    """批量采集中继 OpenTelemetry Span 数组。"""
    ingested_count = 0
    traces_updated = set()

    for item in spans_payload:
        trace_id = str(item.get("trace_id") or uuid.uuid4().hex).lower().replace("-", "")
        span_id = str(item.get("span_id") or uuid.uuid4().hex[:16]).lower().replace("-", "")
        parent_span_id = item.get("parent_span_id")
        if parent_span_id:
            parent_span_id = str(parent_span_id).lower().replace("-", "")

        name = str(item.get("name") or "operation")
        service_name = str(item.get("service_name") or "unknown-service")

        raw_kind = str(item.get("kind") or "SERVER").upper()
        try:
            kind = SpanKind(raw_kind)
        except ValueError:
            kind = SpanKind.SERVER

        start_time_us = int(item.get("start_time_us") or 0)
        end_time_us = int(item.get("end_time_us") or start_time_us)

        duration_ms = item.get("duration_ms")
        if duration_ms is not None:
            duration_ms = float(duration_ms)
        elif end_time_us >= start_time_us:
            duration_ms = (end_time_us - start_time_us) / 1000.0
        else:
            duration_ms = 0.0

        raw_status = str(item.get("status_code") or "OK").upper()
        try:
            status_code = SpanStatusCode(raw_status)
        except ValueError:
            status_code = SpanStatusCode.OK

        span = TelemetrySpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            service_name=service_name,
            kind=kind,
            start_time_us=start_time_us,
            end_time_us=end_time_us,
            duration_ms=duration_ms,
            status_code=status_code,
            status_message=str(item.get("status_message") or ""),
            attributes=dict(item.get("attributes") or {}),
            events=list(item.get("events") or []),
        )

        if trace_id not in _SPAN_STORE:
            _SPAN_STORE[trace_id] = []
        _SPAN_STORE[trace_id].append(span)

        ingested_count += 1
        traces_updated.add(trace_id)

    return {
        "ingested_count": ingested_count,
        "traces_updated_count": len(traces_updated),
        "trace_ids": list(traces_updated),
    }


def reconstruct_trace_tree(trace_id: str) -> TraceTreeReport | None:
    """根据 TraceId 重构多层级调用树。"""
    tid = trace_id.lower().replace("-", "")
    spans = _SPAN_STORE.get(tid)
    if not spans:
        return None

    # 按 start_time 升序排
    sorted_spans = sorted(spans, key=lambda s: s.start_time_us)

    span_map = {s.span_id: s for s in sorted_spans}
    children_map: dict[str, list[TelemetrySpan]] = {s.span_id: [] for s in sorted_spans}
    roots: list[TelemetrySpan] = []

    for s in sorted_spans:
        if s.parent_span_id and s.parent_span_id in span_map:
            children_map[s.parent_span_id].append(s)
        else:
            roots.append(s)

    services_set = set()
    has_error = False
    min_start = sorted_spans[0].start_time_us
    max_end = sorted_spans[0].end_time_us

    for s in sorted_spans:
        services_set.add(s.service_name)
        if s.status_code == SpanStatusCode.ERROR:
            has_error = True
        if s.start_time_us < min_start:
            min_start = s.start_time_us
        if s.end_time_us > max_end:
            max_end = s.end_time_us

    total_duration_ms = max(0.0, (max_end - min_start) / 1000.0)

    def _build_node(s: TelemetrySpan, depth: int) -> SpanTreeNode:
        node = SpanTreeNode(span=s, depth=depth)
        for child_span in children_map.get(s.span_id, []):
            node.children.append(_build_node(child_span, depth + 1))
        return node

    root_nodes = [_build_node(r, 0) for r in roots]
    root_span_id = roots[0].span_id if roots else ""

    return TraceTreeReport(
        trace_id=tid,
        root_span_id=root_span_id,
        total_spans_count=len(sorted_spans),
        total_duration_ms=total_duration_ms,
        services_involved=sorted(list(services_set)),
        has_error=has_error,
        root_nodes=root_nodes,
    )


def list_trace_summaries(
    limit: int = 50,
    service_name: str | None = None,
    has_error: bool | None = None,
    min_duration_ms: float = 0.0,
) -> list[dict[str, Any]]:
    """查询追踪链路概览摘要列表。"""
    summaries = []

    for tid in _SPAN_STORE:
        tree = reconstruct_trace_tree(tid)
        if not tree:
            continue

        if service_name and service_name not in tree.services_involved:
            continue
        if has_error is not None and tree.has_error != has_error:
            continue
        if tree.total_duration_ms < min_duration_ms:
            continue

        root_name = tree.root_nodes[0].span.name if tree.root_nodes else "root"
        root_service = tree.root_nodes[0].span.service_name if tree.root_nodes else "unknown"

        summaries.append(
            {
                "trace_id": tree.trace_id,
                "root_span_id": tree.root_span_id,
                "root_operation": root_name,
                "root_service": root_service,
                "total_spans_count": tree.total_spans_count,
                "total_duration_ms": tree.total_duration_ms,
                "services_involved": tree.services_involved,
                "has_error": tree.has_error,
                "extracted_at": tree.extracted_at.isoformat(),
            }
        )

    # 按耗时降序
    summaries.sort(key=lambda s: float(str(s["total_duration_ms"])), reverse=True)
    return summaries[:limit]


def clear_telemetry_store() -> int:
    """清空 Span 缓存仓库。"""
    count = len(_SPAN_STORE)
    _SPAN_STORE.clear()
    return count
