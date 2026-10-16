"""企业级多渠道交互式卡片 Webhook 智能投递 API (D4.2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.notification_hub_dispatcher import (
    DeliveryPriority,
    NotificationCardPayload,
    NotificationChannel,
    NotificationRouteTarget,
    broadcast_notification,
    calculate_dispatcher_stats,
    dispatch_notification,
    list_delivery_audit_records,
)

router = APIRouter(prefix="/reporting/notifications", tags=["多渠道交互卡片 Webhook 智能投递"])


class NotificationCardIn(BaseModel):
    title: str = Field(min_length=1, max_length=128, description="卡片主标题")
    summary: str = Field(min_length=1, max_length=512, description="执行摘要描述")
    status: str = Field(default="passed", description="状态: passed | failed | error | blocked | approved")
    project_name: str = Field(min_length=1, max_length=128, description="项目名称")
    run_id: str | int = Field(description="测试执行批次 ID")
    pass_rate_pct: float = Field(ge=0.0, le=100.0, description="用例通过率")
    duration_sec: float = Field(ge=0.0, description="执行总耗时 (秒)")
    report_url: str | None = Field(default=None, description="报告跳转 URL")
    metrics: dict[str, Any] = Field(default_factory=dict, description="业务度量键值指标")
    actions: list[dict[str, str]] = Field(default_factory=list, description="卡片交互按钮集合")
    mentions: list[str] = Field(default_factory=list, description="被 @ 的人员标识")


class RouteTargetIn(BaseModel):
    channel: str = Field(description="渠道: wechat | dingtalk | feishu | email | slack")
    webhook_url: str = Field(min_length=5, description="Webhook 回调地址")
    secret: str | None = Field(default=None, description="加签密钥")
    enabled: bool = True


class DispatchNotificationIn(BaseModel):
    target: RouteTargetIn
    card: NotificationCardIn
    priority: str = Field(default="P2", description="投递优先级: P0 | P1 | P2 | P3")


class BroadcastNotificationIn(BaseModel):
    targets: list[RouteTargetIn] = Field(min_length=1, description="广播目标通道列表")
    card: NotificationCardIn
    priority: str = Field(default="P2", description="投递优先级: P0 | P1 | P2 | P3")


def _to_card_payload(card_in: NotificationCardIn) -> NotificationCardPayload:
    return NotificationCardPayload(
        title=card_in.title,
        summary=card_in.summary,
        status=card_in.status,
        project_name=card_in.project_name,
        run_id=card_in.run_id,
        pass_rate_pct=card_in.pass_rate_pct,
        duration_sec=card_in.duration_sec,
        report_url=card_in.report_url,
        metrics=card_in.metrics,
        actions=card_in.actions,
        mentions=card_in.mentions,
    )


def _to_route_target(tgt_in: RouteTargetIn) -> NotificationRouteTarget:
    try:
        chan_enum = NotificationChannel(tgt_in.channel.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的通知渠道: {tgt_in.channel}")

    return NotificationRouteTarget(
        channel=chan_enum,
        webhook_url=tgt_in.webhook_url,
        secret=tgt_in.secret,
        enabled=tgt_in.enabled,
    )


@router.post("/dispatch")
async def dispatch_notification_endpoint(
    body: DispatchNotificationIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """向指定 IM 渠道投递富文本交互式卡片告警 (需工程师权限)。"""
    _ = _user
    target = _to_route_target(body.target)
    card = _to_card_payload(body.card)
    try:
        prio_enum = DeliveryPriority(body.priority.upper())
    except ValueError:
        prio_enum = DeliveryPriority.P2_NORMAL

    record = dispatch_notification(target, card, priority=prio_enum)
    return {"message": "通知已调度投递", "record": record.to_dict()}


@router.post("/broadcast")
async def broadcast_notification_endpoint(
    body: BroadcastNotificationIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """向多个 IM 通道并发广播多模态交互式卡片消息。"""
    _ = _user
    targets = [_to_route_target(t) for t in body.targets]
    card = _to_card_payload(body.card)
    try:
        prio_enum = DeliveryPriority(body.priority.upper())
    except ValueError:
        prio_enum = DeliveryPriority.P2_NORMAL

    records = broadcast_notification(targets, card, priority=prio_enum)
    success_count = sum(1 for r in records if r.success)
    return {
        "message": f"广播投递完成: 成功 {success_count}/{len(records)}",
        "total": len(records),
        "success_count": success_count,
        "records": [r.to_dict() for r in records],
    }


@router.get("/audits")
async def list_delivery_audits_endpoint(
    channel_str: str | None = Query(default=None, alias="channel", description="按通知渠道过滤"),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询多渠道消息投递审计流水台账。"""
    _ = _user
    chan_enum = None
    if channel_str:
        try:
            chan_enum = NotificationChannel(channel_str.lower())
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效的通知渠道: {channel_str}")

    records = list_delivery_audit_records(channel=chan_enum)
    return {"total": len(records), "records": [r.to_dict() for r in records]}


@router.get("/stats")
async def get_dispatcher_stats_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取消息投递成功率与各渠道分布度量。"""
    _ = _user
    stats = calculate_dispatcher_stats()
    return stats
