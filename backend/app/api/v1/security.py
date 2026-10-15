"""Security, PII redaction, and compliance governance API (Phase 4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User
from app.services.sensitive_data_redactor import apply_pii_redaction_gateway

router = APIRouter(prefix="/security", tags=["安全与合规"])


class PiiMaskRequest(BaseModel):
    payload: Any = Field(..., description="待脱敏的文本字符串或 JSON 数据对象")
    custom_keywords: list[str] = Field(default_factory=list, description="自定义敏感词黑名单")


class PiiMaskResponse(BaseModel):
    redacted: Any
    success: bool = True


@router.post("/mask-pii", response_model=PiiMaskResponse)
async def mask_pii_endpoint(
    body: PiiMaskRequest,
    _user: User = Depends(get_current_user),
) -> PiiMaskResponse:
    """动态识别并脱敏文本或 JSON 数据中的手机号、身份证、银行卡、邮箱及凭证密钥。"""
    redacted_result = apply_pii_redaction_gateway(
        body.payload,
        custom_keywords=body.custom_keywords,
    )
    return PiiMaskResponse(redacted=redacted_result, success=True)
