"""端到端测试自愈审计追踪与补丁应用流水线 REST API (T4.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.self_healing_audit_patch_pipeline import (
    clear_pipeline_store,
    execute_self_healing_pipeline,
    get_pipeline_report,
    list_pipeline_reports,
    rollback_healed_patch,
)

router = APIRouter(prefix="/healing/pipeline", tags=["端到端测试自愈流水线 (T4.3)"])


class ExecuteHealingPipelineIn(BaseModel):
    case_id: str = Field(..., description="待自愈测试用例 ID")
    case_name: str = Field(..., description="测试用例名称")
    console_logs: str = Field(default="", description="测试控制台异常日志/堆栈")
    http_status_code: int | None = Field(default=None, description="接口响应状态码")
    http_response_payload: Any = Field(default=None, description="接口实际响应体")
    broken_locator: str = Field(default="", description="失效的 UI 定位符 (选填)")
    dom_candidates: list[dict[str, Any]] | None = Field(default=None, description="页面候选 DOM 节点列表")
    original_assertion: str = Field(default="", description="失效的 API 原断言表达式 (选填)")
    auto_apply: bool = Field(default=True, description="沙箱试跑通过后是否自动持久化应用补丁")


@router.post("/execute")
async def execute_pipeline_endpoint(
    body: ExecuteHealingPipelineIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """触发四阶段测试自愈流水线 (根因分析 → 补丁合成 → 沙箱试跑验证 → 防篡改审计与应用)。"""
    _ = _user
    report = execute_self_healing_pipeline(
        case_id=body.case_id,
        case_name=body.case_name,
        console_logs=body.console_logs,
        http_status_code=body.http_status_code,
        http_response_payload=body.http_response_payload,
        broken_locator=body.broken_locator,
        dom_candidates=body.dom_candidates,
        original_assertion=body.original_assertion,
        auto_apply=body.auto_apply,
    )
    return {"message": "端到端测试自愈流水线执行完成", "report": report.to_dict()}


@router.post("/{pipeline_id}/rollback")
async def rollback_pipeline_endpoint(
    pipeline_id: str,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """一键原子级回滚已应用的自愈补丁，恢复原始用例版本 (需工程师权限)。"""
    _ = _user
    ok = rollback_healed_patch(pipeline_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到可回滚的生效补丁流水线: {pipeline_id}",
        )
    return {"message": "自愈补丁已安全原子回滚", "pipeline_id": pipeline_id}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    applied_only: bool = False,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询测试自愈流水线执行报告列表。"""
    _ = _user
    reports = list_pipeline_reports(limit=limit, applied_only=applied_only)
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/reports/{pipeline_id}")
async def get_report_endpoint(
    pipeline_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定自愈流水线报告与补丁 Diff 详情。"""
    _ = _user
    report = get_pipeline_report(pipeline_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到自愈流水线报告: {pipeline_id}",
        )
    return report.to_dict()


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空自愈流水线报告缓存 (需工程师权限)。"""
    _ = _user
    c = clear_pipeline_store()
    return {"message": f"已清空 {c} 条自愈流水线记录", "cleared_count": c}
