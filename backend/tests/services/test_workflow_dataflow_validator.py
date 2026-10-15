"""Unit tests for T3.2 Bi-Directional Context Variable Dataflow Topology Validator.

Tests:
1. extract_consumed_variables finds all template tokens across nested structures
2. extract_produced_variables extracts keys from node extractions
3. Valid sequential and diamond dataflows pass verification with lineage mapping
4. Reverse-order references (consuming downstream node outputs) are caught
5. Undeclared / phantom variables are detected
6. Unused produced variables warnings
"""

from __future__ import annotations

import pytest

from app.services.workflow_dataflow_validator import (
    WorkflowDataflowError,
    extract_consumed_variables,
    extract_produced_variables,
    validate_workflow_dataflow_topology,
)


def test_extract_consumed_variables():
    payload = {
        "url": "https://api.example.com/orders/{{order_id}}",
        "headers": {"Authorization": "Bearer {{auth_token}}"},
        "nested": {
            "tags": ["env:{{env_name}}", "{{tag_id}}"],
            "count": 123,
        },
    }
    consumed = extract_consumed_variables(payload)
    assert consumed == {"order_id", "auth_token", "env_name", "tag_id"}


def test_extract_produced_variables():
    config = {
        "extractions": {
            "token": "$.auth.token",
            "user_id": "$.data.user_id",
        }
    }
    produced = extract_produced_variables(config)
    assert produced == {"token", "user_id"}


def test_validate_dataflow_valid_diamond_workflow():
    nodes = [
        {
            "id": "node_login",
            "name": "用户登录",
            "depends_on": [],
            "config": {
                "extractions": {"auth_token": "token", "account_id": "id"},
            },
        },
        {
            "id": "node_query_sql",
            "name": "查询数据库",
            "depends_on": ["node_login"],
            "config": {
                "query": "SELECT balance FROM accounts WHERE id = {{account_id}}",
                "extractions": {"user_balance": "balance"},
            },
        },
        {
            "id": "node_check_redis",
            "name": "校验缓存",
            "depends_on": ["node_login"],
            "config": {
                "key": "session:{{auth_token}}",
            },
        },
        {
            "id": "node_mobile_confirm",
            "name": "移动端核验",
            "depends_on": ["node_query_sql", "node_check_redis"],
            "config": {
                "expected_text": "余额: {{user_balance}}, Trace: {{trace_id}}",
            },
        },
    ]

    res = validate_workflow_dataflow_topology(nodes, strict=True)
    assert res["valid"] is True
    assert res["missing_variable_count"] == 0
    assert res["reverse_reference_count"] == 0
    assert len(res["variable_lineage"]) >= 3

    # Check lineage for user_balance
    balance_lineage = next(item for item in res["variable_lineage"] if item["variable"] == "user_balance")
    assert balance_lineage["producer_node"] == "node_query_sql"
    assert "node_mobile_confirm" in balance_lineage["consumers"]


def test_validate_dataflow_detects_reverse_order_reference():
    # Node 1 tries to use variable 'order_id' which is only produced by downstream Node 2!
    nodes = [
        {
            "id": "node_1",
            "name": "先发起的请求",
            "depends_on": [],
            "config": {
                "url": "https://api.example.com/checkout/{{order_id}}",
            },
        },
        {
            "id": "node_2",
            "name": "后创建的订单",
            "depends_on": ["node_1"],
            "config": {
                "extractions": {"order_id": "id"},
            },
        },
    ]

    # Non-strict mode: returns structured issues
    res = validate_workflow_dataflow_topology(nodes, strict=False)
    assert res["valid"] is False
    assert res["reverse_reference_count"] == 1
    assert res["reverse_references"][0]["variable"] == "order_id"
    assert res["reverse_references"][0]["consumer_node"] == "node_1"
    assert res["reverse_references"][0]["producer_node"] == "node_2"

    # Strict mode: raises WorkflowDataflowError
    with pytest.raises(WorkflowDataflowError) as exc_info:
        validate_workflow_dataflow_topology(nodes, strict=True)
    assert "后续或非父节点" in str(exc_info.value)


def test_validate_dataflow_detects_undeclared_phantom_variable():
    nodes = [
        {
            "id": "node_1",
            "name": "数据节点",
            "depends_on": [],
            "config": {
                "query": "SELECT * FROM users WHERE status = '{{undeclared_status}}'",
            },
        }
    ]

    res = validate_workflow_dataflow_topology(nodes, strict=False)
    assert res["valid"] is False
    assert res["missing_variable_count"] == 1
    assert res["missing_variables"][0]["variable"] == "undeclared_status"

    with pytest.raises(WorkflowDataflowError) as exc_info:
        validate_workflow_dataflow_topology(nodes, strict=True)
    assert "未声明的未知变量" in str(exc_info.value)


def test_validate_dataflow_detects_unused_produced_variables():
    nodes = [
        {
            "id": "node_1",
            "name": "生产者节点",
            "depends_on": [],
            "config": {
                "extractions": {"used_var": "val1", "never_used_var": "val2"},
            },
        },
        {
            "id": "node_2",
            "name": "消费者节点",
            "depends_on": ["node_1"],
            "config": {
                "text": "Using {{used_var}}",
            },
        },
    ]

    res = validate_workflow_dataflow_topology(nodes, strict=False)
    assert res["valid"] is True
    assert res["unused_variable_count"] == 1
    assert res["unused_variables"][0]["variable"] == "never_used_var"
