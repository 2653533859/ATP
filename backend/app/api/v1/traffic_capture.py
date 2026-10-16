"""微服务网关旁路流量捕获与 HTTP/gRPC 多协议解析过滤 REST API (T1.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.traffic_capture_gateway import (
    capture_traffic_payload,
    clear_captured_traffic,
    configure_capture_filter,
    get_capture_filter_config,
    get_capture_metrics,
    get_captured_traffic_by_id,
    list_captured_traffic,
)

router = APIRouter(prefix="/traffic/capture", tags=["微服务网关旁路流量捕获 (T1.1)"])


class CaptureFilterConfigIn(BaseModel):
    include_paths: list[str] | None = Field(default=None, description="包含的路径正则列表")
    exclude_paths: list[str] | None = Field(default=None, description="排除的路径正则列表")
    allowed_methods: list[str] | None = Field(default=None, description="放行的方法列表")
    sampling_rate: float | None = Field(default=None, ge=0.0, le=1.0, description="采样率 (0.0~1.0)")
    capture_request_body: bool | None = Field(default=None, description="是否抓取请求体")
    capture_response_body: bool | None = Field(default=None, description="是否抓取响应体")
    max_body_bytes: int | None = Field(default=None, ge=128, le=10485760, description="最大截断字节上限")


class IngestTrafficIn(BaseModel):
    protocol: str = Field(default="HTTP", description="协议: HTTP | GRPC | WEBSOCKET")
    method: str = Field(default="GET", description="请求方法或 RPC 方法名")
    path_or_endpoint: str = Field(
        ..., description="请求路径或 RPC 服务端点 (如 /api/v1/orders 或 /order.OrderService/Create)"
    )
    headers: dict[str, str] = Field(default_factory=dict, description="请求头元数据")
    query_params: dict[str, str] = Field(default_factory=dict, description="Query 参数")
    request_body: str = Field(default="", description="请求体原文")
    response_status_code: int = Field(default=200, description="响应状态码或 gRPC 状态码")
    response_body: str = Field(default="", description="响应体原文")
    duration_ms: float = Field(default=0.0, ge=0.0, description="调用执行耗时 (毫秒)")
    client_ip: str | None = Field(default=None, description="客户端源 IP")
    tags: dict[str, str] = Field(default_factory=dict, description="自定义业务标签")


class BatchIngestTrafficIn(BaseModel):
    items: list[IngestTrafficIn] = Field(..., min_length=1, description="批量捕获流量列表")


@router.post("/config")
async def update_capture_config_endpoint(
    body: CaptureFilterConfigIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """更新流量捕获网关过滤规则与采样率 (需工程师权限)。"""
    _ = _user
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    cfg = configure_capture_filter(data)
    return {"message": "流量捕获配置已更新", "config": cfg.to_dict()}


@router.get("/config")
async def get_capture_config_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取当前生效的流量捕获配置。"""
    _ = _user
    return get_capture_filter_config().to_dict()


@router.post("/intercept")
async def intercept_traffic_endpoint(
    body: IngestTrafficIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """由网关或 Sidecar 旁路提交单条流量进行多协议标准化解析与过滤捕获 (需工程师权限)。"""
    _ = _user
    item = capture_traffic_payload(
        protocol=body.protocol,
        method=body.method,
        path_or_endpoint=body.path_or_endpoint,
        headers=body.headers,
        query_params=body.query_params,
        request_body=body.request_body,
        response_status_code=body.response_status_code,
        response_body=body.response_body,
        duration_ms=body.duration_ms,
        client_ip=body.client_ip,
        tags=body.tags,
    )
    if item:
        return {"message": "流量已捕获入库", "captured": True, "item": item.to_dict()}
    return {"message": "流量未满足过滤/采样规则，已安全过滤丢弃", "captured": False, "item": None}


@router.post("/batch")
async def batch_intercept_traffic_endpoint(
    body: BatchIngestTrafficIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """批量提交旁路流量镜像记录 (需工程师权限)。"""
    _ = _user
    captured_items: list[dict[str, Any]] = []
    filtered_count = 0
    for b in body.items:
        it = capture_traffic_payload(
            protocol=b.protocol,
            method=b.method,
            path_or_endpoint=b.path_or_endpoint,
            headers=b.headers,
            query_params=b.query_params,
            request_body=b.request_body,
            response_status_code=b.response_status_code,
            response_body=b.response_body,
            duration_ms=b.duration_ms,
            client_ip=b.client_ip,
            tags=b.tags,
        )
        if it:
            captured_items.append(it.to_dict())
        else:
            filtered_count += 1

    return {
        "message": f"批量解析完成：捕获 {len(captured_items)} 条，过滤 {filtered_count} 条",
        "total_submitted": len(body.items),
        "captured_count": len(captured_items),
        "filtered_count": filtered_count,
        "items": captured_items,
    }


@router.get("/records")
async def list_traffic_records_endpoint(
    protocol: str | None = Query(default=None, description="协议过滤: HTTP | GRPC | WEBSOCKET"),
    path_pattern: str | None = Query(default=None, description="路径正则或关键字匹配"),
    min_status: int | None = Query(default=None, ge=100, le=599, description="最低响应状态码"),
    max_status: int | None = Query(default=None, ge=100, le=599, description="最高响应状态码"),
    limit: int = Query(default=100, ge=1, le=1000, description="返回数量上限"),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """多维检索已捕获的流量记录列表。"""
    _ = _user
    records = list_captured_traffic(
        protocol=protocol,
        path_pattern=path_pattern,
        min_status=min_status,
        max_status=max_status,
        limit=limit,
    )
    return {"total": len(records), "records": [r.to_dict() for r in records]}


@router.get("/records/{traffic_id}")
async def get_traffic_record_endpoint(
    traffic_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定捕获流量的完整请求头与负载明细。"""
    _ = _user
    rec = get_captured_traffic_by_id(traffic_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"流量记录不存在: {traffic_id}")
    return rec.to_dict()


@router.delete("/records")
async def clear_traffic_records_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空所有捕获流量记录 (需工程师权限)。"""
    _ = _user
    deleted_count = clear_captured_traffic()
    return {"message": f"已清空 {deleted_count} 条流量记录", "deleted_count": deleted_count}


@router.get("/metrics")
async def get_capture_metrics_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取流量网关实时拦截与捕获效能指标。"""
    _ = _user
    return get_capture_metrics()
