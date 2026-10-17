"""测试执行链路上下文传播拦截器服务 (T1.2)

负责在 Celery Worker 异步执行、多步骤会话演进与网络请求发送期间，
透明传播与继承 W3C TraceContext，杜绝跨进程与多步会话断链问题。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.w3c_trace_context_injector import (
    W3CTraceContext,
    create_child_span_context,
    create_trace_context,
    extract_trace_context,
    inject_trace_context,
    validate_traceparent,
)


@dataclass
class StepTraceRecord:
    step_index: int
    step_name: str
    step_span_id: str
    parent_span_id: Optional[str]
    traceparent: str
    injected_headers: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "step_name": self.step_name,
            "step_span_id": self.step_span_id,
            "parent_span_id": self.parent_span_id,
            "traceparent": self.traceparent,
            "injected_headers": self.injected_headers,
            "timestamp": self.timestamp,
        }


@dataclass
class ExecutionTraceSession:
    run_id: str
    case_id: str
    root_trace_context: W3CTraceContext
    carrier_type: str = "celery_async"
    metadata: Dict[str, Any] = field(default_factory=dict)
    steps: List[StepTraceRecord] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "trace_id": self.root_trace_context.trace_id,
            "root_span_id": self.root_trace_context.span_id,
            "root_traceparent": self.root_trace_context.traceparent,
            "carrier_type": self.carrier_type,
            "metadata": self.metadata,
            "steps_count": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
        }


# 全局轻量级执行追踪上下文仓库
_EXECUTION_TRACE_SESSIONS: Dict[str, ExecutionTraceSession] = {}


def clear_execution_trace_sessions() -> None:
    _EXECUTION_TRACE_SESSIONS.clear()


def list_execution_trace_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    values = list(_EXECUTION_TRACE_SESSIONS.values())
    return [s.to_dict() for s in reversed(values[-limit:])]


def get_execution_trace_session(run_id: str) -> Optional[ExecutionTraceSession]:
    return _EXECUTION_TRACE_SESSIONS.get(run_id)


def bind_execution_trace(
    run_id: str,
    case_id: str,
    parent_traceparent: Optional[str] = None,
    parent_tracestate: str = "",
    carrier_type: str = "celery_async",
    metadata: Optional[Dict[str, Any]] = None,
) -> ExecutionTraceSession:
    """为该次执行任务绑定或衍生根追踪上下文"""
    if parent_traceparent and validate_traceparent(parent_traceparent):
        parent_ctx = extract_trace_context(
            {
                "traceparent": parent_traceparent,
                "tracestate": parent_tracestate,
            }
        )
        if parent_ctx:
            # 作为下游任务执行派生子上下文
            root_ctx = create_child_span_context(
                parent_context=parent_ctx,
                new_tracestate_tag=f"run_id={run_id}",
            )
        else:
            root_ctx = create_trace_context(tracestate=f"run_id={run_id}")
    else:
        root_ctx = create_trace_context(tracestate=f"run_id={run_id}")

    session = ExecutionTraceSession(
        run_id=run_id,
        case_id=case_id,
        root_trace_context=root_ctx,
        carrier_type=carrier_type,
        metadata=metadata or {},
        steps=[],
    )
    _EXECUTION_TRACE_SESSIONS[run_id] = session
    return session


def propagate_step_trace(
    run_id: str,
    step_index: int,
    step_name: str,
    request_headers: Optional[Dict[str, Any]] = None,
    carrier_type: str = "http",
) -> StepTraceRecord:
    """为用例执行的具体步骤分配专属子 Span 并向出站请求头透明注入"""
    session = _EXECUTION_TRACE_SESSIONS.get(run_id)
    if not session:
        # 自动补齐兜底绑定
        session = bind_execution_trace(run_id=run_id, case_id="unknown_case")

    # 衍生属于该步骤的专用子 Span 上下文
    step_ctx = create_child_span_context(
        parent_context=session.root_trace_context,
        new_tracestate_tag=f"step={step_index}",
    )

    injected = inject_trace_context(
        headers=request_headers or {},
        context=step_ctx,
        carrier_type=carrier_type,
    )

    record = StepTraceRecord(
        step_index=step_index,
        step_name=step_name,
        step_span_id=step_ctx.span_id,
        parent_span_id=step_ctx.parent_span_id,
        traceparent=step_ctx.traceparent,
        injected_headers=injected,
    )
    session.steps.append(record)
    return record


def pack_celery_task_headers(run_id: str) -> Dict[str, Any]:
    """将当前执行链路上下文打包为 Celery task headers 字典"""
    session = _EXECUTION_TRACE_SESSIONS.get(run_id)
    if not session:
        return {}
    return {
        "traceparent": session.root_trace_context.traceparent,
        "tracestate": session.root_trace_context.tracestate,
        "x_atp_run_id": run_id,
        "x_atp_case_id": session.case_id,
    }


def unpack_celery_task_headers(headers: Dict[str, Any]) -> Optional[ExecutionTraceSession]:
    """从 Celery 任务接收头解包并恢复追踪会话"""
    if not headers or not isinstance(headers, dict):
        return None
    tp = headers.get("traceparent")
    ts = headers.get("tracestate", "")
    run_id = headers.get("x_atp_run_id") or "recovered_task"
    case_id = headers.get("x_atp_case_id") or "recovered_case"

    if tp and validate_traceparent(tp):
        return bind_execution_trace(
            run_id=run_id,
            case_id=case_id,
            parent_traceparent=tp,
            parent_tracestate=ts,
            carrier_type="celery_worker_receiver",
        )
    return None
