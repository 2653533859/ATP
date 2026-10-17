"""低代码可视化漏测血缘与推荐补测管理 REST API (T2.3)"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_engineer
from app.models.user import User
from app.services.missing_test_case_synthesizer import (
    synthesize_cases_for_all_gaps,
)
from app.services.visual_coverage_lineage_analyzer import (
    CoverageLineageEdge,
    CoverageLineageNode,
    LineageCategory,
    analyze_coverage_lineage,
    get_coverage_report,
    list_coverage_reports,
)

router = APIRouter(prefix="/coverage", tags=["Visual Coverage Lineage & Gap Analysis"])


class CoverageNodeDTO(BaseModel):
    node_id: str = Field(..., description="节点唯一标识 (如 'req_checkout', 'api_order_create')")
    node_name: str = Field(..., description="业务或接口名称")
    category: str = Field(..., description="节点类型 (requirement | api_endpoint | ui_interaction | business_branch)")
    expected_branches: List[str] = Field(default_factory=list, description="预期覆盖的分支或场景列表")
    covered_branches: List[str] = Field(default_factory=list, description="实际已被用例覆盖的分支列表")
    linked_case_ids: List[str] = Field(default_factory=list, description="关联的测试用例 ID 列表")
    description: Optional[str] = Field("", description="节点业务说明")


class CoverageEdgeDTO(BaseModel):
    edge_id: str = Field(..., description="边唯一标识")
    source_id: str = Field(..., description="父节点 ID")
    target_id: str = Field(..., description="子节点 ID")
    relationship: str = Field("implements", description="血缘关系 (implements | triggers | validates)")


class AnalyzeLineageRequest(BaseModel):
    project_id: str = Field("default", description="项目唯一标识")
    nodes: List[CoverageNodeDTO] = Field(..., description="业务与接口节点列表")
    edges: List[CoverageEdgeDTO] = Field(default_factory=list, description="血缘层级边连接列表")


class SynthesizeCasesRequest(BaseModel):
    gap_nodes: List[CoverageNodeDTO] = Field(..., description="待补全用例的漏测节点列表")


def _convert_node_dto(dto: CoverageNodeDTO) -> CoverageLineageNode:
    try:
        cat = LineageCategory(dto.category)
    except ValueError:
        cat = LineageCategory.BUSINESS_BRANCH

    return CoverageLineageNode(
        node_id=dto.node_id,
        node_name=dto.node_name,
        category=cat,
        expected_branches=dto.expected_branches,
        covered_branches=dto.covered_branches,
        linked_case_ids=dto.linked_case_ids,
        description=dto.description or "",
    )


@router.post("/lineage/analyze")
def analyze_lineage_endpoint(
    payload: AnalyzeLineageRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """提交业务需求与用例覆盖矩阵，分析漏测血缘与测试盲区"""
    domain_nodes = [_convert_node_dto(n) for n in payload.nodes]
    domain_edges = [
        CoverageLineageEdge(
            edge_id=e.edge_id,
            source_id=e.source_id,
            target_id=e.target_id,
            relationship=e.relationship,
        )
        for e in payload.edges
    ]

    report = analyze_coverage_lineage(
        project_id=payload.project_id,
        nodes=domain_nodes,
        edges=domain_edges,
    )
    return {
        "message": "漏测血缘与覆盖间隙分析完成",
        "report": report.to_dict(),
    }


@router.get("/lineage/{report_id}")
def get_report_endpoint(
    report_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取指定漏测血缘报告详情与树形拓扑"""
    report = get_coverage_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="未找到目标漏测血缘分析报告")
    return {"report": report.to_dict()}


@router.get("/lineages")
def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询近期漏测血缘分析报告"""
    reports = list_coverage_reports(limit=limit)
    return {
        "total": len(reports),
        "reports": reports,
    }


@router.post("/synthesize")
def synthesize_cases_endpoint(
    payload: SynthesizeCasesRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """针对漏测盲区节点一键逆向推导合成自动化测试用例草稿"""
    domain_nodes = [_convert_node_dto(n) for n in payload.gap_nodes]
    drafts = synthesize_cases_for_all_gaps(domain_nodes)
    return {
        "message": f"成功针对漏测盲区合成 {len(drafts)} 条测试用例草稿",
        "total_synthesized": len(drafts),
        "drafts": [d.to_dict() for d in drafts],
    }
