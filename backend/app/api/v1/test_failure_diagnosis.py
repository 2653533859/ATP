"""多模态测试失败根因推导 REST API (T3.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.test_failure_root_cause_reasoner import (
    analyze_test_failure_root_cause,
    batch_analyze_failures,
    clear_root_cause_store,
    get_root_cause_report,
    list_root_cause_reports,
)

router = APIRouter(prefix="/diagnosis/root-cause", tags=["多模态测试失败根因推导 (T3.1)"])


class AnalyzeFailureIn(BaseModel):
    case_id: str = Field(..., description="测试用例 ID")
    case_name: str = Field(..., description="测试用例名称")
    console_logs: str = Field(default="", description="测试运行控制台日志或异常堆栈文本")
    http_status_code: int | None = Field(default=None, description="HTTP 响应状态码")
    http_response_body: str = Field(default="", description="HTTP 错误响应报文")
    spans: list[dict[str, Any]] | None = Field(default=None, description="关联的分布式 Span 链路数据")
    env_factors: dict[str, Any] | None = Field(default=None, description="系统环境与负载参数")


class BatchAnalyzeIn(BaseModel):
    failures: list[dict[str, Any]] = Field(..., min_length=1, description="失败用例多模态数据列表")


@router.post("/analyze")
async def analyze_failure_endpoint(
    body: AnalyzeFailureIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """融合控制台日志、HTTP 报文、分布式 Span 智能推导单用例失败根因。"""
    _ = _user
    report = analyze_test_failure_root_cause(
        case_id=body.case_id,
        case_name=body.case_name,
        console_logs=body.console_logs,
        http_status_code=body.http_status_code,
        http_response_body=body.http_response_body,
        spans=body.spans,
        env_factors=body.env_factors,
    )
    return {"message": "测试失败根因推导完成", "report": report.to_dict()}


@router.post("/batch-analyze")
async def batch_analyze_endpoint(
    body: BatchAnalyzeIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """批量对多个失败用例执行多模态根因推导与因果链提取。"""
    _ = _user
    reports = batch_analyze_failures(body.failures)
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    category: str | None = None,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史根因推导诊断报告列表。"""
    _ = _user
    reports = list_root_cause_reports(limit=limit, category=category)
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/reports/{diagnosis_id}")
async def get_report_endpoint(
    diagnosis_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定测试失败根因报告详情。"""
    _ = _user
    report = get_root_cause_report(diagnosis_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到该根因诊断报告: {diagnosis_id}",
        )
    return report.to_dict()


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空根因诊断报告缓存 (需工程师权限)。"""
    _ = _user
    c = clear_root_cause_store()
    return {"message": f"已清空 {c} 条根因诊断报告", "cleared_count": c}
