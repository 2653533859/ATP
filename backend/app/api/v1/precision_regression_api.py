"""增量影响面计算与精准用例推荐 REST API (T1.3)

为自动化测试提供代码补丁解析、AST 符号变更提取、精准测试用例推荐与影响血缘追溯 RESTful 端点:
1. 代码补丁 AST 符号变更分析 (/precision-regression/diff/analyze);
2. 符号影响面扩散与精准用例集推荐 (/precision-regression/recommend);
3. 端到端一站式 Diff 到用例推荐计算 (/precision-regression/analyze-and-recommend);
4. 单用例底层接口与符号覆盖反向追溯 (/precision-regression/coverage/{case_id});
5. 拓扑血缘关系动态注册 (/precision-regression/lineage/register)。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import require_engineer
from app.models.user import User
from app.services.code_diff_symbol_extractor import extract_diff_changed_symbols
from app.services.symbol_call_graph_mapper import get_global_call_graph

router = APIRouter(prefix="/precision-regression", tags=["Precision Regression & DAG Topology Orchestrator"])


class DiffAnalyzeRequest(BaseModel):
    diff_text: str = Field(..., description="标准 Unified Diff 补丁文本")
    source_files: Dict[str, str] = Field(..., description="变更关联文件的最新源码映射")


class RecommendCasesRequest(BaseModel):
    changed_symbols: List[str] = Field(..., min_length=1, description="变更的函数或类符号列表")
    total_suite_size: int = Field(50, ge=1, description="回归测试套件全量用例规模")


class EndToEndPrecisionRequest(BaseModel):
    diff_text: str = Field(..., description="标准 Unified Diff 补丁文本")
    source_files: Dict[str, str] = Field(..., description="变更文件源码字典")
    total_suite_size: int = Field(50, ge=1, description="测试套件全量规模")


class RegisterLineageRequest(BaseModel):
    symbol_name: str = Field(..., description="代码符号全限定名")
    endpoint: str = Field(..., description="接口端点标识 (如 POST /api/v1/orders)")
    case_id: Optional[str] = Field(None, description="测试用例 ID")
    case_name: Optional[str] = Field(None, description="测试用例名称")
    cost_seconds: float = Field(10.0, description="用例执行平均耗时")
    priority: str = Field("P1", description="用例优先级 (P0/P1/P2)")


@router.post("/diff/analyze")
def analyze_diff_endpoint(
    payload: DiffAnalyzeRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """解析代码 Diff 补丁并基于 AST 提取发生变更的高危符号"""
    report = extract_diff_changed_symbols(
        diff_text=payload.diff_text,
        source_files=payload.source_files,
    )
    return {
        "message": f"Diff 解析完成，识别出 {report.changed_symbols_count} 个受影响符号",
        "report": report.to_dict(),
    }


@router.post("/recommend")
def recommend_cases_endpoint(
    payload: RecommendCasesRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """根据变更符号集合正向拓扑扩散，输出推荐回归的最小受影响用例集"""
    graph = get_global_call_graph()
    res = graph.trace_impacted_cases(
        changed_symbols=payload.changed_symbols,
        total_suite_size=payload.total_suite_size,
    )
    return {
        "message": f"精准影响面推导完成，从 {res.total_cases_in_suite} 条用例中锁定 {res.impacted_cases_count} 条核心回归用例",
        "result": res.to_dict(),
    }


@router.post("/analyze-and-recommend")
def analyze_and_recommend_endpoint(
    payload: EndToEndPrecisionRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """端到端一站式：从代码 Diff 直达最小精准回归用例集合"""
    diff_report = extract_diff_changed_symbols(
        diff_text=payload.diff_text,
        source_files=payload.source_files,
    )

    symbols_list = [s.symbol_name for s in diff_report.symbols]
    # 添加全限定名
    symbols_list.extend([s.qualified_name for s in diff_report.symbols])

    graph = get_global_call_graph()
    recommend_res = graph.trace_impacted_cases(
        changed_symbols=symbols_list,
        total_suite_size=payload.total_suite_size,
    )

    return {
        "message": "端到端增量精准回归推荐计算完成",
        "diff_symbol_report": diff_report.to_dict(),
        "precision_recommendation": recommend_res.to_dict(),
    }


@router.get("/coverage/{case_id}")
def get_case_coverage_endpoint(
    case_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """反向追溯查询单个用例底层覆盖的接口与函数符号血缘"""
    graph = get_global_call_graph()
    cov = graph.trace_case_symbol_coverage(case_id=case_id)
    return {
        "coverage": cov,
    }


@router.post("/lineage/register")
def register_lineage_endpoint(
    payload: RegisterLineageRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """动态注册符号-接口-用例血缘节点"""
    graph = get_global_call_graph()
    graph.register_symbol_endpoint(payload.symbol_name, payload.endpoint)
    if payload.case_id:
        graph.register_endpoint_case(
            endpoint=payload.endpoint,
            case_id=payload.case_id,
            case_name=payload.case_name or payload.case_id,
            cost_seconds=payload.cost_seconds,
            priority=payload.priority,
        )
    return {
        "message": f"成功建立血缘节点: {payload.symbol_name} ➔ {payload.endpoint}"
        + (f" ➔ {payload.case_id}" if payload.case_id else ""),
    }
