"""测试报告多模态聚合打包导出 API (D4.1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.report_bundler_exporter import (
    BundledReportPayload,
    ReportExportFormat,
    export_report_bundle,
    get_export_artifact,
    list_export_artifacts,
)

router = APIRouter(prefix="/reporting/exports", tags=["测试报告多模态聚合导出"])


class ExportReportBundleIn(BaseModel):
    run_id: int = Field(ge=1, description="测试批次 Run ID")
    title: str = Field(min_length=1, max_length=128, description="报告标题")
    project_name: str = Field(min_length=1, max_length=128, description="所属项目名称")
    environment_name: str = Field(min_length=1, max_length=64, description="执行环境标识")
    total_cases: int = Field(ge=0, description="用例总数")
    passed_cases: int = Field(ge=0, description="通过用例数")
    failed_cases: int = Field(ge=0, description="失败用例数")
    pass_rate_pct: float = Field(ge=0.0, le=100.0, description="通过率百分比")
    duration_sec: float = Field(ge=0.0, description="测试执行总耗时 (秒)")
    format: str = Field(
        default="multi_modal_zip", description="导出格式: html5 | excel_detailed | pdf_summary | multi_modal_zip"
    )
    executed_by: str = Field(default="ATP Automation System", description="执行人")
    cases_summary: list[dict[str, Any]] = Field(default_factory=list, description="用例执行简要清单")
    digital_seal_signature: str | None = Field(default=None, description="防伪数字印章签名")
    quality_score: float | None = Field(default=90.0, description="全生命周期质量综合健康分")
    healed_cases_count: int = Field(default=0, ge=0, description="AI 智能自愈用例数")
    perf_summary: dict[str, Any] | None = Field(default=None, description="多维性能指标摘要")


@router.post("/bundle")
async def export_report_bundle_endpoint(
    body: ExportReportBundleIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """多模态聚合打包导出测试执行报告与质检凭据 (需工程师权限)。"""
    _ = _user
    try:
        fmt_enum = ReportExportFormat(body.format.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的导出格式: {body.format}")

    payload = BundledReportPayload(
        run_id=body.run_id,
        title=body.title,
        project_name=body.project_name,
        environment_name=body.environment_name,
        total_cases=body.total_cases,
        passed_cases=body.passed_cases,
        failed_cases=body.failed_cases,
        pass_rate_pct=body.pass_rate_pct,
        duration_sec=body.duration_sec,
        executed_by=body.executed_by,
        cases_summary=body.cases_summary,
        digital_seal_signature=body.digital_seal_signature,
        quality_score=body.quality_score,
        healed_cases_count=body.healed_cases_count,
        perf_summary=body.perf_summary,
    )

    artifact = export_report_bundle(payload, export_format=fmt_enum)
    res = artifact.to_dict()
    res["download_url"] = f"/api/v1/reporting/exports/download/{artifact.bundle_id}"
    return {"message": "报告归档打包生成成功", "artifact": res}


@router.get("/download/{bundle_id}")
async def download_export_artifact_endpoint(
    bundle_id: str,
) -> Response:
    """直接流式下载已生成的测试报告与质检归档包。"""
    artifact = get_export_artifact(bundle_id)
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"导出归档包不存在: {bundle_id}")

    headers = {
        "Content-Disposition": f'attachment; filename="{artifact.filename}"',
        "Content-Length": str(artifact.file_size_bytes),
    }
    return Response(
        content=artifact.data_bytes,
        media_type=artifact.content_type,
        headers=headers,
    )


@router.get("/artifacts")
async def list_export_artifacts_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询平台当前已归档导出的全部报告列表。"""
    _ = _user
    artifacts = list_export_artifacts()
    return {"total": len(artifacts), "artifacts": [a.to_dict() for a in artifacts]}
