"""测试领域意图语义规划服务单测 (T1.2)"""

from __future__ import annotations

from app.services.intent_semantic_prompt_planner import plan_semantic_slots


def test_plan_semantic_slots_ecommerce():
    prompt = (
        "测试用户在 Web 端浏览商品并下单，然后用 iOS 客户端完成人脸核身与支付，最后在后台数据库校验订单为 PAID 状态"
    )

    slots = plan_semantic_slots(prompt)
    assert slots.business_domain == "ecommerce"
    assert "web" in slots.protocols
    assert "ios" in slots.protocols
    assert "sql" in slots.protocols
    assert len(slots.actions) >= 3
    assert any("浏览商品" in a or "下单" in a for a in slots.actions)
    assert "order" in slots.extracted_entities or "订单" in slots.extracted_entities


def test_plan_semantic_slots_fintech():
    prompt = "接口发起转账还款申请，然后通过 gRPC 微服务校验风控余额"

    slots = plan_semantic_slots(prompt)
    assert slots.business_domain == "fintech"
    assert "http" in slots.protocols
    assert "grpc" in slots.protocols
