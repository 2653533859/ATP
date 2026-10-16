"""响应体动态字段智能过滤与字段级精确差分比对 REST API (T2.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.traffic_capture_gateway import get_captured_traffic_by_id
from app.services.traffic_diff_comparator import (
    NoiseFilterConfig,
    clear_diff_reports,
    compare_traffic_responses,
    get_diff_report,
    list_diff_reports,
)

router = APIRouter(prefix="/traffic/diff", tags=["流量响应体智能差分比对器 (T2.2)"])


class NoiseFilterConfigIn(BaseModel):
    ignore_keys: list[str] | None = Field(default=None, description="自定义忽略的字段 Key 列表")
    ignore_paths: list[str] | None = Field(default=None, description="自定义忽略的 JSONPath 列表")
    auto_detect_uuid: bool = Field(default=True, description="是否自动忽略 UUID 格式动态噪声")
    auto_detect_timestamp: bool = Field(default=True, description="是否自动忽略时间戳/ISO时间动态噪声")


class CompareResponsesIn(BaseModel):
    baseline_response: Any = Field(..., description="基线响应体 (JSON 对象或文本字符串)")
    replayed_response: Any = Field(..., description="影子回放响应体 (JSON 对象或文本字符串)")
    baseline_status_code: int = Field(default=200, description="基线响应状态码")
    replayed_status_code: int = Field(default=200, description="影子回放响应状态码")
    noise_config: NoiseFilterConfigIn | None = Field(default=None, description="动态噪声过滤配置")


class CompareTrafficIdsIn(BaseModel):
    baseline_traffic_id: str = Field(..., description="基线捕获流量 ID")
    replayed_traffic_id: str = Field(..., description="回放捕获流量 ID")
    noise_config: NoiseFilterConfigIn | None = Field(default=None, description="动态噪声过滤配置")


def _build_noise_config(cfg_in: NoiseFilterConfigIn | None) -> NoiseFilterConfig:
    if not cfg_in:
        return NoiseFilterConfig()
    return NoiseFilterConfig(
        ignore_keys=cfg_in.ignore_keys or NoiseFilterConfig().ignore_keys,
        ignore_paths=cfg_in.ignore_paths or [],
        auto_detect_uuid=cfg_in.auto_detect_uuid,
        auto_detect_timestamp=cfg_in.auto_detect_timestamp,
    )


@router.post("/compare")
async def compare_responses_endpoint(
    body: CompareResponsesIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """执行两份响应体的字段级深度差分比对并自动滤除动态噪声。"""
    _ = _user
    cfg = _build_noise_config(body.noise_config)
    report = compare_traffic_responses(
        baseline_response_body=body.baseline_response,
        replayed_response_body=body.replayed_response,
        baseline_status_code=body.baseline_status_code,
        replayed_status_code=body.replayed_status_code,
        config=cfg,
    )
    return {"message": "响应体差分比对完成", "report": report.to_dict()}


@router.post("/compare-traffic-ids")
async def compare_by_traffic_ids_endpoint(
    body: CompareTrafficIdsIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """根据两个已捕获的流量记录 ID 提取响应体并执行差分比对。"""
    _ = _user
    base_item = get_captured_traffic_by_id(body.baseline_traffic_id)
    if not base_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"基线流量记录未找到: {body.baseline_traffic_id}"
        )

    repl_item = get_captured_traffic_by_id(body.replayed_traffic_id)
    if not repl_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"回放流量记录未找到: {body.replayed_traffic_id}"
        )

    cfg = _build_noise_config(body.noise_config)
    report = compare_traffic_responses(
        baseline_response_body=base_item.response_body,
        replayed_response_body=repl_item.response_body,
        baseline_status_code=base_item.response_status_code,
        replayed_status_code=repl_item.response_status_code,
        config=cfg,
    )
    return {"message": "流量记录差分比对完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史响应差分比对报告列表。"""
    _ = _user
    reports = list_diff_reports()
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定响应差分比对报告详情。"""
    _ = _user
    report = get_diff_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"差分报告不存在: {report_id}")
    return report.to_dict()


@router.get("/noise-rules/defaults")
async def get_default_noise_rules_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取系统默认动态噪声过滤配置。"""
    _ = _user
    return NoiseFilterConfig().to_dict()


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空差分比对报告缓存 (需工程师权限)。"""
    _ = _user
    count = clear_diff_reports()
    return {"message": f"已清空 {count} 条差分报告", "deleted_count": count}
