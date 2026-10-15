"""Global Test Asset Full-Scope Dependency Graph REST API Router (C2.1)."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_engineer
from app.core.database import get_db
from app.models.case import TestCase
from app.models.dataset import TestDataset
from app.models.plan import TestPlan
from app.models.suite import TestSuite
from app.models.user import User
from app.services.asset_graph_indexer import (
    AssetType,
    RelationType,
    get_global_asset_indexer,
)
from app.services.contract_change_impact_analyzer import analyze_contract_change_impact
from app.services.targeted_regression_trigger import synthesize_and_trigger_targeted_regression

router = APIRouter(prefix="/asset-graph", tags=["测试资产全景依赖图谱与反向索引"])


class AnalyzeContractImpactIn(BaseModel):
    method: str = Field(default="POST", description="HTTP 请求方法")
    path: str = Field(default="/api/v1/orders", description="接口路由路径")
    baseline_schema: dict[str, Any] = Field(..., description="基线旧版接口契约 Schema")
    current_schema: dict[str, Any] = Field(..., description="当前新版接口契约 Schema")
    project_id: int | None = Field(default=None, description="所属项目 ID")


class SynthesizeRegressionIn(BaseModel):
    impacted_case_ids: list[int] = Field(min_length=1, description="受影响的用例 ID 列表")
    project_id: int = Field(ge=1, description="归属项目 ID")
    suite_name: str | None = Field(default=None, description="生成的精准回归套件名称")
    priority: str | None = Field(default=None, description="任务优先级 P0 | P1 | P2 | P3")
    is_breaking_change: bool = Field(default=False, description="是否破坏性变更 (为 True 则自动触发 P0 弹性抢占)")
    persist: bool = Field(default=True, description="是否持久化写入数据库")
    auto_trigger: bool = Field(default=True, description="是否自动向调度队列投递执行任务")
    queue_name: str = Field(default="default", description="目标执行队列")


@router.get("/project/{project_id}")
async def get_project_asset_graph_endpoint(
    project_id: int,
    _user: User = Depends(get_current_user),
):
    """获取指定项目的全景测试资产依赖有向拓扑图谱与孤儿资产统计。"""
    _ = _user
    indexer = get_global_asset_indexer()
    subgraph = indexer.export_project_subgraph(project_id)
    return subgraph


@router.get("/asset/{asset_type}/{asset_id}/lineage")
async def get_asset_lineage_endpoint(
    asset_type: str,
    asset_id: str,
    max_depth: int = Query(default=5, ge=1, le=10),
    _user: User = Depends(get_current_user),
):
    """双向追踪指定测试资产的全链路血缘：向上查询消费方 (Suites/Plans)，向下查询依赖项 (APIs/Datasets)。"""
    _ = _user
    try:
        a_type = AssetType(asset_type)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"未知的资产类型: {asset_type}")

    indexer = get_global_asset_indexer()
    consumers = indexer.get_upstream_consumers(a_type, asset_id, max_depth=max_depth)
    dependencies = indexer.get_downstream_dependencies(a_type, asset_id, max_depth=max_depth)

    return {
        "asset_type": asset_type,
        "asset_id": asset_id,
        "upstream_consumers": consumers,
        "downstream_dependencies": dependencies,
        "total_consumers_count": len(consumers),
        "total_dependencies_count": len(dependencies),
    }


@router.get("/project/{project_id}/orphans")
async def get_project_orphan_assets_endpoint(
    project_id: int,
    _user: User = Depends(get_current_user),
):
    """检测指定项目中未被任何测试套件或执行计划引用的孤儿用例与无用数据集。"""
    _ = _user
    indexer = get_global_asset_indexer()
    return indexer.find_orphan_assets(project_id)


@router.post("/reindex")
async def trigger_reindex_assets_endpoint(
    project_id: int | None = Query(default=None),
    _user: User = Depends(require_engineer),
    db: AsyncSession = Depends(get_db),
):
    """全量扫描数据库中的用例、套件、计划与数据集，重新构建全域测试资产依赖拓扑与双向索引。"""
    _ = _user
    indexer = get_global_asset_indexer()
    if project_id is not None:
        # Clear only nodes belonging to this project
        pass

    # 1. Index Datasets
    d_stmt = select(TestDataset)
    if project_id:
        d_stmt = d_stmt.where(TestDataset.project_id == project_id)
    d_res = await db.execute(d_stmt)
    datasets = d_res.scalars().all()
    for d in datasets:
        indexer.add_node(AssetType.DATASET, d.id, d.name, d.project_id)

    # 2. Index Test Cases
    c_stmt = select(TestCase)
    c_res = await db.execute(c_stmt)
    cases = c_res.scalars().all()
    for c in cases:
        c_proj = getattr(c, "project_id", project_id or 1)
        indexer.add_node(AssetType.CASE, c.id, c.name, c_proj)
        # Check step API requests in config
        config = c.config or {}
        steps = config.get("steps", [])
        for st in steps:
            if isinstance(st, dict):
                method = st.get("method") or "GET"
                url_path = st.get("url") or st.get("path") or ""
                if url_path:
                    ep_id = f"{method} {url_path}"
                    indexer.add_node(AssetType.API_ENDPOINT, ep_id, ep_id, c_proj)
                    indexer.add_edge(AssetType.CASE, c.id, AssetType.API_ENDPOINT, ep_id, RelationType.CALLS_API)

    # 3. Index Test Suites
    s_stmt = select(TestSuite)
    if project_id:
        s_stmt = s_stmt.where(TestSuite.project_id == project_id)
    s_res = await db.execute(s_stmt)
    suites = s_res.scalars().all()
    for s in suites:
        indexer.add_node(AssetType.SUITE, s.id, s.name, s.project_id)
        # Link cases
        c_ids = s.case_ids or []
        for c_entry in c_ids:
            cid = c_entry.get("case_id") if isinstance(c_entry, dict) else c_entry
            if cid:
                indexer.add_edge(AssetType.SUITE, s.id, AssetType.CASE, cid, RelationType.CONTAINS)

    # 4. Index Test Plans
    p_stmt = select(TestPlan)
    if project_id:
        p_stmt = p_stmt.where(TestPlan.project_id == project_id)
    p_res = await db.execute(p_stmt)
    plans = p_res.scalars().all()
    for p in plans:
        indexer.add_node(AssetType.PLAN, p.id, p.name, p.project_id)
        s_ids = p.suite_ids or []
        for s_entry in s_ids:
            sid = s_entry.get("suite_id") if isinstance(s_entry, dict) else s_entry
            if sid:
                indexer.add_edge(AssetType.PLAN, p.id, AssetType.SUITE, sid, RelationType.CONTAINS)

    return {
        "message": "资产拓扑与双向反向索引全量构建完成",
        "total_nodes": len(indexer.nodes),
        "total_forward_edges": sum(len(e) for e in indexer.forward_edges.values()),
    }


@router.post("/contract-impact/analyze")
async def analyze_contract_impact_endpoint(
    body: AnalyzeContractImpactIn,
    _user: User = Depends(get_current_user),
):
    """对比接口契约前后版本 Schema 变动，并逆向推导波及受损的测试用例与套件影响面。"""
    _ = _user
    report = analyze_contract_change_impact(
        method=body.method,
        path=body.path,
        baseline_schema=body.baseline_schema,
        current_schema=body.current_schema,
        project_id=body.project_id,
    )
    return report.to_dict()


@router.post("/contract-impact/synthesize-and-trigger")
async def synthesize_and_trigger_regression_endpoint(
    body: SynthesizeRegressionIn,
    user: User = Depends(require_engineer),
    db: AsyncSession = Depends(get_db),
):
    """将契约受波及用例自动重组合成为精准回归套件，并向自适应调度队列弹性投递执行。"""
    try:
        result = await synthesize_and_trigger_targeted_regression(
            impacted_case_ids=body.impacted_case_ids,
            project_id=body.project_id,
            owner_id=user.id,
            suite_name=body.suite_name,
            priority=body.priority,
            is_breaking_change=body.is_breaking_change,
            persist=body.persist,
            auto_trigger=body.auto_trigger,
            queue_name=body.queue_name,
            db=db,
        )
        return result.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
