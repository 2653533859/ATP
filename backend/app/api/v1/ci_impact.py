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
from app.services.code_to_test_mapping_indexer import (
    TestCaseRef,
    get_mapping_indexer,
)
from app.services.smart_test_selection_engine import (
    SelectionStrategy,
    get_selection_report,
    list_selection_reports,
    select_tests_from_diff,
)
from app.services.dynamic_test_shard_partitioner import (
    get_sharding_report,
    list_sharding_reports,
    partition_tests_dynamically,
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


class RegisterBindingIn(BaseModel):
    case_id: int = Field(ge=1, description="测试用例 ID")
    case_name: str = Field(min_length=1, max_length=128, description="测试用例名称")
    case_type: str = Field(default="api", description="用例类型: api | web | android | ios")
    project_id: int | None = Field(default=None, description="所属项目 ID")
    priority: str = Field(default="P1", description="用例优先级: P0 | P1 | P2 | P3")
    bound_symbols: list[str] | None = Field(default=None, description="绑定的代码符号 ID 列表")
    bound_routes: list[tuple[str, str]] | None = Field(
        default=None, description="绑定的 API 路由 [(METHOD, PATH), ...]"
    )


class AutoIndexStepsIn(BaseModel):
    case_id: int = Field(ge=1, description="测试用例 ID")
    case_name: str = Field(min_length=1, max_length=128, description="测试用例名称")
    case_type: str = Field(default="api", description="用例类型")
    steps: list[dict[str, Any]] = Field(default_factory=list, description="用例步骤列表")
    project_id: int | None = Field(default=None, description="项目 ID")
    priority: str = Field(default="P1", description="用例优先级")


class QueryAffectedCasesIn(BaseModel):
    symbols: list[str] | None = Field(default=None, description="变更的代码符号 ID 列表")
    routes: list[str] | None = Field(default=None, description="变更的 API 路由 (如 ['POST /api/v1/orders'])")
    file_paths: list[str] | None = Field(default=None, description="变更的源码文件路径")
    project_id: int | None = Field(default=None, description="项目隔离过滤")


@router.post("/mapping/bind")
async def register_binding_endpoint(
    body: RegisterBindingIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """显式注册代码符号、API 端点与测试用例的双向映射绑定 (需工程师权限)。"""
    _ = _user
    indexer = get_mapping_indexer()
    case = TestCaseRef(
        case_id=body.case_id,
        case_name=body.case_name,
        case_type=body.case_type,
        project_id=body.project_id,
        priority=body.priority,
    )
    res = indexer.register_binding(
        case=case,
        bound_symbols=body.bound_symbols,
        bound_routes=body.bound_routes,
    )
    return {"message": "用例与代码符号依赖映射注册成功", "case": res.to_dict()}


@router.post("/mapping/auto-index-steps")
async def auto_index_steps_endpoint(
    body: AutoIndexStepsIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """从用例步骤参数中自动提取请求 URL 与 Method 并建立映射索引 (需工程师权限)。"""
    _ = _user
    indexer = get_mapping_indexer()
    case = indexer.auto_index_from_steps(
        case_id=body.case_id,
        case_name=body.case_name,
        case_type=body.case_type,
        steps=body.steps,
        project_id=body.project_id,
        priority=body.priority,
    )
    return {"message": "用例步骤路由依赖自动提取索引完成", "case": case.to_dict()}


@router.post("/mapping/query-affected")
async def query_affected_cases_endpoint(
    body: QueryAffectedCasesIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """依据代码符号、API 端点或文件变更，反查全部波及的测试用例列表。"""
    _ = _user
    indexer = get_mapping_indexer()
    cases = indexer.query_affected_cases(
        symbols=body.symbols,
        routes=body.routes,
        file_paths=body.file_paths,
        project_id=body.project_id,
    )
    return {"total": len(cases), "cases": [c.to_dict() for c in cases]}


@router.get("/mapping/stats")
async def get_mapping_stats_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询代码-用例映射图谱的总体统计指标。"""
    _ = _user
    indexer = get_mapping_indexer()
    return indexer.get_stats()


class SelectTestsIn(BaseModel):
    diff_text: str = Field(min_length=1, description="Git Unified Diff 文本")
    file_sources: dict[str, str] | None = Field(default=None, description="变更涉及的 Python 源码字典")
    strategy: str = Field(default="balanced", description="选择策略: minimal | balanced | comprehensive")
    max_cases: int = Field(default=100, ge=1, le=1000, description="最大推荐用例数量限制")
    project_id: int | None = Field(default=None, description="项目隔离过滤")
    total_repo_cases_override: int | None = Field(
        default=None, ge=1, description="仓库全量用例数基准（用于计算裁剪率）"
    )


@router.post("/test-selection/select")
async def select_tests_endpoint(
    body: SelectTestsIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """基于 Git Diff 运行 TIA 算法，推导精准最小化回归测试子集 (需工程师权限)。"""
    _ = _user
    try:
        strat_enum = SelectionStrategy(body.strategy.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的选择策略: {body.strategy}")

    report = select_tests_from_diff(
        diff_text=body.diff_text,
        file_sources=body.file_sources,
        strategy=strat_enum,
        max_cases=body.max_cases,
        project_id=body.project_id,
        total_repo_cases_override=body.total_repo_cases_override,
    )
    return {"message": "精准测试用例集推荐推导完成", "report": report.to_dict()}


@router.get("/test-selection/reports")
async def list_selection_reports_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史精准测试集推荐报告列表。"""
    _ = _user
    reports = list_selection_reports()
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/test-selection/reports/{selection_id}")
async def get_selection_report_endpoint(
    selection_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定精准测试集推荐报告详情。"""
    _ = _user
    report = get_selection_report(selection_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"测试推荐报告不存在: {selection_id}")
    return report.to_dict()


class PartitionTestsIn(BaseModel):
    case_ids: list[int] = Field(min_length=1, description="需切片执行的测试用例 ID 列表")
    target_shards_count: int = Field(default=4, ge=1, le=64, description="目标并发分片数 (Worker 容器数)")
    case_duration_history: dict[int, float] | None = Field(default=None, description="用例历史执行耗时秒数字典")
    default_case_duration_sec: float = Field(default=3.5, ge=0.1, description="无历史耗时记录时的兜底均值 (秒)")


@router.post("/sharding/partition")
async def partition_tests_endpoint(
    body: PartitionTestsIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """基于贪心 LPT 算法对测试用例集执行动态负载均衡切片分发 (需工程师权限)。"""
    _ = _user
    report = partition_tests_dynamically(
        case_ids=body.case_ids,
        target_shards_count=body.target_shards_count,
        case_duration_history=body.case_duration_history,
        default_case_duration_sec=body.default_case_duration_sec,
    )
    return {"message": "动态测试切片分配完成", "report": report.to_dict()}


@router.get("/sharding/reports")
async def list_sharding_reports_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史动态分片报告列表。"""
    _ = _user
    reports = list_sharding_reports()
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/sharding/reports/{sharding_id}")
async def get_sharding_report_endpoint(
    sharding_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定动态分片报告详情。"""
    _ = _user
    report = get_sharding_report(sharding_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"分片报告不存在: {sharding_id}")
    return report.to_dict()
