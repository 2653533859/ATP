"""接口响应 Schema 动态漂移自适应修正与柔性断言 API (D2.2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User
from app.services.flexible_schema_assertion_engine import (
    AssertionToleranceMode,
    FlexibleAssertionConfig,
    assert_flexible_schema,
    list_assertion_audits,
)

router = APIRouter(prefix="/ai-healing/assertions", tags=["AI 接口 Schema 柔性断言与自适应漂移修正"])


class EvaluateSchemaAssertionIn(BaseModel):
    expected_schema: dict[str, Any] = Field(description="预期的 OpenAPI / JSON Schema 定义")
    actual_payload: Any = Field(description="接口实际返回的 JSON 数据载荷")
    mode: str = Field(default="compatible", description="容差模式: strict | compatible | lenient")
    ignore_extra_fields: bool = Field(default=True, description="是否容忍新增额外未声明字段")
    ignore_array_order: bool = Field(default=True, description="是否容忍数组内部元素顺序差异")
    allow_numeric_string_coercion: bool = Field(default=True, description="是否允许数字与字符串数字柔性强转")
    autofix_schema: bool = Field(default=True, description="是否推导自动修复版 Schema")


@router.post("/evaluate")
async def evaluate_flexible_assertion_endpoint(
    body: EvaluateSchemaAssertionIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对接口响应执行智能柔性契约断言，捕获良性/破坏性漂移并推导修复 Schema。"""
    _ = _user
    try:
        mode_enum = AssertionToleranceMode(body.mode.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的断言模式: {body.mode}")

    config = FlexibleAssertionConfig(
        mode=mode_enum,
        ignore_extra_fields=body.ignore_extra_fields,
        ignore_array_order=body.ignore_array_order,
        allow_numeric_string_coercion=body.allow_numeric_string_coercion,
        autofix_schema=body.autofix_schema,
    )

    res = assert_flexible_schema(
        expected_schema=body.expected_schema,
        actual_payload=body.actual_payload,
        config=config,
    )
    return res.to_dict()


@router.post("/autofix")
async def autofix_schema_endpoint(
    body: EvaluateSchemaAssertionIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """一键推导并生成可直接替代旧基线的新版自愈 Schema。"""
    _ = _user
    try:
        mode_enum = AssertionToleranceMode(body.mode.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的断言模式: {body.mode}")

    config = FlexibleAssertionConfig(
        mode=mode_enum,
        ignore_extra_fields=True,
        autofix_schema=True,
    )
    res = assert_flexible_schema(
        expected_schema=body.expected_schema,
        actual_payload=body.actual_payload,
        config=config,
    )

    if not res.passed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"存在破坏性缺失字段，无法安全自愈 Schema: {res.summary}",
        )

    return {
        "message": "Schema 自愈修正推导成功",
        "has_drifts": len(res.drifts) > 0,
        "drifts_count": len(res.drifts),
        "autofixed_schema": res.autofixed_schema or body.expected_schema,
    }


@router.get("/history")
async def list_assertion_audits_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史接口柔性断言与漂移评估台账。"""
    _ = _user
    history = list_assertion_audits()
    return {"total": len(history), "history": [h.to_dict() for h in history]}
