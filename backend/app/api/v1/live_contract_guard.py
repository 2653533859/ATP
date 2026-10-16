"""实时生产流量契约动态逆向提取推导 REST API (T3.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.live_contract_schema_extractor import (
    batch_extract_contracts_from_traffic,
    clear_extracted_contracts,
    extract_contract_from_traffic,
    get_contract_by_endpoint,
    get_extracted_contract,
    list_extracted_contracts,
)
from app.services.traffic_capture_gateway import list_captured_traffic

router = APIRouter(prefix="/contract-guard/extract", tags=["实时接口契约逆向推导器 (T3.1)"])


class ExtractSingleContractIn(BaseModel):
    endpoint: str = Field(..., description="接口端点标识 (如 POST /api/v1/orders/checkout)")
    traffic_samples: list[dict[str, Any]] = Field(..., min_length=1, description="该端点的真实调用流量样本列表")
    protocol: str = Field(default="HTTP", description="协议: HTTP | GRPC")


class ExtractBatchContractIn(BaseModel):
    traffic_records: list[dict[str, Any]] | None = Field(
        default=None, description="待提取契约的流量列表。若留空则自动从系统已捕获的流量库中提取"
    )
    limit_captured: int = Field(default=100, ge=1, le=1000, description="从系统捕获库提取的最大流量条数")


@router.post("/single")
async def extract_single_contract_endpoint(
    body: ExtractSingleContractIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """从单接口的多条调用样本中逆向提取推导 OpenAPI 3.0 与 Protobuf Schema (需工程师权限)。"""
    _ = _user
    contract = extract_contract_from_traffic(
        endpoint=body.endpoint,
        traffic_samples=body.traffic_samples,
        protocol=body.protocol,
    )
    return {"message": "接口契约逆向推导完成", "contract": contract.to_dict()}


@router.post("/batch")
async def extract_batch_contracts_endpoint(
    body: ExtractBatchContractIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """批量对海量生产流量执行按接口聚合逆向推导契约 (需工程师权限)。"""
    _ = _user
    records = body.traffic_records
    if records is None:
        captured = list_captured_traffic(limit=body.limit_captured)
        records = [c.to_dict() for c in captured]

    report = batch_extract_contracts_from_traffic(records)
    return {
        "message": f"批量契约逆向提取完成：从 {report.total_traffic_analyzed} 条流量中提炼出 {report.contracts_extracted_count} 个接口契约",
        "report": report.to_dict(),
    }


@router.get("/contracts")
async def list_contracts_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史已逆向提取的契约列表。"""
    _ = _user
    contracts = list_extracted_contracts()
    return {"total": len(contracts), "contracts": [c.to_dict() for c in contracts]}


@router.get("/contracts/by-endpoint")
async def get_contract_by_endpoint_endpoint(
    endpoint: str = Query(..., description="接口端点 (如 POST /api/v1/orders)"),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """根据接口端点获取最新逆向推导的契约详情。"""
    _ = _user
    contract = get_contract_by_endpoint(endpoint)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到该端点的契约: {endpoint}")
    return contract.to_dict()


@router.get("/contracts/{contract_id}")
async def get_contract_endpoint(
    contract_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定逆向推导契约的完整 OpenAPI Schema 与 Protobuf 规范。"""
    _ = _user
    contract = get_extracted_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"契约不存在: {contract_id}")
    return contract.to_dict()


@router.delete("/contracts")
async def clear_contracts_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空已提取的契约缓存 (需工程师权限)。"""
    _ = _user
    count = clear_extracted_contracts()
    return {"message": f"已清空 {count} 条契约记录", "deleted_count": count}
