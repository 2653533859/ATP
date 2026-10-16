"""前端运行时长任务与主线程掉帧卡顿诊断 REST API (T4.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.client_long_task_jank_profiler import (
    clear_long_task_store,
    diagnose_long_tasks_and_jank,
    get_long_task_report,
    list_long_task_reports,
)

router = APIRouter(prefix="/client-perf/long-tasks", tags=["长任务与掉帧卡顿诊断 (T4.1)"])


class TaskEventIn(BaseModel):
    duration_ms: float = Field(..., description="任务执行耗时 ms")
    culprit_symbol: str | None = Field(default=None, description="触发函数名或脚本标识")
    call_stack: list[str] = Field(default_factory=list, description="执行调用栈")


class DiagnoseLongTasksIn(BaseModel):
    page_name: str = Field(default="case_list_view", description="被采样页面或组件名称")
    task_events: list[TaskEventIn] = Field(..., min_length=1, description="主线程任务执行事件批次")
    sampling_duration_ms: float = Field(default=5000.0, description="采样时间窗口大小 ms")


@router.post("/profile")
async def profile_long_tasks_endpoint(
    body: DiagnoseLongTasksIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """全息分析客户端长任务采样事件，量化 TBT、卡顿掉帧率与优化建议。"""
    _ = _user
    events_dicts = [e.model_dump() for e in body.task_events]
    report = diagnose_long_tasks_and_jank(
        page_name=body.page_name,
        task_events=events_dicts,
        sampling_duration_ms=body.sampling_duration_ms,
    )
    return {"message": "长任务与掉帧卡顿诊断完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史长任务诊断报告列表。"""
    _ = _user
    reports = list_long_task_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次长任务诊断报告详情。"""
    _ = _user
    report = get_long_task_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空长任务诊断报告仓库 (需工程师权限)。"""
    _ = _user
    clear_long_task_store()
    return {"message": "已清空所有长任务诊断报告"}
