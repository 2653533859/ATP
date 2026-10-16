"""数据库 Schema 结构与索引变更漂移自动比对 REST API (T2.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.db_schema_drift_compatibility_checker import (
    clear_schema_drift_store,
    compare_database_schemas,
    get_schema_drift_report,
    list_schema_drift_reports,
    register_db_schema_snapshot,
)

router = APIRouter(prefix="/env-drift/schema", tags=["数据库 Schema 漂移比对 (T2.2)"])


class ColumnItemIn(BaseModel):
    name: str = Field(...)
    data_type: str = Field(...)
    nullable: bool = Field(default=True)
    default_value: str | None = Field(default=None)
    is_primary_key: bool = Field(default=False)


class IndexItemIn(BaseModel):
    name: str = Field(...)
    columns: list[str] = Field(...)
    is_unique: bool = Field(default=False)


class TableItemIn(BaseModel):
    table_name: str = Field(...)
    columns: list[ColumnItemIn] = Field(...)
    indexes: list[IndexItemIn] = Field(default_factory=list)


class RegisterSchemaSnapshotIn(BaseModel):
    env_name: str = Field(..., description="环境名称 (如 production, testing)")
    database_name: str = Field(..., description="数据库名称 (如 orders_db)")
    tables: list[TableItemIn] = Field(..., description="表结构列表")


class CompareSchemaIn(BaseModel):
    database_name: str = Field(...)
    base_env: str = Field(default="production")
    target_env: str = Field(default="testing")
    base_tables: list[TableItemIn] | None = Field(default=None)
    target_tables: list[TableItemIn] | None = Field(default=None)


@router.post("/register-snapshot")
async def register_schema_snapshot_endpoint(
    body: RegisterSchemaSnapshotIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """登记数据库环境表结构与索引快照（需工程师权限）。"""
    _ = _user
    tables_dicts = [t.model_dump() for t in body.tables]
    res = register_db_schema_snapshot(
        env_name=body.env_name,
        database_name=body.database_name,
        tables=tables_dicts,
    )
    return res


@router.post("/compare")
async def compare_schemas_endpoint(
    body: CompareSchemaIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """比对基准环境与目标环境数据库 Schema 结构与索引差异，输出报告与修复 DDL。"""
    _ = _user
    b_tbls = [t.model_dump() for t in body.base_tables] if body.base_tables is not None else None
    t_tbls = [t.model_dump() for t in body.target_tables] if body.target_tables is not None else None

    report = compare_database_schemas(
        database_name=body.database_name,
        base_env=body.base_env,
        target_env=body.target_env,
        base_tables=b_tbls,
        target_tables=t_tbls,
    )
    return {"message": "数据库 Schema 结构漂移比对完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史 Schema 漂移报告列表。"""
    _ = _user
    reports = list_schema_drift_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单次 Schema 漂移报告详情。"""
    _ = _user
    report = get_schema_drift_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空 Schema 快照与历史报告（需工程师权限）。"""
    _ = _user
    clear_schema_drift_store()
    return {"message": "已清空数据库 Schema 快照与历史报告"}
