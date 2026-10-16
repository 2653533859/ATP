"""接口黄金响应基线版本化管理与回归偏离判定 REST API (T2.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.golden_response_baseline_manager import (
    batch_verify_against_baselines,
    clear_golden_baselines,
    create_or_update_golden_baseline,
    delete_golden_baseline,
    get_batch_verification_report,
    get_golden_baseline,
    list_batch_verification_reports,
    list_golden_baselines,
    verify_response_against_baseline,
)

router = APIRouter(prefix="/traffic/golden-baselines", tags=["接口黄金响应基线卫士 (T2.3)"])


class CreateGoldenBaselineIn(BaseModel):
    endpoint: str = Field(..., description="接口方法与端点 (如 POST /api/v1/orders/checkout)")
    golden_response_body: Any = Field(..., description="官方认证的黄金响应体 (JSON 或文本)")
    golden_response_status: int = Field(default=200, description="黄金响应状态码")
    golden_request_body: str = Field(default="", description="触发该黄金响应的典型请求体")
    protocol: str = Field(default="HTTP", description="协议: HTTP | GRPC")
    version_tag: str = Field(default="v1.0-prod-gold", description="版本化快照标签 (如 v1.0-prod-gold)")
    description: str = Field(default="", description="基线快照描述")
    tolerance_threshold_pct: float = Field(default=95.0, ge=50.0, le=100.0, description="最低相似度容差阈值 (%)")
    is_active: bool = Field(default=True, description="是否处于激活状态")
    baseline_id: str | None = Field(default=None, description="可选指定基线 ID，用于覆盖更新")
    tags: dict[str, str] = Field(default_factory=dict, description="业务标签")


class VerifySingleIn(BaseModel):
    baseline_id: str = Field(..., description="比对的黄金基线 ID")
    actual_response_body: Any = Field(..., description="当前重构版本或回放实测响应体")
    actual_status_code: int = Field(default=200, description="当前实测响应状态码")
    custom_tolerance_pct: float | None = Field(default=None, ge=50.0, le=100.0, description="覆盖默认容差阈值")


class BatchVerifyIn(BaseModel):
    items: list[dict[str, Any]] = Field(..., min_length=1, description="批量实测响应列表")
    default_version_tag: str | None = Field(default=None, description="默认比对的版本基线标签")


@router.post("")
async def create_or_update_baseline_endpoint(
    body: CreateGoldenBaselineIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """录入或更新官方接口黄金响应基线快照 (需工程师权限)。"""
    _ = _user
    item = create_or_update_golden_baseline(
        endpoint=body.endpoint,
        golden_response_body=body.golden_response_body,
        golden_response_status=body.golden_response_status,
        golden_request_body=body.golden_request_body,
        protocol=body.protocol,
        version_tag=body.version_tag,
        description=body.description,
        tolerance_threshold_pct=body.tolerance_threshold_pct,
        is_active=body.is_active,
        baseline_id=body.baseline_id,
        tags=body.tags,
    )
    return {"message": "黄金响应基线已保存", "baseline": item.to_dict()}


@router.get("")
async def list_baselines_endpoint(
    endpoint: str | None = Query(default=None, description="接口端点搜索"),
    version_tag: str | None = Query(default=None, description="版本标签"),
    is_active: bool | None = Query(default=None, description="是否激活"),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """多维检索黄金响应基线列表。"""
    _ = _user
    items = list_golden_baselines(endpoint_pattern=endpoint, version_tag=version_tag, is_active=is_active)
    return {"total": len(items), "baselines": [b.to_dict() for b in items]}


@router.get("/{baseline_id}")
async def get_baseline_endpoint(
    baseline_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定黄金响应基线详情。"""
    _ = _user
    item = get_golden_baseline(baseline_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"黄金基线不存在: {baseline_id}")
    return item.to_dict()


@router.delete("/{baseline_id}")
async def delete_baseline_endpoint(
    baseline_id: str,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """删除指定黄金响应基线 (需工程师权限)。"""
    _ = _user
    ok = delete_golden_baseline(baseline_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"黄金基线未找到: {baseline_id}")
    return {"message": "黄金响应基线已删除", "baseline_id": baseline_id}


@router.post("/verify")
async def verify_single_endpoint(
    body: VerifySingleIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对比实测响应与黄金基线，执行字段级去噪精确差分并输出回归偏离评级。"""
    _ = _user
    try:
        res = verify_response_against_baseline(
            baseline_id_or_item=body.baseline_id,
            actual_response_body=body.actual_response_body,
            actual_status_code=body.actual_status_code,
            custom_tolerance_pct=body.custom_tolerance_pct,
        )
        return {"message": "黄金基线回归对齐校验完成", "result": res.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/batch-verify")
async def batch_verify_endpoint(
    body: BatchVerifyIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """批量校验一组实测/影子回放响应与黄金基线的偏离度。"""
    _ = _user
    report = batch_verify_against_baselines(
        actual_items=body.items,
        default_version_tag=body.default_version_tag,
    )
    return {
        "message": f"批量回归校验完成：总计 {report.total_verified} 条，通过率 {report.pass_rate_pct}%，偏离报警 {report.drifted_count} 处",
        "report": report.to_dict(),
    }


@router.get("/batch-reports")
async def list_batch_reports_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史黄金基线批量回归验证报告列表。"""
    _ = _user
    reports = list_batch_verification_reports()
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/batch-reports/{batch_id}")
async def get_batch_report_endpoint(
    batch_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定批次黄金基线回归偏离报告详情。"""
    _ = _user
    report = get_batch_verification_report(batch_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"批量校验报告不存在: {batch_id}")
    return report.to_dict()
