"""基于流量特征匹配的微服务故障注入 REST API (T4.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.traffic_chaos_fault_injector import (
    create_or_update_fault_rule,
    delete_fault_rule,
    evaluate_and_inject_fault,
    get_chaos_session,
    get_fault_rule,
    list_chaos_sessions,
    list_fault_rules,
    start_chaos_session,
    stop_chaos_session,
)

router = APIRouter(prefix="/chaos-traffic/inject", tags=["流量特征故障注入执行器 (T4.1)"])


class CreateFaultRuleIn(BaseModel):
    rule_name: str = Field(..., description="故障规则名称")
    fault_type: str = Field(
        default="LATENCY", description="故障类型: LATENCY | ERROR_RESPONSE | CORRUPTION | ABRUPT_DROP"
    )
    endpoint_pattern: str | None = Field(default=None, description="接口路径匹配正则 (如 .*/orders/checkout.*)")
    methods: list[str] | None = Field(default=None, description="HTTP 方法列表")
    header_match: dict[str, str] = Field(default_factory=dict, description="匹配的 Header 键值对")
    param_match: dict[str, Any] = Field(default_factory=dict, description="匹配的 Query/Body 字段")
    traffic_ratio: float = Field(default=1.0, ge=0.0, le=1.0, description="故障注入概率 (0.0~1.0)")
    latency_ms: float = Field(default=0.0, ge=0.0, description="注入时延 (毫秒)")
    latency_jitter_max_ms: float = Field(default=0.0, ge=0.0, description="最大随机抖动时延 (毫秒)")
    error_status_code: int = Field(default=500, description="返回的 HTTP/gRPC 状态码")
    error_response_body: str = Field(default='{"error": "Chaos Injected"}', description="错误返回体")
    corruption_mode: str = Field(default="TRUNCATE", description="数据破坏模式: TRUNCATE | GARBLE")
    enabled: bool = Field(default=True, description="是否启用")
    max_triggers_limit: int = Field(default=1000, description="最大触发上限 (防失控保护)")
    rule_id: str | None = Field(default=None, description="规则 ID (更新时必填)")


class EvaluateFaultIn(BaseModel):
    method: str = Field(default="POST", description="请求方法")
    path_or_endpoint: str = Field(..., description="请求路径或端点")
    headers: dict[str, str] = Field(default_factory=dict, description="请求头")
    request_body: str = Field(default="", description="请求体")
    default_status_code: int = Field(default=200, description="无故障时的默认响应码")
    default_response_body: str = Field(default='{"code": 0, "status": "OK"}', description="无故障时的默认响应体")
    execute_actual_delay: bool = Field(default=False, description="是否实际产生线程休眠延时")


class StartSessionIn(BaseModel):
    name: str = Field(..., description="混沌演练批次名称")
    description: str = Field(default="", description="演练描述")
    rule_ids: list[str] | None = Field(default=None, description="挂载的故障规则 ID 列表 (留空挂载全部)")


@router.post("/rules")
async def create_rule_endpoint(
    body: CreateFaultRuleIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """创建或更新混沌故障注入规则 (需工程师权限)。"""
    _ = _user
    rule = create_or_update_fault_rule(
        rule_name=body.rule_name,
        fault_type=body.fault_type,
        endpoint_pattern=body.endpoint_pattern,
        methods=body.methods,
        header_match=body.header_match,
        param_match=body.param_match,
        traffic_ratio=body.traffic_ratio,
        latency_ms=body.latency_ms,
        latency_jitter_max_ms=body.latency_jitter_max_ms,
        error_status_code=body.error_status_code,
        error_response_body=body.error_response_body,
        corruption_mode=body.corruption_mode,
        enabled=body.enabled,
        max_triggers_limit=body.max_triggers_limit,
        rule_id=body.rule_id,
    )
    return {"message": "故障注入规则已保存", "rule": rule.to_dict()}


@router.get("/rules")
async def list_rules_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询生效的故障注入规则列表。"""
    _ = _user
    rules = list_fault_rules()
    return {"total": len(rules), "rules": [r.to_dict() for r in rules]}


@router.delete("/rules/{rule_id}")
async def delete_rule_endpoint(
    rule_id: str,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """删除指定故障规则 (需工程师权限)。"""
    _ = _user
    ok = delete_fault_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"故障规则未找到: {rule_id}")
    return {"message": "规则已删除", "rule_id": rule_id}


@router.post("/evaluate")
async def evaluate_fault_endpoint(
    body: EvaluateFaultIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """在线评估/模拟流量特征是否命中故障注入规则并返回拦截结果。"""
    _ = _user
    res = evaluate_and_inject_fault(
        method=body.method,
        path_or_endpoint=body.path_or_endpoint,
        headers=body.headers,
        request_body=body.request_body,
        default_status_code=body.default_status_code,
        default_response_body=body.default_response_body,
        execute_actual_delay=body.execute_actual_delay,
    )
    return {"message": "故障评估执行完成", "result": res.to_dict()}


@router.post("/sessions/start")
async def start_session_endpoint(
    body: StartSessionIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """启动全局流量混沌演练批次 (需工程师权限)。"""
    _ = _user
    session = start_chaos_session(
        name=body.name,
        description=body.description,
        rule_ids=body.rule_ids,
    )
    return {"message": "混沌演练已启动", "session": session.to_dict()}


@router.post("/sessions/{experiment_id}/stop")
async def stop_session_endpoint(
    experiment_id: str,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """停止混沌演练批次 (需工程师权限)。"""
    _ = _user
    session = stop_chaos_session(experiment_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"演练会话不存在: {experiment_id}")
    return {"message": "混沌演练已停止", "session": session.to_dict()}


@router.get("/sessions")
async def list_sessions_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史混沌演练会话列表。"""
    _ = _user
    sessions = list_chaos_sessions()
    return {"total": len(sessions), "sessions": [s.to_dict() for s in sessions]}


@router.get("/sessions/{experiment_id}")
async def get_session_endpoint(
    experiment_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定演练会话详情与故障统计。"""
    _ = _user
    session = get_chaos_session(experiment_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"演练会话不存在: {experiment_id}")
    return session.to_dict()
