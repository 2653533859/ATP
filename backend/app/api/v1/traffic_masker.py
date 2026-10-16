"""生产敏感数据自适应规则脱敏 REST API (T1.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.traffic_data_masker import (
    batch_mask_traffic_items,
    get_active_masking_rules,
    mask_captured_traffic_item,
    mask_payload_recursively,
    mask_text_content,
    reset_masking_rules,
    update_masking_rules,
)

router = APIRouter(prefix="/traffic/mask", tags=["生产流量敏感数据脱敏器 (T1.2)"])


class MaskTextIn(BaseModel):
    text: str = Field(..., description="待脱敏的文本字符串")
    custom_keywords: list[str] | None = Field(default=None, description="自定义黑名单关键词")


class MaskPayloadIn(BaseModel):
    payload: Any = Field(..., description="待脱敏的 JSON 对象或数据结构")
    custom_keywords: list[str] | None = Field(default=None, description="自定义黑名单关键词")


class MaskTrafficItemIn(BaseModel):
    traffic_item: dict[str, Any] = Field(..., description="捕获的原始流量对象")
    custom_keywords: list[str] | None = Field(default=None, description="自定义黑名单关键词")


class BatchMaskTrafficIn(BaseModel):
    items: list[dict[str, Any]] = Field(..., min_length=1, description="批量捕获流量列表")
    custom_keywords: list[str] | None = Field(default=None, description="自定义黑名单关键词")


class UpdateRulesIn(BaseModel):
    rules: list[dict[str, Any]] = Field(..., min_length=1, description="脱敏规则配置列表")


@router.get("/rules")
async def get_rules_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取当前生效的敏感数据脱敏规则列表。"""
    _ = _user
    rules = get_active_masking_rules()
    return {"total": len(rules), "rules": [r.to_dict() for r in rules]}


@router.put("/rules")
async def update_rules_endpoint(
    body: UpdateRulesIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """更新脱敏规则配置 (需工程师权限)。"""
    _ = _user
    updated = update_masking_rules(body.rules)
    return {"message": f"成功更新 {len(updated)} 条脱敏规则", "rules": [r.to_dict() for r in updated]}


@router.post("/rules/reset")
async def reset_rules_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """重置脱敏规则为系统出厂默认值 (需工程师权限)。"""
    _ = _user
    rules = reset_masking_rules()
    return {"message": "已重置为系统出厂脱敏规则", "rules": [r.to_dict() for r in rules]}


@router.post("/text")
async def mask_text_endpoint(
    body: MaskTextIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对单段文本执行正则 PII 扫描脱敏。"""
    _ = _user
    masked = mask_text_content(body.text, custom_keywords=body.custom_keywords)
    return {"original": body.text, "masked": masked}


@router.post("/payload")
async def mask_payload_endpoint(
    body: MaskPayloadIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对任意嵌套 JSON Payload 对象递归清洗脱敏。"""
    _ = _user
    masked = mask_payload_recursively(body.payload, custom_keywords=body.custom_keywords)
    return {"masked_payload": masked}


@router.post("/item")
async def mask_traffic_item_endpoint(
    body: MaskTrafficItemIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """对单条旁路抓包流量条目进行全局脱敏清洗 (需工程师权限)。"""
    _ = _user
    masked_item = mask_captured_traffic_item(body.traffic_item, custom_keywords=body.custom_keywords)
    return {"message": "流量条目脱敏完成", "item": masked_item}


@router.post("/batch")
async def batch_mask_traffic_endpoint(
    body: BatchMaskTrafficIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """批量清洗并脱敏流量条目列表 (需工程师权限)。"""
    _ = _user
    masked_items = batch_mask_traffic_items(body.items, custom_keywords=body.custom_keywords)
    return {
        "message": f"批量脱敏完成：共处理 {len(masked_items)} 条流量",
        "total": len(masked_items),
        "items": masked_items,
    }
