"""消息总线延迟积压、死信与幂等消费验证 REST API (T2.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.event_bus_deadletter_idempotency_guard import (
    clear_event_bus,
    consume_event_message,
    get_topic_lag_metrics,
    list_dead_letter_messages,
    produce_event_message,
    requeue_dead_letter,
    verify_message_idempotency,
)

router = APIRouter(prefix="/consistency/event-bus", tags=["消息事件总线死信与幂等守卫 (T2.3)"])


class ProduceMessageIn(BaseModel):
    topic: str = Field(..., description="目标 Topic (如 order.events)")
    payload: dict[str, Any] = Field(..., description="消息体内容")
    idempotency_key: str | None = Field(default=None, description="业务幂等性凭证 (如 order_id)")
    consumer_group: str = Field(default="default_group", description="消费者组名")
    max_retries: int = Field(default=3, ge=1, le=10, description="最大允许重试次数")


class ConsumeMessageIn(BaseModel):
    message_id: str = Field(..., description="待消费的消息唯一 ID")
    consumer_group: str | None = Field(default=None, description="消费者组名")
    simulate_fail: bool = Field(default=False, description="是否模拟消费失败")
    error_reason: str = Field(default="Simulated consumer execution failure", description="失败原因")


class VerifyIdempotencyIn(BaseModel):
    topic: str = Field(default="order.events", description="测试 Topic")
    idempotency_key: str = Field(..., description="测试唯一幂等业务键 (如 order_1001)")
    delivery_times: int = Field(default=3, ge=2, le=20, description="重复投递次数")
    consumer_group: str = Field(default="order_consumer_group", description="消费者组名")


@router.post("/messages/produce")
async def produce_message_endpoint(
    body: ProduceMessageIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """向事件总线模拟发布一条事件消息。"""
    _ = _user
    msg = produce_event_message(
        topic=body.topic,
        payload=body.payload,
        idempotency_key=body.idempotency_key,
        consumer_group=body.consumer_group,
        max_retries=body.max_retries,
    )
    return {"message": "消息发布成功", "event": msg.to_dict()}


@router.post("/messages/consume")
async def consume_message_endpoint(
    body: ConsumeMessageIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """模拟消费消息，执行幂等检查与死信转移。"""
    _ = _user
    res = consume_event_message(
        message_id=body.message_id,
        consumer_group=body.consumer_group,
        simulate_fail=body.simulate_fail,
        error_reason=body.error_reason,
    )
    return res


@router.post("/idempotency/verify")
async def verify_idempotency_endpoint(
    body: VerifyIdempotencyIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对同一个业务幂等凭证发起多轮重复投递压测，校验业务消费幂等性。"""
    _ = _user
    report = verify_message_idempotency(
        topic=body.topic,
        idempotency_key=body.idempotency_key,
        delivery_times=body.delivery_times,
        consumer_group=body.consumer_group,
    )
    return {"message": "幂等性压测完成", "report": report.to_dict()}


@router.get("/lag")
async def get_lag_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询各 Topic 与消费者组当前消费延迟与消息积压指标。"""
    _ = _user
    metrics = get_topic_lag_metrics()
    return {"total": len(metrics), "metrics": [m.to_dict() for m in metrics]}


@router.get("/dead-letters")
async def list_dead_letters_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询死信队列 (DLQ) 中的有毒消息列表。"""
    _ = _user
    dlqs = list_dead_letter_messages()
    return {"total": len(dlqs), "dead_letters": [d.to_dict() for d in dlqs]}


@router.post("/dead-letters/{message_id}/requeue")
async def requeue_dlq_endpoint(
    message_id: str,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """将死信重新放回排队重试队列 (需工程师权限)。"""
    _ = _user
    ok = requeue_dead_letter(message_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到处于死信状态的消息: {message_id}",
        )
    return {"message": "死信已重新入队排队重试", "message_id": message_id}


@router.delete("/messages")
async def clear_messages_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空事件总线消息与幂等记录 (需工程师权限)。"""
    _ = _user
    c = clear_event_bus()
    return {"message": f"已清空 {c} 条消息数据", "cleared_count": c}
