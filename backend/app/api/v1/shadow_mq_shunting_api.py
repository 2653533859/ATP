"""消息队列影子队列与死信重试分流隔离 REST API (T1.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.shadow_mq_queue_router import (
    MqBypassAction,
    clear_mq_shunting_store,
    get_mq_shunting_report,
    list_mq_route_rules,
    list_mq_shunting_reports,
    register_mq_route_rule,
    route_mq_messages,
)

router = APIRouter(prefix="/stress/shadow-traffic/mq-shunting", tags=["MQ 影子队列分流隔离 (T1.3)"])


class MqMessageIn(BaseModel):
    message_id: str | None = Field(default=None, description="消息唯一标识")
    topic: str = Field(..., description="原始投递的主题/队列名称")
    headers: dict[str, Any] = Field(default_factory=dict, description="消息头或元数据")
    is_shadow_traffic: bool = Field(default=True, description="是否属于压测影子消息")


class RouteMqMessagesIn(BaseModel):
    cluster_name: str = Field(default="prod_kafka_cluster_01", description="消息中间件集群名称")
    messages: list[MqMessageIn] = Field(..., min_length=1, description="待分流路由的消息批次")


class RegisterMqRuleIn(BaseModel):
    production_topic: str = Field(..., description="生产真实 Topic/Queue")
    shadow_topic: str = Field(..., description="影子重定向 Topic/Queue (如 __shadow_orders__)")
    dead_letter_queue: str = Field(..., description="关联隔离的死信队列 (如 __shadow_orders_dlq__)")
    bypass_action: str = Field(
        default="REDIRECT_SHADOW_CONSUMER",
        description="旁路阻断动作: REDIRECT_SHADOW_CONSUMER, MOCK_DISPATCH, DROP_SILENTLY",
    )


@router.post("/route")
async def route_mq_messages_endpoint(
    body: RouteMqMessagesIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """模拟 MQ 代理/拦截器，对发布与消费的消息执行影子分流、死信隔离与旁路 Mock。"""
    _ = _user
    msgs_dicts = [m.model_dump() for m in body.messages]
    report = route_mq_messages(
        cluster_name=body.cluster_name,
        messages=msgs_dicts,
    )
    return {"message": "MQ 影子消息分流与隔离审计完成", "report": report.to_dict()}


@router.post("/rules")
async def register_mq_rule_endpoint(
    body: RegisterMqRuleIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """配置或注册 MQ 影子分流规则 (需工程师权限)。"""
    _ = _user
    try:
        action = MqBypassAction[body.bypass_action.upper()]
    except KeyError:
        action = MqBypassAction.REDIRECT_SHADOW_CONSUMER

    rule = register_mq_route_rule(
        production_topic=body.production_topic,
        shadow_topic=body.shadow_topic,
        dead_letter_queue=body.dead_letter_queue,
        bypass_action=action,
    )
    return {"message": "MQ 影子分流规则注册成功", "rule": rule.to_dict()}


@router.get("/rules")
async def list_mq_rules_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取所有已生效的 MQ 影子分流路由规则。"""
    _ = _user
    rules = list_mq_route_rules()
    return {"total": len(rules), "rules": rules}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史 MQ 影子分流审计报告列表。"""
    _ = _user
    reports = list_mq_shunting_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次 MQ 分流报告详情。"""
    _ = _user
    report = get_mq_shunting_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空 MQ 分流报告仓库 (需工程师权限)。"""
    _ = _user
    clear_mq_shunting_store()
    return {"message": "已清空所有 MQ 影子分流报告"}
