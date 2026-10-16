"""跨微服务异构数据源最终一致性双向稽核 REST API (T2.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.cross_db_data_consistency_auditor import (
    clear_audit_store,
    delete_audit_rule,
    execute_consistency_audit,
    get_audit_report,
    list_audit_reports,
    list_audit_rules,
    register_audit_rule,
)

router = APIRouter(prefix="/consistency/audit", tags=["跨库数据最终一致性稽核 (T2.2)"])


class RegisterAuditRuleIn(BaseModel):
    rule_name: str = Field(..., description="对账规则名称 (如 订单中心-支付结算双向核账)")
    source_service: str = Field(..., description="源微服务名称 (如 order-service)")
    source_table: str = Field(..., description="源数据表/集合名 (如 order_records)")
    target_service: str = Field(..., description="目标微服务名称 (如 pay-service)")
    target_table: str = Field(..., description="目标数据表/集合名 (如 payment_orders)")
    join_key: str = Field(..., description="业务主键关联字段名 (如 order_id)")
    field_mappings: dict[str, str] = Field(default_factory=dict, description="字段映射字典: source_col -> target_col")
    numeric_tolerance: float = Field(default=0.001, ge=0.0, description="浮点数等值容差")
    tolerance_threshold_pct: float = Field(default=98.0, ge=50.0, le=100.0, description="对账通过最低阈值 (%)")
    rule_id: str | None = Field(default=None, description="指定规则 ID (选填)")


class ExecuteAuditIn(BaseModel):
    rule_id: str | None = Field(default=None, description="已注册的规则 ID (选填)")
    rule_name: str = Field(default="动态对账规则", description="规则名称")
    source_service: str = Field(default="order-service", description="源服务")
    source_table: str = Field(default="orders", description="源表")
    target_service: str = Field(default="pay-service", description="目标服务")
    target_table: str = Field(default="payments", description="目标表")
    join_key: str = Field(default="order_id", description="关联对齐主键")
    field_mappings: dict[str, str] = Field(default_factory=dict, description="字段映射字典")
    numeric_tolerance: float = Field(default=0.001, description="数值容差")
    tolerance_threshold_pct: float = Field(default=98.0, description="容忍度阈值")
    source_records: list[dict[str, Any]] = Field(default_factory=list, description="源库待稽核记录数组")
    target_records: list[dict[str, Any]] = Field(default_factory=list, description="目标库待稽核记录数组")


@router.post("/rules")
async def register_rule_endpoint(
    body: RegisterAuditRuleIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """注册跨库最终一致性对账稽核规则 (需工程师权限)。"""
    _ = _user
    rule = register_audit_rule(
        rule_name=body.rule_name,
        source_service=body.source_service,
        source_table=body.source_table,
        target_service=body.target_service,
        target_table=body.target_table,
        join_key=body.join_key,
        field_mappings=body.field_mappings,
        numeric_tolerance=body.numeric_tolerance,
        tolerance_threshold_pct=body.tolerance_threshold_pct,
        rule_id=body.rule_id,
    )
    return {"message": "对账规则已注册", "rule": rule.to_dict()}


@router.get("/rules")
async def list_rules_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询生效的跨库对账稽核规则列表。"""
    _ = _user
    rules = list_audit_rules()
    return {"total": len(rules), "rules": [r.to_dict() for r in rules]}


@router.delete("/rules/{rule_id}")
async def delete_rule_endpoint(
    rule_id: str,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """删除对账规则 (需工程师权限)。"""
    _ = _user
    ok = delete_audit_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"规则未找到: {rule_id}")
    return {"message": "对账规则已删除", "rule_id": rule_id}


@router.post("/execute")
async def execute_audit_endpoint(
    body: ExecuteAuditIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """执行跨微服务异构数据源双向对账稽核。"""
    _ = _user
    rule = register_audit_rule(
        rule_name=body.rule_name,
        source_service=body.source_service,
        source_table=body.source_table,
        target_service=body.target_service,
        target_table=body.target_table,
        join_key=body.join_key,
        field_mappings=body.field_mappings,
        numeric_tolerance=body.numeric_tolerance,
        tolerance_threshold_pct=body.tolerance_threshold_pct,
        rule_id=body.rule_id,
    )
    report = execute_consistency_audit(
        rule=rule,
        source_records=body.source_records,
        target_records=body.target_records,
    )
    return {"message": "跨库数据一致性稽核完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史跨库对账审计报告列表。"""
    _ = _user
    reports = list_audit_reports()
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定跨库对账报告详情。"""
    _ = _user
    report = get_audit_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"对账报告不存在: {report_id}")
    return report.to_dict()


@router.delete("/clear")
async def clear_audit_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空对账规则与报告缓存 (需工程师权限)。"""
    _ = _user
    c = clear_audit_store()
    return {"message": f"已清空 {c} 条对账数据", "cleared_count": c}
