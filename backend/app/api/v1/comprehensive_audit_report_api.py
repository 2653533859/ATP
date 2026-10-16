"""端到端测试执行与质量合规全景审计报告 REST API (T4.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.comprehensive_test_audit_report_generator import (
    clear_audit_report_store,
    export_report_as_markdown,
    generate_comprehensive_audit_report,
    get_comprehensive_audit_report,
    list_comprehensive_audit_reports,
    verify_audit_report_integrity,
)

router = APIRouter(prefix="/gatekeeper/audit-report", tags=["全景质量审计报告 (T4.3)"])


class GenerateAuditReportIn(BaseModel):
    target_version: str = Field(default="v4.2.0", description="待发版目标版本")
    project_name: str = Field(default="ATP 自动化测试平台", description="项目名称")
    execution_data: dict[str, Any] | None = Field(default=None)
    health_data: dict[str, Any] | None = Field(default=None)
    drift_data: dict[str, Any] | None = Field(default=None)
    iac_data: dict[str, Any] | None = Field(default=None)
    fuzzing_data: dict[str, Any] | None = Field(default=None)
    gatekeeper_data: dict[str, Any] | None = Field(default=None)


class VerifyIntegrityIn(BaseModel):
    tampered_data: dict[str, Any] | None = Field(default=None, description="待校验的数据体（选填，为空则验证原始记录）")


@router.post("/generate")
async def generate_audit_report_endpoint(
    body: GenerateAuditReportIn,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """组装全维度质量合规数据，生成带 SHA-256 防篡改指纹的全景审计报告。"""
    report = generate_comprehensive_audit_report(
        target_version=body.target_version,
        project_name=body.project_name,
        generated_by=user.username or "quality_bot",
        execution_data=body.execution_data,
        health_data=body.health_data,
        drift_data=body.drift_data,
        iac_data=body.iac_data,
        fuzzing_data=body.fuzzing_data,
        gatekeeper_data=body.gatekeeper_data,
    )
    return {"message": "质量合规全景审计报告生成完成", "report": report.to_dict()}


@router.post("/{report_id}/verify")
async def verify_report_integrity_endpoint(
    report_id: str,
    body: VerifyIntegrityIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """校验指定审计报告的 SHA-256 存证指纹防篡改完整性。"""
    _ = _user
    res = verify_audit_report_integrity(report_id=report_id, tampered_data=body.tampered_data)
    return res


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史全景质量审计报告列表。"""
    _ = _user
    reports = list_comprehensive_audit_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单次审计报告详情。"""
    _ = _user
    report = get_comprehensive_audit_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.get("/reports/{report_id}/markdown")
async def export_markdown_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> Response:
    """导出标准 Markdown 格式交付物审阅文档。"""
    _ = _user
    report = get_comprehensive_audit_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    md_content = export_report_as_markdown(report_id)
    return Response(content=md_content, media_type="text/markdown")


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空所有全景审计报告（需工程师权限）。"""
    _ = _user
    clear_audit_report_store()
    return {"message": "已清空所有全景质量审计报告"}
