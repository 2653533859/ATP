"""代码变更影响面与精准测试推荐 API (S1.1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.git_diff_ast_analyzer import (
    analyze_git_diff_ast,
    get_diff_ast_report,
    list_diff_ast_reports,
)

router = APIRouter(prefix="/ci-impact", tags=["CI 代码变更影响面与精准测试"])


class AnalyzeDiffAstIn(BaseModel):
    diff_text: str = Field(min_length=1, description="Git Unified Diff 文本")
    file_sources: dict[str, str] | None = Field(
        default=None, description="变更涉及的 Python 源码字典（文件路径 -> 源码文本）"
    )


@router.post("/diff-ast/analyze")
async def analyze_diff_ast_endpoint(
    body: AnalyzeDiffAstIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """对提交的 Git Diff 进行 Python AST 语法树遍历与符号级变更影响面推导 (需工程师权限)。"""
    _ = _user
    report = analyze_git_diff_ast(
        diff_text=body.diff_text,
        file_sources=body.file_sources,
    )
    return {"message": "Git Diff AST 变更符号解析完成", "report": report.to_dict()}


@router.get("/diff-ast/reports")
async def list_diff_ast_reports_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史 Git Diff AST 分析报告列表。"""
    _ = _user
    reports = list_diff_ast_reports()
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/diff-ast/reports/{analysis_id}")
async def get_diff_ast_report_endpoint(
    analysis_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定 Git Diff AST 分析报告详情。"""
    _ = _user
    report = get_diff_ast_report(analysis_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Diff AST 报告不存在: {analysis_id}")
    return report.to_dict()
