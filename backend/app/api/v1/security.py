"""Security, PII redaction, and compliance governance API (Phase 4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin, require_engineer
from app.core.database import get_db
from app.models.user import User, UserRole
from app.services.api_key_governance import (
    export_api_key_audit_report,
    generate_api_key,
    revoke_api_key,
)
from app.services.disaster_recovery import (
    create_disaster_recovery_snapshot,
    perform_disaster_recovery_drill,
)
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


class ApiKeyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    project_id: int | None = None
    environment_id: int | None = None
    role: str = "engineer"
    ip_allowlist: list[str] = Field(default_factory=list)
    expires_in_days: int | None = 90


class ApiKeyCreateOut(BaseModel):
    id: int
    name: str
    raw_key: str
    key_prefix: str
    project_id: int | None
    role: str
    ip_allowlist: list[str]
    expires_at: str | None
    is_active: bool


@router.post("/api-keys", response_model=ApiKeyCreateOut, status_code=status.HTTP_201_CREATED)
async def create_api_key_endpoint(
    body: ApiKeyCreateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    """生成全新的 API Key，明文令牌仅在创建响应中返回一次，后台仅存储 SHA-256 安全哈希。"""
    api_key, raw_token = await generate_api_key(
        db,
        name=body.name,
        user_id=current_user.id,
        project_id=body.project_id,
        environment_id=body.environment_id,
        role=body.role,
        ip_allowlist=body.ip_allowlist,
        expires_in_days=body.expires_in_days,
    )
    await db.commit()
    return ApiKeyCreateOut(
        id=api_key.id,
        name=api_key.name,
        raw_key=raw_token,
        key_prefix=api_key.key_prefix,
        project_id=api_key.project_id,
        role=api_key.role,
        ip_allowlist=api_key.ip_allowlist or [],
        expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
        is_active=api_key.is_active,
    )


@router.get("/api-keys/audit-report")
async def get_api_key_audit_report_endpoint(
    project_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_engineer),
):
    """导出格式化的 API Key / 租户令牌安全合规审计与使用统计报表。"""
    return await export_api_key_audit_report(db, project_id=project_id)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key_endpoint(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    """废除或下线指定的 API Key。"""
    is_admin = current_user.role == UserRole.admin
    revoked = await revoke_api_key(db, key_id, current_user.id, is_admin=is_admin)
    if not revoked:
        raise HTTPException(status_code=404, detail="API Key 不存在或无权限操作")
    await db.commit()
    return None


class DrSnapshotCreateIn(BaseModel):
    snapshot_tag: str = "manual"


@router.post("/disaster-recovery/snapshot")
async def create_dr_snapshot_endpoint(
    body: DrSnapshotCreateIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """创建平台全量核心资产灾备快照（包含数据库表统计、SHA-256 校验清单与元数据）。"""
    manifest, _archive_bytes = await create_disaster_recovery_snapshot(
        db,
        snapshot_tag=body.snapshot_tag,
    )
    return manifest


@router.post("/disaster-recovery/drill")
async def perform_dr_drill_endpoint(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """执行自动化灾备恢复演练（测试解压、SHA-256 完整性核对与关键表数量核对）。"""
    manifest, archive_bytes = await create_disaster_recovery_snapshot(db, snapshot_tag="drill")
    report = perform_disaster_recovery_drill(
        archive_bytes,
        expected_table_counts=manifest.get("table_counts"),
    )
    return report
