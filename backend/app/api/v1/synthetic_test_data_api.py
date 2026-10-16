"""生产级测试合成数据生成器 REST API (T3.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.synthetic_test_data_generator import (
    clear_synthetic_data_store,
    generate_synthetic_dataset,
    get_synthetic_dataset_batch,
    list_synthetic_dataset_batches,
)

router = APIRouter(prefix="/llm-testing/synthetic-data", tags=["生产级测试合成数据 (T3.2)"])


class FieldRuleIn(BaseModel):
    field_name: str = Field(..., description="字段名称")
    data_type: str = Field(
        default="string", description="类型 (string, integer, float, boolean, email, phone, id_card, enum)"
    )
    min_value: float | None = Field(default=None)
    max_value: float | None = Field(default=None)
    min_length: int | None = Field(default=None)
    max_length: int | None = Field(default=None)
    enum_values: list[str] = Field(default_factory=list)
    nullable: bool = Field(default=False)


class GenerateDatasetIn(BaseModel):
    dataset_name: str = Field(default="order_checkout_dataset", description="数据集批次标识")
    rules: list[FieldRuleIn] = Field(..., min_length=1, description="字段级业务约束规则列表")
    row_count: int = Field(default=10, ge=1, le=500, description="需要合成的数据行数 (1~500)")


@router.post("/generate")
async def generate_dataset_endpoint(
    body: GenerateDatasetIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """基于业务字段约束合成正向、边界与负向测试数据包。"""
    _ = _user
    rules_dicts = [r.model_dump() for r in body.rules]
    batch = generate_synthetic_dataset(
        dataset_name=body.dataset_name,
        rules=rules_dicts,
        row_count=body.row_count,
    )
    return {"message": "生产级测试数据集合成完成", "batch": batch.to_dict()}


@router.get("/batches")
async def list_batches_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史合成数据批次列表。"""
    _ = _user
    batches = list_synthetic_dataset_batches(limit=limit)
    return {"total": len(batches), "batches": batches}


@router.get("/batches/{batch_id}")
async def get_batch_endpoint(
    batch_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单次合成数据批次详情与全部数据行。"""
    _ = _user
    batch = get_synthetic_dataset_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"数据批次 [{batch_id}] 不存在")
    return {"batch": batch.to_dict()}


@router.delete("/batches")
async def clear_batches_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空所有合成数据批次（需工程师权限）。"""
    _ = _user
    clear_synthetic_data_store()
    return {"message": "已清空所有合成测试数据集"}
