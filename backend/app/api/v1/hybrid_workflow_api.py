"""混合工作流编排与执行管理 REST API (T1.3)"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_engineer
from app.models.user import User
from app.services.hybrid_workflow_dag_engine import (
    CyclicWorkflowError,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeType,
    execute_hybrid_workflow,
    get_workflow_run,
    list_workflow_runs,
)
from app.services.workflow_context_variable_bus import (
    WorkflowVariableBus,
    resolve_node_inputs,
)

router = APIRouter(prefix="/workflow", tags=["Hybrid Workflow Orchestrator"])


class WorkflowNodeDTO(BaseModel):
    node_id: str = Field(..., description="节点全局唯一标识 (如 'node_1')")
    node_name: str = Field(..., description="节点展示名称")
    node_type: str = Field(
        ...,
        description="节点协议类型 (http_request, grpc_call, web_ui_step, mobile_android, mobile_ios, database_query, condition_branch, delay_sleep)",
    )
    config: Dict[str, Any] = Field(default_factory=dict, description="节点参数配置字典")
    condition_expr: Optional[str] = Field(None, description="条件分支判断表达式")


class WorkflowEdgeDTO(BaseModel):
    edge_id: str = Field(..., description="边唯一标识")
    source_node_id: str = Field(..., description="源节点 ID")
    target_node_id: str = Field(..., description="目标节点 ID")
    branch_type: str = Field("default", description="分支流转类型 (default | true | false)")


class SaveWorkflowDraftRequest(BaseModel):
    workflow_id: str = Field(..., description="工作流唯一标识")
    workflow_name: str = Field(..., description="工作流业务名称")
    description: Optional[str] = Field(None, description="工作流业务描述")
    nodes: List[WorkflowNodeDTO] = Field(default_factory=list, description="工作流拓扑节点列表")
    edges: List[WorkflowEdgeDTO] = Field(default_factory=list, description="工作流连接线边列表")


class ExecuteWorkflowRequest(BaseModel):
    workflow_id: str = Field(..., description="工作流唯一标识")
    workflow_name: str = Field("混合自动化测试工作流", description="工作流名称")
    nodes: List[WorkflowNodeDTO] = Field(..., description="拓扑节点列表")
    edges: List[WorkflowEdgeDTO] = Field(default_factory=list, description="拓扑连接边列表")
    initial_variables: Dict[str, Any] = Field(default_factory=dict, description="全局初始化变量字典")


class ResolveVariablesRequest(BaseModel):
    raw_config: Dict[str, Any] = Field(..., description="待解析的原始配置字典")
    context_variables: Dict[str, Any] = Field(default_factory=dict, description="当前总线上下文变量字典")


# 全局轻量级工作流草稿存储
_WORKFLOW_DRAFTS: Dict[str, Dict[str, Any]] = {}


@router.post("/save")
def save_workflow_draft_endpoint(
    payload: SaveWorkflowDraftRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """保存或更新混合编排工作流拓扑草稿"""
    _WORKFLOW_DRAFTS[payload.workflow_id] = payload.model_dump()
    return {
        "message": f"工作流草稿 [{payload.workflow_name}] 保存成功",
        "workflow_id": payload.workflow_id,
        "nodes_count": len(payload.nodes),
        "edges_count": len(payload.edges),
    }


@router.get("/drafts")
def list_workflow_drafts_endpoint(
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取已保存的工作流草稿列表"""
    drafts = list(_WORKFLOW_DRAFTS.values())
    return {
        "total": len(drafts),
        "drafts": drafts,
    }


@router.get("/draft/{workflow_id}")
def get_workflow_draft_endpoint(
    workflow_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取指定工作流草稿拓扑配置"""
    draft = _WORKFLOW_DRAFTS.get(workflow_id)
    if not draft:
        raise HTTPException(status_code=404, detail="未找到目标工作流草稿")
    return {"draft": draft}


@router.post("/execute")
def execute_workflow_endpoint(
    payload: ExecuteWorkflowRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """触发多协议多端混合工作流拓扑排序执行"""
    domain_nodes: List[WorkflowNode] = []
    for n in payload.nodes:
        try:
            ntype = WorkflowNodeType(n.node_type)
        except ValueError:
            ntype = WorkflowNodeType.HTTP_REQUEST

        domain_nodes.append(
            WorkflowNode(
                node_id=n.node_id,
                node_name=n.node_name,
                node_type=ntype,
                config=n.config,
                condition_expr=n.condition_expr,
            )
        )

    domain_edges: List[WorkflowEdge] = [
        WorkflowEdge(
            edge_id=e.edge_id,
            source_node_id=e.source_node_id,
            target_node_id=e.target_node_id,
            branch_type=e.branch_type,
        )
        for e in payload.edges
    ]

    try:
        report = execute_hybrid_workflow(
            workflow_id=payload.workflow_id,
            workflow_name=payload.workflow_name,
            nodes=domain_nodes,
            edges=domain_edges,
            initial_variables=payload.initial_variables,
        )
        return {
            "message": "混合工作流执行完成",
            "report": report.to_dict(),
        }
    except CyclicWorkflowError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/run/{run_id}")
def get_run_report_endpoint(
    run_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取指定运行任务报告详情"""
    report = get_workflow_run(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="未找到目标工作流执行报告")
    return {"report": report.to_dict()}


@router.get("/runs")
def list_runs_endpoint(
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询近期混合工作流执行历史"""
    runs = list_workflow_runs(limit=limit)
    return {
        "total": len(runs),
        "runs": runs,
    }


@router.post("/variable/resolve")
def resolve_variables_endpoint(
    payload: ResolveVariablesRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """独立测试变量表达式与总线求值"""
    bus = WorkflowVariableBus(payload.context_variables)
    resolved = resolve_node_inputs(payload.raw_config, bus)
    return {
        "resolved_config": resolved,
        "variables_in_bus": bus.to_dict(),
    }
