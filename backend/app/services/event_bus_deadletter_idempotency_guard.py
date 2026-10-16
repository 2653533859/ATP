"""消息事件总线消费延迟、死信积压与幂等消费验证引擎 (T2.3)。

负责在微服务异步事件驱动体系 (Kafka / RabbitMQ / RocketMQ) 中：
1. 监控各 Topic 与消费者组 (Consumer Group) 的消费延迟与消息积压 (Consumer Lag)；
2. 识别与隔离反复失败的有毒消息至死信队列 (Dead Letter Queue / DLQ)，支持死信重放；
3. 实施高并发下多轮重复投递压测，严格校验业务消费端的幂等性 (Idempotency Guard)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class MessageStatus(str, Enum):
    PRODUCED = "PRODUCED"  # 已生产发布待消费
    CONSUMED = "CONSUMED"  # 消费成功
    RETRYING = "RETRYING"  # 消费失败重试中
    DEAD_LETTER = "DEAD_LETTER"  # 超过最大重试次数转入死信队列
    DUPLICATE_SUPPRESSED = "DUPLICATE_SUPPRESSED"  # 命中幂等防线，重复消费被安全抑制


class LagSeverity(str, Enum):
    HEALTHY = "HEALTHY"  # 正常无积压 (Lag < 100)
    WARNING = "WARNING"  # 轻微积压 (Lag 100~1000)
    CRITICAL_BACKLOG = "CRITICAL_BACKLOG"  # 严重阻塞积压 (Lag > 1000)


@dataclass
class EventMessageItem:
    message_id: str
    topic: str
    consumer_group: str
    idempotency_key: str
    payload: dict[str, Any]
    status: MessageStatus = MessageStatus.PRODUCED
    retry_count: int = 0
    max_retries: int = 3
    lag_ms: float = 0.0
    error_message: str = ""
    produced_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consumed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "topic": self.topic,
            "consumer_group": self.consumer_group,
            "idempotency_key": self.idempotency_key,
            "payload": self.payload,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "lag_ms": round(self.lag_ms, 2),
            "error_message": self.error_message,
            "produced_at": self.produced_at.isoformat(),
            "consumed_at": self.consumed_at.isoformat() if self.consumed_at else None,
        }


@dataclass
class TopicLagMetric:
    topic: str
    consumer_group: str
    current_lag: int
    lag_severity: LagSeverity
    avg_processing_time_ms: float
    oldest_unconsumed_age_sec: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "consumer_group": self.consumer_group,
            "current_lag": self.current_lag,
            "lag_severity": self.lag_severity.value,
            "avg_processing_time_ms": round(self.avg_processing_time_ms, 2),
            "oldest_unconsumed_age_sec": round(self.oldest_unconsumed_age_sec, 2),
        }


@dataclass
class IdempotencyVerificationReport:
    idempotency_key: str
    topic: str
    consumer_group: str
    total_deliveries: int
    state_mutations_count: int  # 实际执行了底层状态写入/扣款的次数 (必须严格为 1)
    duplicate_suppressed_count: int  # 幂等拦截过滤的重复投递次数
    is_idempotent: bool
    verdict_summary: str
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "idempotency_key": self.idempotency_key,
            "topic": self.topic,
            "consumer_group": self.consumer_group,
            "total_deliveries": self.total_deliveries,
            "state_mutations_count": self.state_mutations_count,
            "duplicate_suppressed_count": self.duplicate_suppressed_count,
            "is_idempotent": self.is_idempotent,
            "verdict_summary": self.verdict_summary,
            "verified_at": self.verified_at.isoformat(),
        }


# 内存消息队列与幂等记录中心
_MESSAGES_STORE: dict[str, EventMessageItem] = {}  # message_id -> EventMessageItem
_IDEMPOTENCY_RECORDS: dict[str, set[str]] = {}  # consumer_group -> set(idempotency_key)
_STATE_MUTATIONS_AUDIT: dict[str, int] = {}  # idempotency_key -> mutation_count


def produce_event_message(
    topic: str,
    payload: dict[str, Any],
    idempotency_key: str | None = None,
    consumer_group: str = "default_group",
    max_retries: int = 3,
    message_id: str | None = None,
) -> EventMessageItem:
    """向事件总线模拟发布一条事件消息。"""
    mid = message_id or f"msg_{uuid.uuid4().hex[:12]}"
    ikey = idempotency_key or f"idem_{uuid.uuid4().hex[:8]}"

    msg = EventMessageItem(
        message_id=mid,
        topic=topic,
        consumer_group=consumer_group,
        idempotency_key=ikey,
        payload=payload,
        status=MessageStatus.PRODUCED,
        max_retries=max_retries,
    )
    _MESSAGES_STORE[mid] = msg
    return msg


def consume_event_message(
    message_id: str,
    consumer_group: str | None = None,
    simulate_fail: bool = False,
    error_reason: str = "Simulated consumer execution failure",
) -> dict[str, Any]:
    """模拟消费消息，执行幂等检查与死信转移。"""
    msg = _MESSAGES_STORE.get(message_id)
    if not msg:
        return {"success": False, "message": f"未找到消息: {message_id}"}

    cg = consumer_group or msg.consumer_group
    now = datetime.now(timezone.utc)
    lag_ms = (now - msg.produced_at).total_seconds() * 1000.0
    msg.lag_ms = lag_ms

    if cg not in _IDEMPOTENCY_RECORDS:
        _IDEMPOTENCY_RECORDS[cg] = set()

    # 1. 幂等性校验：如果该消费者组已处理过该 idempotency_key，安全拦截无副作用返回
    if msg.idempotency_key in _IDEMPOTENCY_RECORDS[cg]:
        msg.status = MessageStatus.DUPLICATE_SUPPRESSED
        msg.consumed_at = now
        return {
            "success": True,
            "status": MessageStatus.DUPLICATE_SUPPRESSED.value,
            "message": f"消息 [{message_id}] 命中幂等防线: idempotency_key='{msg.idempotency_key}' 已在 [{cg}] 执行，安全抑制重复状态变更",
            "state_mutated": False,
        }

    # 2. 模拟业务消费失败与死信队列流转
    if simulate_fail:
        msg.retry_count += 1
        msg.error_message = error_reason
        if msg.retry_count >= msg.max_retries:
            msg.status = MessageStatus.DEAD_LETTER
            return {
                "success": False,
                "status": MessageStatus.DEAD_LETTER.value,
                "message": f"消息重试达上限 ({msg.retry_count}/{msg.max_retries})，已转移至死信队列 (DLQ)",
                "state_mutated": False,
            }
        else:
            msg.status = MessageStatus.RETRYING
            return {
                "success": False,
                "status": MessageStatus.RETRYING.value,
                "message": f"消息消费失败，进入第 {msg.retry_count} 次重试等待",
                "state_mutated": False,
            }

    # 3. 正常消费成功：标记幂等凭证，记录状态变更次数
    _IDEMPOTENCY_RECORDS[cg].add(msg.idempotency_key)
    _STATE_MUTATIONS_AUDIT[msg.idempotency_key] = _STATE_MUTATIONS_AUDIT.get(msg.idempotency_key, 0) + 1

    msg.status = MessageStatus.CONSUMED
    msg.consumed_at = now

    return {
        "success": True,
        "status": MessageStatus.CONSUMED.value,
        "message": f"消息 [{message_id}] 消费成功并提交 Offset",
        "state_mutated": True,
    }


def verify_message_idempotency(
    topic: str,
    idempotency_key: str,
    delivery_times: int = 3,
    consumer_group: str = "order_consumer_group",
) -> IdempotencyVerificationReport:
    """对同一个业务幂等凭证发起多轮重复投递压测，验证消费幂等性。"""
    suppressed_count = 0

    for i in range(delivery_times):
        mid = f"dup_{idempotency_key}_{i + 1}"
        produce_event_message(
            topic=topic,
            payload={"order_id": idempotency_key, "action": "deduct_stock", "seq": i + 1},
            idempotency_key=idempotency_key,
            consumer_group=consumer_group,
            message_id=mid,
        )
        res = consume_event_message(message_id=mid, consumer_group=consumer_group, simulate_fail=False)
        if res.get("status") == MessageStatus.DUPLICATE_SUPPRESSED.value:
            suppressed_count += 1

    mutations_count = _STATE_MUTATIONS_AUDIT.get(idempotency_key, 0)
    is_idempotent = mutations_count == 1 and suppressed_count == delivery_times - 1

    if is_idempotent:
        summary = (
            f"幂等性验证通过：共模拟重复投递 {delivery_times} 次，"
            f"仅首次发生状态变更 (1 次)，后续 {suppressed_count} 次重复投递全部被幂等凭证安全拦截！"
        )
    else:
        summary = (
            f"幂等性严重漏洞破坏：共投递 {delivery_times} 次，"
            f"导致了 {mutations_count} 次重复数据写入/扣减，未能有效抵御重复消息风险！"
        )

    return IdempotencyVerificationReport(
        idempotency_key=idempotency_key,
        topic=topic,
        consumer_group=consumer_group,
        total_deliveries=delivery_times,
        state_mutations_count=mutations_count,
        duplicate_suppressed_count=suppressed_count,
        is_idempotent=is_idempotent,
        verdict_summary=summary,
    )


def get_topic_lag_metrics() -> list[TopicLagMetric]:
    """计算各 Topic 与 ConsumerGroup 的当前积压与延迟指标。"""
    # 统计未消费与死信
    topic_groups: dict[tuple[str, str], list[EventMessageItem]] = {}
    for msg in _MESSAGES_STORE.values():
        k = (msg.topic, msg.consumer_group)
        if k not in topic_groups:
            topic_groups[k] = []
        topic_groups[k].append(msg)

    metrics: list[TopicLagMetric] = []
    now = datetime.now(timezone.utc)

    for (topic, cg), msgs in topic_groups.items():
        unconsumed = [m for m in msgs if m.status in (MessageStatus.PRODUCED, MessageStatus.RETRYING)]
        lag_count = len(unconsumed)

        if lag_count == 0:
            severity = LagSeverity.HEALTHY
            oldest_age = 0.0
        elif lag_count < 20:
            severity = LagSeverity.HEALTHY
            oldest_age = max((now - m.produced_at).total_seconds() for m in unconsumed)
        elif lag_count < 100:
            severity = LagSeverity.WARNING
            oldest_age = max((now - m.produced_at).total_seconds() for m in unconsumed)
        else:
            severity = LagSeverity.CRITICAL_BACKLOG
            oldest_age = max((now - m.produced_at).total_seconds() for m in unconsumed)

        durations = [m.lag_ms for m in msgs if m.lag_ms > 0]
        avg_proc_ms = sum(durations) / len(durations) if durations else 15.0

        metrics.append(
            TopicLagMetric(
                topic=topic,
                consumer_group=cg,
                current_lag=lag_count,
                lag_severity=severity,
                avg_processing_time_ms=avg_proc_ms,
                oldest_unconsumed_age_sec=oldest_age,
            )
        )

    return metrics


def list_dead_letter_messages() -> list[EventMessageItem]:
    """查询死信队列中的全部有毒消息。"""
    return [m for m in _MESSAGES_STORE.values() if m.status == MessageStatus.DEAD_LETTER]


def requeue_dead_letter(message_id: str) -> bool:
    """将死信重新放回排队重试队列。"""
    msg = _MESSAGES_STORE.get(message_id)
    if not msg or msg.status != MessageStatus.DEAD_LETTER:
        return False
    msg.status = MessageStatus.RETRYING
    msg.retry_count = 0
    msg.error_message = "Requeued from DLQ by operator"
    return True


def clear_event_bus() -> int:
    """清空消息总线与幂等审计数据。"""
    c = len(_MESSAGES_STORE)
    _MESSAGES_STORE.clear()
    _IDEMPOTENCY_RECORDS.clear()
    _STATE_MUTATIONS_AUDIT.clear()
    return c
