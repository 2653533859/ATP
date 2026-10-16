"""跨环境配置漂移自动探测与环境变量差分 REST API (T2.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.multi_env_config_drift_detector import (
    clear_config_drift_store,
    compare_environment_configs,
    get_config_drift_report,
    list_config_drift_reports,
    register_environment_config_snapshot,
)

router = APIRouter(prefix="/env-drift/config", tags=["跨环境配置漂移探测 (T2.1)"])


class RegisterSnapshotIn(BaseModel):
    env_name: str = Field(..., description="环境名称 (如 production, staging, testing, development)")
    service_name: str = Field(..., description="微服务名称 (如 order-service)")
    configs: dict[str, Any] = Field(..., description="微服务环境变量与配置项键值字典")


class CompareConfigsIn(BaseModel):
    service_name: str = Field(..., description="微服务名称")
    base_env: str = Field(default="production", description="基准对比环境 (默认生产环境)")
    target_env: str = Field(default="testing", description="目标检查环境 (默认测试环境)")
    base_configs: dict[str, Any] | None = Field(default=None, description="直接传入的基准环境配置字典（选填）")
    target_configs: dict[str, Any] | None = Field(default=None, description="直接传入的目标环境配置字典（选填）")


@router.post("/register-snapshot")
async def register_snapshot_endpoint(
    body: RegisterSnapshotIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """登记或上报环境微服务配置快照（需工程师权限）。"""
    _ = _user
    res = register_environment_config_snapshot(
        env_name=body.env_name,
        service_name=body.service_name,
        configs=body.configs,
    )
    return res


@router.post("/compare")
async def compare_configs_endpoint(
    body: CompareConfigsIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """比对基准环境与目标环境微服务配置，输出差异明细与一致性审计报告。"""
    _ = _user
    report = compare_environment_configs(
        base_env=body.base_env,
        target_env=body.target_env,
        service_name=body.service_name,
        base_configs=body.base_configs,
        target_configs=body.target_configs,
    )
    return {"message": "跨环境配置漂移比对完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史配置漂移审计报告列表。"""
    _ = _user
    reports = list_config_drift_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单次配置漂移报告详情。"""
    _ = _user
    report = get_config_drift_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空配置快照与历史审计报告（需工程师权限）。"""
    _ = _user
    clear_config_drift_store()
    return {"message": "已清空跨环境配置与历史报告"}
