"""工作流跨节点动态变量总线单测 (T1.2)"""

from __future__ import annotations

from app.services.workflow_context_variable_bus import (
    WorkflowVariableBus,
    extract_field_by_path,
    resolve_node_inputs,
)


def test_extract_field_by_path():
    data = {
        "node_http": {
            "status_code": 200,
            "body": {
                "order_id": "ORD_123456",
                "items": [
                    {"sku": "SKU_001", "price": 99.0},
                    {"sku": "SKU_002", "price": 120.0},
                ],
            },
        },
        "env": {"BASE_URL": "https://test.internal"},
    }

    # 1. 基础多层点分提取
    assert extract_field_by_path(data, "node_http.status_code") == 200
    assert extract_field_by_path(data, "node_http.body.order_id") == "ORD_123456"

    # 2. 数组下标切片提取 (同时支持 .0. 与 [0])
    assert extract_field_by_path(data, "node_http.body.items[0].sku") == "SKU_001"
    assert extract_field_by_path(data, "node_http.body.items.1.price") == 120.0

    # 3. 不存在属性返回默认值
    assert extract_field_by_path(data, "node_http.not_exist", default="fallback") == "fallback"
    assert extract_field_by_path(data, "node_http.body.items[99].sku", default=None) is None


def test_variable_bus_resolve_placeholders():
    bus = WorkflowVariableBus(
        {
            "node_auth": {"token": "jwt_token_secret_888"},
            "node_order": {"order_id": "ORD_998877", "amount": 299.5},
            "env": {"HOST": "api.shop.com"},
        }
    )

    # 1. 单纯占位符直换原对象类型
    assert bus.resolve_template_string("{{node_order.amount}}") == 299.5

    # 2. 字符串内嵌插值
    interpolated = bus.resolve_template_string("Bearer {{node_auth.token}} for order {{node_order.order_id}}")
    assert interpolated == "Bearer jwt_token_secret_888 for order ORD_998877"

    # 3. 递归结构体字典/列表解析
    raw_node_config = {
        "headers": {"Authorization": "Bearer {{node_auth.token}}"},
        "url": "https://{{env.HOST}}/v1/pay",
        "payload": {
            "order_id": "{{node_order.order_id}}",
            "amount": "{{node_order.amount}}",
        },
        "tags": ["order:{{node_order.order_id}}", "prod"],
    }

    resolved = resolve_node_inputs(raw_node_config, bus)
    assert resolved["headers"]["Authorization"] == "Bearer jwt_token_secret_888"
    assert resolved["url"] == "https://api.shop.com/v1/pay"
    assert resolved["payload"]["order_id"] == "ORD_998877"
    assert resolved["payload"]["amount"] == 299.5
    assert resolved["tags"][0] == "order:ORD_998877"
