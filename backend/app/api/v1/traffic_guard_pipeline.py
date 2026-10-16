"""生产流量录制回放与契约防线端到端流水线 OpenAPI (T4.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.traffic_guard_pipeline_api import (
    clear_pipeline_reports,
    execute_traffic_guard_pipeline,
    get_pipeline_report,
    list_pipeline_reports,
)

router = APIRouter(prefix="/traffic-guard/pipeline", tags=["生产流量防线端到端编排流水线 (T4.3)"])


class RunTrafficGuardPipelineIn(BaseModel):
    endpoint: str = Field(default="POST /api/v1/orders/checkout", description="被测接口端点与方法")
    raw_traffic_samples: list[dict[str, Any]] | None = Field(
        default=None, description="自定义输入的抓包流量样本 (留空使用典型样例)"
    )
    design_contract: dict[str, Any] | None = Field(default=None, description="设计期期望契约 (留空自动推导)")
    target_base_url: str = Field(default="http://127.0.0.1:8000", description="影子回放服务 Base URL")
    pipeline_name: str = Field(default="ATP-Traffic-Guard-Pipeline", description="流水线名称")
    write_guard_mode: str = Field(
        default="BLOCK_WRITES", description="写操作防护模式: BLOCK_WRITES | DRY_RUN | ALLOW_ALL"
    )
    tolerance_threshold_pct: float = Field(default=95.0, ge=50.0, le=100.0, description="黄金基线相似度容差阈值 (%)")
    simulate_chaos_resilience: bool = Field(default=True, description="是否编排执行微服务故障注入与 RTO 韧性验证")


@router.post("/run")
async def run_pipeline_endpoint(
    body: RunTrafficGuardPipelineIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """一键触发生产流量防线端到端四阶段检查点流水线执行 (需工程师权限)。"""
    _ = _user
    report = execute_traffic_guard_pipeline(
        endpoint=body.endpoint,
        raw_traffic_samples=body.raw_traffic_samples,
        design_contract=body.design_contract,
        target_base_url=body.target_base_url,
        pipeline_name=body.pipeline_name,
        write_guard_mode=body.write_guard_mode,
        tolerance_threshold_pct=body.tolerance_threshold_pct,
        simulate_chaos_resilience=body.simulate_chaos_resilience,
    )
    return {
        "message": f"生产流量防线流水线执行完毕，Exit Code: {report.exit_code} ({report.overall_status.value})",
        "report": report.to_dict(),
    }


@router.get("/reports")
async def list_reports_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史流量防线流水线执行报告列表。"""
    _ = _user
    reports = list_pipeline_reports()
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/reports/{pipeline_run_id}")
async def get_report_endpoint(
    pipeline_run_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定流量防线流水线执行报告详情与 ANSI 控制台日志。"""
    _ = _user
    report = get_pipeline_report(pipeline_run_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"流水线报告不存在: {pipeline_run_id}")
    return report.to_dict()


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空历史流水线执行报告缓存 (需工程师权限)。"""
    _ = _user
    count = clear_pipeline_reports()
    return {"message": f"已清空 {count} 条流水线报告记录", "deleted_count": count}
