"""Tamper-Evident Audit Log Hash Chain & Compliance Report API Router (T4.3)."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.services.audit_tamper_evident_chain import (
    build_audit_hash_chain,
    generate_compliance_audit_report,
    verify_audit_chain_integrity,
)

router = APIRouter(prefix="/audit/chain", tags=["企业级审计日志防篡改哈希链"])


class GenerateComplianceReportIn(BaseModel):
    organization: str = Field(default="ATP Enterprise QA & Security Org")
    limit: int = Field(default=100, ge=1, le=1000)
    project_id: int | None = None
    custom_records: list[dict[str, Any]] | None = None


@router.post("/verify")
async def verify_audit_chain_endpoint(
    limit: int = Query(default=100, ge=1, le=1000),
    project_id: int | None = Query(default=None),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """自检当前审计日志哈希链完整性 (需管理员权限)。"""
    _ = _admin
    stmt = select(AuditLog)
    if project_id is not None:
        stmt = stmt.where(AuditLog.project_id == project_id)
    stmt = stmt.order_by(AuditLog.id.asc()).limit(limit)

    res = await db.execute(stmt)
    logs = res.scalars().all()

    log_dicts = [
        {
            "id": l.id,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "user_id": l.user_id,
            "username": l.username,
            "detail": l.detail,
            "ip_address": l.ip_address,
            "project_id": l.project_id,
            "created_at": l.created_at,
        }
        for l in logs
    ]

    blocks = build_audit_hash_chain(log_dicts)
    integrity = verify_audit_chain_integrity(blocks)
    return integrity


@router.post("/report")
async def generate_compliance_report_endpoint(
    body: GenerateComplianceReportIn,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """导出附带数字签名防伪印章的企业合规审计证明报表 (需管理员权限)。"""
    _ = _admin
    if body.custom_records is not None:
        log_dicts = body.custom_records
    else:
        stmt = select(AuditLog)
        if body.project_id is not None:
            stmt = stmt.where(AuditLog.project_id == body.project_id)
        stmt = stmt.order_by(AuditLog.id.asc()).limit(body.limit)

        res = await db.execute(stmt)
        logs = res.scalars().all()
        log_dicts = [
            {
                "id": l.id,
                "action": l.action,
                "resource_type": l.resource_type,
                "resource_id": l.resource_id,
                "user_id": l.user_id,
                "username": l.username,
                "detail": l.detail,
                "ip_address": l.ip_address,
                "project_id": l.project_id,
                "created_at": l.created_at,
            }
            for l in logs
        ]

    report = generate_compliance_audit_report(
        log_records=log_dicts,
        organization=body.organization,
    )
    return report
