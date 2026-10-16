"""影子数据库/影子表隔离与防污染拦截 REST API (T1.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.shadow_database_isolation_inspector import (
    IsolationStrategy,
    clear_db_isolation_store,
    get_db_isolation_report,
    inspect_sql_isolation_routing,
    list_db_isolation_reports,
    list_shadow_mappings,
    register_shadow_mapping,
)

router = APIRouter(prefix="/stress/shadow-traffic/db-isolation", tags=["影子库表防污染隔离 (T1.2)"])


class QuerySqlIn(BaseModel):
    sql: str = Field(..., description="待检验执行的 SQL 语句")
    is_shadow_traffic: bool = Field(default=True, description="是否属于压测影子流量")


class InspectQueriesIn(BaseModel):
    target_cluster: str = Field(default="prod_db_cluster_01", description="目标数据源/集群标识")
    queries: list[QuerySqlIn] = Field(..., min_length=1, description="SQL 查询集合")


class RegisterMappingIn(BaseModel):
    production_table: str = Field(..., description="生产真实业务表名")
    shadow_table: str = Field(..., description="影子表表名 (如 __shadow_orders__)")
    strategy: str = Field(default="SHADOW_TABLE", description="隔离策略: SHADOW_TABLE, SHADOW_DATABASE, SHADOW_SCHEMA")


@router.post("/inspect")
async def inspect_sql_isolation_endpoint(
    body: InspectQueriesIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """模拟数据库连接池中间件，对压测 SQL 执行影子路由重写与生产防污染拦截。"""
    _ = _user
    queries_dicts = [q.model_dump() for q in body.queries]
    report = inspect_sql_isolation_routing(
        target_cluster=body.target_cluster,
        queries=queries_dicts,
    )
    return {"message": "影子库表隔离与防污染审计完成", "report": report.to_dict()}


@router.post("/mappings")
async def register_mapping_endpoint(
    body: RegisterMappingIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """配置或注册影子表映射规则 (需工程师权限)。"""
    _ = _user
    try:
        strat = IsolationStrategy[body.strategy.upper()]
    except KeyError:
        strat = IsolationStrategy.SHADOW_TABLE

    mapping = register_shadow_mapping(
        production_table=body.production_table,
        shadow_table=body.shadow_table,
        strategy=strat,
    )
    return {"message": "影子表映射注册成功", "mapping": mapping.to_dict()}


@router.get("/mappings")
async def list_mappings_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取所有已注册的影子表路由映射规则。"""
    _ = _user
    mappings = list_shadow_mappings()
    return {"total": len(mappings), "mappings": mappings}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史影子库表隔离审计报告列表。"""
    _ = _user
    reports = list_db_isolation_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次影子库表隔离报告详情。"""
    _ = _user
    report = get_db_isolation_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空影子库表隔离报告仓库 (需工程师权限)。"""
    _ = _user
    clear_db_isolation_store()
    return {"message": "已清空所有影子库表隔离报告"}
