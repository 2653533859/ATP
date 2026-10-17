"""全链路分布式追踪与 OpenTelemetry 观测接口 (T1.1)"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_engineer
from app.models.user import User
from app.services.w3c_trace_context_injector import (
    clear_injected_trace_store,
    create_child_span_context,
    create_trace_context,
    extract_trace_context,
    inject_trace_context,
    list_injected_trace_contexts,
    validate_traceparent,
)
from app.services.test_execution_trace_propagator import (
    bind_execution_trace,
    clear_execution_trace_sessions,
    get_execution_trace_session,
    list_execution_trace_sessions,
    propagate_step_trace,
)

router = APIRouter(prefix="/observability/trace", tags=["Observability Trace"])


class InjectTraceRequest(BaseModel):
    headers: Dict[str, Any] = Field(default_factory=dict, description="待注入追踪上下文的请求头字典")
    trace_id: Optional[str] = Field(None, description="自定义 32 字符小写 16 进制 TraceID")
    span_id: Optional[str] = Field(None, description="自定义 16 字符小写 16 进制 SpanID")
    sampled: bool = Field(True, description="采样标记")
    tracestate: str = Field("", description="供应商定制链路状态串")
    carrier_type: str = Field("http", description="载体协议 (http, grpc, ws, mq)")


class ExtractTraceRequest(BaseModel):
    headers: Dict[str, Any] = Field(..., description="待提取 W3C Traceparent 的请求头字典")


class ChildSpanRequest(BaseModel):
    parent_traceparent: str = Field(..., description="父级 traceparent 字符串")
    parent_tracestate: str = Field("", description="父级 tracestate 字符串")
    new_span_id: Optional[str] = Field(None, description="可选指定新子 SpanID")
    new_tracestate_tag: Optional[str] = Field(None, description="新附加的 tracestate 标签")


class BindExecutionTraceRequest(BaseModel):
    run_id: str = Field(..., description="执行运行任务 ID")
    case_id: str = Field(..., description="测试用例 ID")
    parent_traceparent: Optional[str] = Field(None, description="上游传入的 traceparent")
    parent_tracestate: str = Field("", description="上游传入的 tracestate")
    carrier_type: str = Field("celery_async", description="载体通道类型")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="执行元数据")


class PropagateStepRequest(BaseModel):
    run_id: str = Field(..., description="执行运行任务 ID")
    step_index: int = Field(..., description="测试步骤序号 (1, 2, 3...)")
    step_name: str = Field(..., description="测试步骤名称")
    request_headers: Dict[str, Any] = Field(default_factory=dict, description="出站请求头字典")
    carrier_type: str = Field("http", description="出站协议类型")


@router.post("/inject")
def inject_trace_endpoint(
    payload: InjectTraceRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """为请求头注入标准 W3C TraceContext (traceparent & tracestate)"""
    ctx = create_trace_context(
        trace_id=payload.trace_id,
        span_id=payload.span_id,
        sampled=payload.sampled,
        tracestate=payload.tracestate,
    )
    injected_headers = inject_trace_context(payload.headers, context=ctx, carrier_type=payload.carrier_type)
    return {
        "message": "W3C TraceContext 注入成功",
        "context": ctx.to_dict(),
        "injected_headers": injected_headers,
    }


@router.post("/extract")
def extract_trace_endpoint(
    payload: ExtractTraceRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """从请求头提取并校验 W3C TraceContext"""
    ctx = extract_trace_context(payload.headers)
    if not ctx:
        raise HTTPException(status_code=400, detail="请求头中未找到合法且非全零的 W3C traceparent 头部")
    return {
        "message": "W3C TraceContext 提取成功",
        "context": ctx.to_dict(),
    }


@router.post("/child-span")
def create_child_span_endpoint(
    payload: ChildSpanRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """从父级 traceparent 衍生下游子 Span 追踪上下文"""
    if not validate_traceparent(payload.parent_traceparent):
        raise HTTPException(status_code=400, detail="提供的父级 traceparent 格式不合法或为全0值")

    dummy_headers = {"traceparent": payload.parent_traceparent, "tracestate": payload.parent_tracestate}
    parent_ctx = extract_trace_context(dummy_headers)
    if not parent_ctx:
        raise HTTPException(status_code=400, detail="无法解析父级追踪上下文")

    child_ctx = create_child_span_context(
        parent_context=parent_ctx,
        new_span_id=payload.new_span_id,
        new_tracestate_tag=payload.new_tracestate_tag,
    )
    return {
        "message": "下游子 Span 上下文创建成功",
        "child_context": child_ctx.to_dict(),
    }


@router.get("/contexts")
def list_contexts_endpoint(
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取最近内存记录的链路追踪上下文列表"""
    items = list_injected_trace_contexts(limit=limit)
    return {
        "total": len(items),
        "contexts": items,
    }


@router.delete("/contexts")
def clear_contexts_endpoint(
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """清空链路追踪上下文内存仓库"""
    clear_injected_trace_store()
    return {"message": "已清空追踪上下文历史"}


@router.post("/execution/bind")
def bind_execution_trace_endpoint(
    payload: BindExecutionTraceRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """为测试执行任务绑定全局根 TraceContext"""
    session = bind_execution_trace(
        run_id=payload.run_id,
        case_id=payload.case_id,
        parent_traceparent=payload.parent_traceparent,
        parent_tracestate=payload.parent_tracestate,
        carrier_type=payload.carrier_type,
        metadata=payload.metadata,
    )
    return {
        "message": "执行链路跟踪会话已成功绑定",
        "session": session.to_dict(),
    }


@router.post("/execution/step")
def propagate_step_trace_endpoint(
    payload: PropagateStepRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """为步骤分配子 Span 并在出站请求头中透明注入 traceparent"""
    record = propagate_step_trace(
        run_id=payload.run_id,
        step_index=payload.step_index,
        step_name=payload.step_name,
        request_headers=payload.request_headers,
        carrier_type=payload.carrier_type,
    )
    return {
        "message": "步骤子 Span 追踪上下文已成功注入",
        "step_record": record.to_dict(),
    }


@router.get("/trail/{run_id}")
def get_execution_trail_endpoint(
    run_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取指定执行任务的完整调用链痕迹 (Trail)"""
    session = get_execution_trace_session(run_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"未找到运行任务 {run_id} 的追踪会话")
    return {
        "run_id": run_id,
        "session": session.to_dict(),
    }


@router.get("/sessions")
def list_sessions_endpoint(
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """列出当前内存记录的执行追踪会话"""
    items = list_execution_trace_sessions(limit=limit)
    return {
        "total": len(items),
        "sessions": items,
    }


@router.delete("/sessions")
def clear_sessions_endpoint(
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """清空执行追踪会话历史"""
    clear_execution_trace_sessions()
    return {"message": "已清空执行追踪会话历史"}
