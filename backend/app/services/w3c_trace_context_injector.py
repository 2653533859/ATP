"""W3C TraceContext 标准协议注入与提取服务 (T1.1)

遵循 W3C Trace Context Recommendation (https://www.w3.org/TR/trace-context/) 标准规范：
1. traceparent: 00-{trace_id:32hex}-{parent_id:16hex}-{trace_flags:2hex}
   - version: 当前版本恒为 '00'
   - trace_id: 16 字节 / 32 字符小写十六进制字符串（不能为全0）
   - parent_id: 8 字节 / 16 字符小写十六进制字符串（不能为全0）
   - trace_flags: 8 位位掩码，01 表示录制/采样 (Sampled)，00 表示未采样
2. tracestate: 逗号分隔的 vendor-specific 键值对字符串，例如 'atp=c:stress;s:1,rojo=1'
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

TRACEPARENT_REGEX = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")
INVALID_TRACE_ID = "0" * 32
INVALID_SPAN_ID = "0" * 16


@dataclass
class W3CTraceContext:
    version: str = "00"
    trace_id: str = field(default_factory=lambda: secrets.token_hex(16))
    span_id: str = field(default_factory=lambda: secrets.token_hex(8))
    parent_span_id: Optional[str] = None
    sampled: bool = True
    tracestate: str = ""
    injected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def trace_flags(self) -> str:
        return "01" if self.sampled else "00"

    @property
    def traceparent(self) -> str:
        return f"{self.version}-{self.trace_id.lower()}-{self.span_id.lower()}-{self.trace_flags}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "sampled": self.sampled,
            "trace_flags": self.trace_flags,
            "traceparent": self.traceparent,
            "tracestate": self.tracestate,
            "injected_at": self.injected_at,
        }


# 全局轻量级注入会话内存仓库
_INJECTED_CONTEXT_HISTORY: List[W3CTraceContext] = []


def clear_injected_trace_store() -> None:
    _INJECTED_CONTEXT_HISTORY.clear()


def list_injected_trace_contexts(limit: int = 50) -> List[Dict[str, Any]]:
    return [ctx.to_dict() for ctx in reversed(_INJECTED_CONTEXT_HISTORY[-limit:])]


def generate_trace_id() -> str:
    tid = secrets.token_hex(16)
    while tid == INVALID_TRACE_ID:
        tid = secrets.token_hex(16)
    return tid


def generate_span_id() -> str:
    sid = secrets.token_hex(8)
    while sid == INVALID_SPAN_ID:
        sid = secrets.token_hex(8)
    return sid


def validate_traceparent(traceparent: str) -> bool:
    if not traceparent or not isinstance(traceparent, str):
        return False
    tp = traceparent.strip().lower()
    match = TRACEPARENT_REGEX.match(tp)
    if not match:
        return False
    trace_id, span_id, _ = match.groups()
    if trace_id == INVALID_TRACE_ID or span_id == INVALID_SPAN_ID:
        return False
    return True


def create_trace_context(
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    sampled: bool = True,
    tracestate: str = "",
) -> W3CTraceContext:
    valid_trace_id = (
        trace_id.lower() if trace_id and len(trace_id) == 32 and trace_id != INVALID_TRACE_ID else generate_trace_id()
    )
    valid_span_id = (
        span_id.lower() if span_id and len(span_id) == 16 and span_id != INVALID_SPAN_ID else generate_span_id()
    )

    ctx = W3CTraceContext(
        version="00",
        trace_id=valid_trace_id,
        span_id=valid_span_id,
        parent_span_id=parent_span_id.lower() if parent_span_id else None,
        sampled=sampled,
        tracestate=tracestate.strip(),
    )
    _INJECTED_CONTEXT_HISTORY.append(ctx)
    return ctx


def inject_trace_context(
    headers: Dict[str, Any],
    context: Optional[W3CTraceContext] = None,
    carrier_type: str = "http",
) -> Dict[str, Any]:
    """向目标 Header 载体注入 W3C traceparent 与 tracestate"""
    updated = dict(headers) if headers else {}
    ctx = context or create_trace_context()

    # 规范化键名
    if carrier_type.lower() in ("http", "grpc", "ws"):
        updated["traceparent"] = ctx.traceparent
        if ctx.tracestate:
            updated["tracestate"] = ctx.tracestate
    else:
        # 针对消息队列（如 Kafka/RabbitMQ）支持下划线或前缀兼容
        updated["traceparent"] = ctx.traceparent
        updated["__w3c_traceparent__"] = ctx.traceparent
        if ctx.tracestate:
            updated["tracestate"] = ctx.tracestate

    return updated


def extract_trace_context(headers: Dict[str, Any]) -> Optional[W3CTraceContext]:
    """从输入 Header 载体提取 W3C TraceContext（大小写不敏感）"""
    if not headers or not isinstance(headers, dict):
        return None

    normalized = {str(k).lower(): str(v) for k, v in headers.items()}
    raw_tp = normalized.get("traceparent") or normalized.get("__w3c_traceparent__")
    if not raw_tp or not validate_traceparent(raw_tp):
        return None

    match = TRACEPARENT_REGEX.match(raw_tp.strip().lower())
    if not match:
        return None

    trace_id, span_id, flags_hex = match.groups()
    sampled = bool(int(flags_hex, 16) & 0x01)
    raw_ts = normalized.get("tracestate", "")

    return W3CTraceContext(
        version="00",
        trace_id=trace_id,
        span_id=span_id,
        sampled=sampled,
        tracestate=raw_ts.strip(),
    )


def create_child_span_context(
    parent_context: W3CTraceContext,
    new_span_id: Optional[str] = None,
    new_tracestate_tag: Optional[str] = None,
) -> W3CTraceContext:
    """衍生下游子 Span 上下文：保持 TraceID 不变，将当前 SpanID 作为 parent_span_id，分配全新 SpanID"""
    child_span_id = (
        new_span_id.lower()
        if new_span_id and len(new_span_id) == 16 and new_span_id != INVALID_SPAN_ID
        else generate_span_id()
    )
    merged_ts = parent_context.tracestate
    if new_tracestate_tag:
        merged_ts = f"{new_tracestate_tag},{merged_ts}".strip(",")

    child_ctx = W3CTraceContext(
        version="00",
        trace_id=parent_context.trace_id,
        span_id=child_span_id,
        parent_span_id=parent_context.span_id,
        sampled=parent_context.sampled,
        tracestate=merged_ts,
    )
    _INJECTED_CONTEXT_HISTORY.append(child_ctx)
    return child_ctx
