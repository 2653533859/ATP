"""缺陷工单自动指派与多平台网关 REST API (T3.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.defect_auto_ticket_dispatcher import (
    clear_ticket_store,
    dispatch_defect_ticket,
    get_ticket,
    list_tickets,
    update_ticket_status,
)

router = APIRouter(prefix="/diagnosis/ticket-dispatch", tags=["缺陷严重度评级与工单指派 (T3.3)"])


class DispatchTicketIn(BaseModel):
    case_id: str = Field(..., description="失败用例 ID")
    case_name: str = Field(..., description="用例名称")
    category: str = Field(..., description="根因分类 (如 DATABASE_EXECUTION_FAILURE / DOWNSTREAM_SERVICE_CRASH)")
    primary_summary: str = Field(..., description="根因诊断摘要")
    culprit_service: str = Field(default="unknown-service", description="故障责任微服务")
    culprit_location: str = Field(default="unknown_location", description="首发代码位置")
    causal_chain: list[str] = Field(default_factory=list, description="因果链条列表")
    suggested_action: str = Field(default="排查相关服务日志与代码实现", description="专家建议")
    http_status_code: int | None = Field(default=None, description="HTTP 状态码")
    error_message: str = Field(default="", description="原始错误信息")
    platform: str = Field(default="JIRA", description="建单目标平台: JIRA | GITHUB_ISSUE | WEBHOOK_ROBOT")
    override_assignee: str | None = Field(default=None, description="覆盖指派人 (选填)")
    is_critical_asset: bool = Field(default=False, description="是否属于核心关键资产")


class UpdateTicketStatusIn(BaseModel):
    status: str = Field(..., description="新状态: OPEN | ASSIGNED | DISPATCHED | RESOLVED")


@router.post("/dispatch")
async def dispatch_ticket_endpoint(
    body: DispatchTicketIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """智能评定缺陷等级并在目标平台 (Jira/GitHub/Webhook) 自动建单。"""
    _ = _user
    ticket = dispatch_defect_ticket(
        case_id=body.case_id,
        case_name=body.case_name,
        category=body.category,
        primary_summary=body.primary_summary,
        culprit_service=body.culprit_service,
        culprit_location=body.culprit_location,
        causal_chain=body.causal_chain,
        suggested_action=body.suggested_action,
        http_status_code=body.http_status_code,
        error_message=body.error_message,
        platform=body.platform,
        override_assignee=body.override_assignee,
        is_critical_asset=body.is_critical_asset,
    )
    return {"message": "缺陷工单已自动创建并成功指派", "ticket": ticket.to_dict()}


@router.get("/tickets")
async def list_tickets_endpoint(
    platform: str | None = None,
    severity: str | None = None,
    culprit_service: str | None = None,
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询已分发的缺陷工单列表。"""
    _ = _user
    tickets = list_tickets(
        platform=platform,
        severity=severity,
        culprit_service=culprit_service,
        limit=limit,
    )
    return {"total": len(tickets), "tickets": [t.to_dict() for t in tickets]}


@router.get("/tickets/{ticket_id}")
async def get_ticket_endpoint(
    ticket_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定缺陷工单详情。"""
    _ = _user
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到该工单: {ticket_id}",
        )
    return ticket.to_dict()


@router.patch("/tickets/{ticket_id}")
async def update_ticket_endpoint(
    ticket_id: str,
    body: UpdateTicketStatusIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """更新缺陷工单流转状态。"""
    _ = _user
    ok = update_ticket_status(ticket_id, body.status)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"更新工单状态失败: {ticket_id}",
        )
    return {"message": "工单状态已更新", "ticket_id": ticket_id, "status": body.status.upper()}


@router.delete("/tickets")
async def clear_tickets_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空已建单记录 (需工程师权限)。"""
    _ = _user
    c = clear_ticket_store()
    return {"message": f"已清空 {c} 条工单记录", "cleared_count": c}
