"""Unit Tests for Event Bus Dead-Letter and Idempotency Guard (T2.3)。"""

from __future__ import annotations

import pytest

from app.services.event_bus_deadletter_idempotency_guard import (
    LagSeverity,
    MessageStatus,
    clear_event_bus,
    consume_event_message,
    get_topic_lag_metrics,
    list_dead_letter_messages,
    produce_event_message,
    requeue_dead_letter,
    verify_message_idempotency,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_event_bus()
    yield
    clear_event_bus()


def test_produce_and_consume_event_message_normal():
    msg = produce_event_message(
        topic="order.created",
        payload={"order_id": "ord_101", "amount": 99.0},
        idempotency_key="idem_101",
        consumer_group="order_handler",
    )
    assert msg.status == MessageStatus.PRODUCED
    assert msg.message_id.startswith("msg_")

    res = consume_event_message(msg.message_id, consumer_group="order_handler")
    assert res["success"] is True
    assert res["status"] == MessageStatus.CONSUMED.value
    assert res["state_mutated"] is True
    assert msg.status == MessageStatus.CONSUMED


def test_idempotent_duplicate_delivery_suppression():
    # 验证同一幂等凭证被重复投递 4 次，仅 1 次实际发生变更，其余 3 次被安全拦截
    report = verify_message_idempotency(
        topic="inventory.deduct",
        idempotency_key="order_sku_999",
        delivery_times=4,
        consumer_group="inventory_service",
    )

    assert report.is_idempotent is True
    assert report.total_deliveries == 4
    assert report.state_mutations_count == 1
    assert report.duplicate_suppressed_count == 3
    assert "幂等性验证通过" in report.verdict_summary


def test_dead_letter_queue_and_requeue():
    msg = produce_event_message(
        topic="payment.notify",
        payload={"pay_id": "p_001"},
        max_retries=3,
    )

    # 模拟第 1 次失败 -> RETRYING
    r1 = consume_event_message(msg.message_id, simulate_fail=True, error_reason="DB lock timeout")
    assert r1["status"] == MessageStatus.RETRYING.value
    assert msg.retry_count == 1

    # 模拟第 2 次失败 -> RETRYING
    r2 = consume_event_message(msg.message_id, simulate_fail=True, error_reason="DB lock timeout")
    assert r2["status"] == MessageStatus.RETRYING.value
    assert msg.retry_count == 2

    # 模拟第 3 次失败 -> 达到 max_retries=3 -> 转入 DEAD_LETTER
    r3 = consume_event_message(msg.message_id, simulate_fail=True, error_reason="DB dead lock")
    assert r3["status"] == MessageStatus.DEAD_LETTER.value
    assert msg.status == MessageStatus.DEAD_LETTER

    # 查询死信队列
    dlqs = list_dead_letter_messages()
    assert len(dlqs) == 1
    assert dlqs[0].message_id == msg.message_id

    # 死信重放入队
    requeued = requeue_dead_letter(msg.message_id)
    assert requeued is True
    assert msg.status == MessageStatus.RETRYING
    assert msg.retry_count == 0


def test_topic_lag_metrics():
    # 生产 25 条消息且不消费 -> 触发积压统计
    for i in range(25):
        produce_event_message(
            topic="high_throughput.events",
            payload={"idx": i},
            consumer_group="batch_worker",
        )

    metrics = get_topic_lag_metrics()
    assert len(metrics) >= 1
    m = next(x for x in metrics if x.topic == "high_throughput.events")
    assert m.current_lag == 25
    assert m.lag_severity in (LagSeverity.HEALTHY, LagSeverity.WARNING)
