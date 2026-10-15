"""Ephemeral Mock Sandbox & Dynamic Port Lifecycle REST API (C3.1)."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.ephemeral_sandbox_manager import (
    dispatch_sandbox_mock_request,
    get_sandbox,
    list_sandboxes,
    provision_ephemeral_sandbox,
    reap_expired_sandboxes,
    terminate_ephemeral_sandbox,
)
from app.services.cross_protocol_session_bus import (
    get_or_create_session_bus,
    get_session_bus,
)

router = APIRouter(prefix="/sandboxes", tags=["瞬时多协议仿真沙箱与端口调度"])


class ProvisionSandboxIn(BaseModel):
    session_name: str = Field(min_length=1, max_length=128, description="沙箱会话名称")
    protocol: str = Field(default="http", description="协议类型: http | grpc | websocket | multi_protocol")
    ttl_seconds: float = Field(default=300.0, ge=10.0, le=3600.0, description="沙箱生命周期 TTL 秒数")
    mock_rules: list[dict[str, Any]] = Field(default_factory=list, description="内置 Mock 响应规则集合")
    metadata: dict[str, Any] = Field(default_factory=dict, description="业务元数据")


class MockDispatchIn(BaseModel):
    method: str = Field(default="GET", description="请求方法")
    path: str = Field(default="/api/v1/resource", description="请求路径")


class SetVarIn(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    value: Any


class PropagateIn(BaseModel):
    direction: str = Field(default="http_to_grpc", description="http_to_grpc | http_to_websocket")


class RenderPayloadIn(BaseModel):
    payload: Any


@router.post("")
async def provision_sandbox_endpoint(
    body: ProvisionSandboxIn,
    _user: User = Depends(require_engineer),
):
    """分配瞬时隔离端口并秒级拉起轻量级 Mock 仿真沙箱。"""
    _ = _user
    try:
        instance = provision_ephemeral_sandbox(
            session_name=body.session_name,
            protocol=body.protocol,
            ttl_seconds=body.ttl_seconds,
            mock_rules=body.mock_rules,
            metadata=body.metadata,
        )
        return instance.to_dict()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.get("")
async def list_sandboxes_endpoint(
    protocol: str | None = Query(default=None, description="按协议过滤"),
    only_active: bool = Query(default=True, description="仅返回活跃可用的沙箱"),
    _user: User = Depends(get_current_user),
):
    """获取当前所有瞬时沙箱实例与已分配端口状态。"""
    _ = _user
    instances = list_sandboxes(protocol=protocol, only_active=only_active)
    return {"total": len(instances), "sandboxes": [s.to_dict() for s in instances]}


@router.get("/{sandbox_id}")
async def get_sandbox_endpoint(
    sandbox_id: str,
    _user: User = Depends(get_current_user),
):
    """获取指定仿真沙箱的访问地址与 Mock 规则明细。"""
    _ = _user
    instance = get_sandbox(sandbox_id)
    if not instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"沙箱不存在: {sandbox_id}")
    return instance.to_dict()


@router.post("/{sandbox_id}/terminate")
async def terminate_sandbox_endpoint(
    sandbox_id: str,
    _user: User = Depends(require_engineer),
):
    """安全回收沙箱并将分配的端口释放回操作系统端口池。"""
    _ = _user
    try:
        instance = terminate_ephemeral_sandbox(sandbox_id)
        return {"message": "沙箱已安全终止并回收端口", "sandbox": instance.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/reap")
async def reap_sandboxes_endpoint(
    _user: User = Depends(require_engineer),
):
    """触发全集群过期沙箱巡检与端口强制回收。"""
    _ = _user
    reaped_count = reap_expired_sandboxes()
    return {"reaped_count": reaped_count, "message": f"成功回收 {reaped_count} 个过期沙箱与网络端口"}


@router.post("/{sandbox_id}/mock-dispatch")
async def mock_dispatch_endpoint(
    sandbox_id: str,
    body: MockDispatchIn,
    _user: User = Depends(get_current_user),
):
    """向指定沙箱的 Mock 路由引擎模拟分发请求并返回响应。"""
    _ = _user
    try:
        return dispatch_sandbox_mock_request(sandbox_id, body.method, body.path)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/bus/init")
async def init_session_bus_endpoint(
    bus_id: str | None = Query(default=None),
    _user: User = Depends(get_current_user),
):
    """初始化或获取跨协议会话级数据共享与透传总线 (Session Bus)。"""
    _ = _user
    bus = get_or_create_session_bus(bus_id)
    return bus.to_dict()


@router.post("/bus/{bus_id}/set-var")
async def set_bus_var_endpoint(
    bus_id: str,
    body: SetVarIn,
    _user: User = Depends(get_current_user),
):
    """向指定跨协议会话总线写入通用变量 (供 HTTP、gRPC、WebSocket 共享)。"""
    _ = _user
    bus = get_session_bus(bus_id)
    if not bus:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"会话总线不存在: {bus_id}")
    bus.set_variable(body.key, body.value)
    return {"message": "变量写入成功", "key": body.key, "value": body.value}


@router.get("/bus/{bus_id}/vars")
async def get_bus_vars_endpoint(
    bus_id: str,
    _user: User = Depends(get_current_user),
):
    """查询会话总线当前存放的所有跨协议共享变量集合。"""
    _ = _user
    bus = get_session_bus(bus_id)
    if not bus:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"会话总线不存在: {bus_id}")
    return {"bus_id": bus_id, "variables": bus.variables}


@router.post("/bus/{bus_id}/propagate")
async def propagate_bus_context_endpoint(
    bus_id: str,
    body: PropagateIn,
    _user: User = Depends(get_current_user),
):
    """触发跨协议凭据与上下文主动透传 (如 HTTP Auth -> gRPC Metadata / WS Handshake)。"""
    _ = _user
    bus = get_session_bus(bus_id)
    if not bus:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"会话总线不存在: {bus_id}")
    if body.direction == "http_to_grpc":
        meta = bus.propagate_http_to_grpc()
        return {"direction": body.direction, "grpc_metadata": meta}
    elif body.direction == "http_to_websocket":
        ws_ctx = bus.propagate_http_to_websocket()
        return {"direction": body.direction, "websocket_context": ws_ctx}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的透传方向: {body.direction}")


@router.post("/bus/{bus_id}/render")
async def render_bus_payload_endpoint(
    bus_id: str,
    body: RenderPayloadIn,
    _user: User = Depends(get_current_user),
):
    """利用会话总线变量对目标报文/路径中的 {{variable}} 执行动态插值渲染。"""
    _ = _user
    bus = get_session_bus(bus_id)
    if not bus:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"会话总线不存在: {bus_id}")
    rendered = bus.render_template(body.payload)
    return {"rendered": rendered}
