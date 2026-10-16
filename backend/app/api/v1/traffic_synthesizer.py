"""真实流量聚类归一与自动化测试用例智能生成 REST API (T1.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.traffic_capture_gateway import list_captured_traffic
from app.services.traffic_to_test_case_synthesizer import (
    cluster_traffic_records,
    get_synthesis_report,
    list_synthesis_reports,
    synthesize_test_cases_from_traffic,
)

router = APIRouter(prefix="/traffic/synthesize", tags=["真实流量用例智能合成器 (T1.3)"])


class SynthesizeFromTrafficIn(BaseModel):
    traffic_records: list[dict[str, Any]] | None = Field(
        default=None, description="待合成的镜像流量列表。若留空则自动从系统已捕获的流量库中提取"
    )
    auto_mask_first: bool = Field(default=True, description="是否在合成前自动执行 PII 数据脱敏清洗")
    max_dataset_rows_per_case: int = Field(default=10, ge=1, le=100, description="单条用例关联的参数化数据集行数上限")
    case_name_prefix: str = Field(default="AUTO_TRAFFIC", description="生成的测试用例命名前缀")
    protocol_filter: str | None = Field(default=None, description="从系统捕获库提取时的协议过滤: HTTP | GRPC")
    limit_captured: int = Field(default=100, ge=1, le=1000, description="从系统捕获库提取的最大流量条数")


class ClusterPreviewIn(BaseModel):
    traffic_records: list[dict[str, Any]] = Field(..., min_length=1, description="待聚类分析的流量记录列表")


@router.post("/run")
async def run_traffic_synthesis_endpoint(
    body: SynthesizeFromTrafficIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """根据真实流量请求聚类归一并智能合成标准化 ATP TestCase 与参数化数据集 (需工程师权限)。"""
    _ = _user
    records = body.traffic_records
    if records is None:
        # 从系统捕获库拉取
        captured = list_captured_traffic(protocol=body.protocol_filter, limit=body.limit_captured)
        records = [c.to_dict() for c in captured]

    report = synthesize_test_cases_from_traffic(
        records=records,
        auto_mask_first=body.auto_mask_first,
        max_dataset_rows_per_case=body.max_dataset_rows_per_case,
        case_name_prefix=body.case_name_prefix,
    )

    return {
        "message": f"成功评估 {report.total_traffic_evaluated} 条流量，生成 {report.synthesized_cases_count} 条测试用例，聚类去重率 {report.deduplication_ratio_pct}%",
        "report": report.to_dict(),
    }


@router.post("/cluster-preview")
async def cluster_preview_endpoint(
    body: ClusterPreviewIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """纯分析预览流量特征指纹聚类结果与去重分布。"""
    _ = _user
    clusters = cluster_traffic_records(body.traffic_records)
    total = len(body.traffic_records)
    dedup_ratio = max(0.0, (1.0 - (len(clusters) / total)) * 100.0) if total > 0 else 0.0

    return {
        "total_evaluated": total,
        "clusters_formed": len(clusters),
        "deduplication_ratio_pct": round(dedup_ratio, 2),
        "clusters": [c.to_dict() for c in clusters],
    }


@router.get("/reports")
async def list_reports_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史测试用例合成报告列表。"""
    _ = _user
    reports = list_synthesis_reports()
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定测试用例合成报告详情与生成的用例列表。"""
    _ = _user
    report = get_synthesis_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"用例合成报告不存在: {report_id}")
    return report.to_dict()
