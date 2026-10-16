"""基础设施即代码 (IaC) 与网络策略安全合规巡检 REST API (T2.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.iac_network_policy_compliance_scanner import (
    COMPLIANCE_RULES_METADATA,
    clear_compliance_store,
    get_compliance_report,
    list_compliance_reports,
    scan_iac_manifests,
)

router = APIRouter(prefix="/env-drift/iac-compliance", tags=["IaC 基础设施合规巡检 (T2.3)"])


class ScanManifestsIn(BaseModel):
    target_name: str = Field(default="k8s-workloads", description="扫描目标名称 (如 release-manifests)")
    manifests: list[dict[str, Any]] = Field(..., min_length=1, description="Kubernetes / Docker Compose 清单对象列表")


@router.post("/scan")
async def scan_manifests_endpoint(
    body: ScanManifestsIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对传入的 IaC 清单执行合规检查并输出安全评分与阻断裁决。"""
    _ = _user
    report = scan_iac_manifests(
        target_name=body.target_name,
        manifests=body.manifests,
    )
    return {"message": "IaC 与网络策略合规扫描完成", "report": report.to_dict()}


@router.get("/rules")
async def list_rules_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询平台内置的 IaC 与网络策略合规基线规则。"""
    _ = _user
    return {"total": len(COMPLIANCE_RULES_METADATA), "rules": COMPLIANCE_RULES_METADATA}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史合规审计报告列表。"""
    _ = _user
    reports = list_compliance_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单次合规扫描报告详情。"""
    _ = _user
    report = get_compliance_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空合规审计报告历史（需工程师权限）。"""
    _ = _user
    clear_compliance_store()
    return {"message": "已清空所有 IaC 合规扫描报告"}
