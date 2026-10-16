"""Unit tests for Live Contract Schema Extractor Service (T3.1)."""

from __future__ import annotations

import json
import pytest

from app.services.live_contract_schema_extractor import (
    batch_extract_contracts_from_traffic,
    clear_extracted_contracts,
    extract_contract_from_traffic,
    generate_protobuf_from_schema,
    get_contract_by_endpoint,
    get_extracted_contract,
    infer_json_schema_from_samples,
    infer_type_and_format,
    list_extracted_contracts,
)


@pytest.fixture(autouse=True)
def clean_contracts():
    clear_extracted_contracts()
    yield
    clear_extracted_contracts()


def test_infer_type_and_format():
    """验证单值的基础类型与语义格式识别。"""
    assert infer_type_and_format(100) == ("integer", "int32")
    assert infer_type_and_format(3000000000) == ("integer", "int64")
    assert infer_type_and_format(99.5) == ("number", "double")
    assert infer_type_and_format(True) == ("boolean", None)
    assert infer_type_and_format("2026-10-16T12:00:00Z") == ("string", "date-time")
    assert infer_type_and_format("550e8400-e29b-41d4-a716-446655440000") == ("string", "uuid")
    assert infer_type_and_format("dev@example.com") == ("string", "email")
    assert infer_type_and_format("hello") == ("string", None)
    assert infer_type_and_format(None) == ("null", None)


def test_infer_json_schema_from_multi_samples():
    """验证从多条真实样本中自适应归纳推导字段类型、必填性与枚举。"""
    samples = [
        {
            "order_id": 1001,
            "status": "PAID",
            "amount": 100,  # int
            "buyer_email": "buyer1@test.com",
            "coupon": "VIP10",
        },
        {
            "order_id": 1002,
            "status": "PENDING",
            "amount": 150.5,  # float -> 提升为 number
            "buyer_email": "buyer2@test.com",
            # 缺失 coupon (非必填)
        },
        {
            "order_id": 1003,
            "status": "PAID",
            "amount": 200,
            "buyer_email": "buyer3@test.com",
            "coupon": "VIP20",
        },
    ]

    schema = infer_json_schema_from_samples(samples)

    assert schema["type"] == "object"
    props = schema["properties"]

    # 1. order_id: 必填 integer
    assert props["order_id"]["type"] == "integer"
    assert "order_id" in schema["required"]

    # 2. buyer_email: 必填 email
    assert props["buyer_email"]["type"] == "string"
    assert props["buyer_email"]["format"] == "email"
    assert "buyer_email" in schema["required"]

    # 3. amount: 类型归一提升为 number
    assert props["amount"]["type"] == "number"

    # 4. status: 自动归纳为枚举 ["PAID", "PENDING"]
    assert "enum" in props["status"]
    assert set(props["status"]["enum"]) == {"PAID", "PENDING"}

    # 5. coupon: 缺失样本，不可为 required
    assert "coupon" not in schema["required"]


def test_generate_protobuf_from_schema():
    """验证将 JSON Schema 转换为符合规范的 Protobuf 3 IDL。"""
    schema = {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer", "format": "int64"},
            "amount": {"type": "number"},
            "status": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
    }

    proto = generate_protobuf_from_schema("OrderRequest", schema)

    assert 'syntax = "proto3";' in proto
    assert "message Orderrequest {" in proto or "message OrderRequest {" in proto
    assert "double amount = 1;" in proto
    assert "int64 order_id = 2;" in proto
    assert "string status = 3;" in proto
    assert "repeated string tags = 4;" in proto


def test_extract_contract_from_traffic():
    """验证端到端提取接口契约、Query 参数与不同响应码 Schema。"""
    traffic_samples = [
        {
            "protocol": "HTTP",
            "method": "POST",
            "path_or_endpoint": "/api/v1/orders/checkout",
            "query_params": {"source": "mobile"},
            "request_body": json.dumps({"order_id": 1001, "amount": 99.0}),
            "response_status_code": 200,
            "response_body": json.dumps({"code": 0, "status": "CREATED"}),
        },
        {
            "protocol": "HTTP",
            "method": "POST",
            "path_or_endpoint": "/api/v1/orders/checkout",
            "query_params": {"source": "web"},
            "request_body": json.dumps({"order_id": 1002, "amount": 199.0}),
            "response_status_code": 200,
            "response_body": json.dumps({"code": 0, "status": "CREATED"}),
        },
        {
            "protocol": "HTTP",
            "method": "POST",
            "path_or_endpoint": "/api/v1/orders/checkout",
            "query_params": {},
            "request_body": json.dumps({"order_id": 1003, "amount": 299.0}),
            "response_status_code": 400,
            "response_body": json.dumps({"code": 4001, "error": "Invalid coupon"}),
        },
    ]

    contract = extract_contract_from_traffic(
        endpoint="POST /api/v1/orders/checkout",
        traffic_samples=traffic_samples,
    )

    assert contract.contract_id.startswith("ct_")
    assert contract.method == "POST"
    assert contract.path == "/api/v1/orders/checkout"
    assert contract.samples_count == 3

    # 请求体 Schema
    assert "order_id" in contract.request_schema["properties"]
    assert "amount" in contract.request_schema["properties"]

    # 响应体分类 Schema: 包含 200 与 400 两个响应分支
    assert "200" in contract.response_schemas
    assert "400" in contract.response_schemas
    assert "status" in contract.response_schemas["200"]["properties"]
    assert "error" in contract.response_schemas["400"]["properties"]

    # Protobuf 自动生成
    assert 'syntax = "proto3";' in contract.protobuf_definition

    # 检索查回
    fetched = get_extracted_contract(contract.contract_id)
    assert fetched is not None
    assert fetched.contract_id == contract.contract_id

    by_ep = get_contract_by_endpoint("POST /api/v1/orders/checkout")
    assert by_ep is not None
    assert by_ep.contract_id == contract.contract_id


def test_batch_extract_contracts_from_traffic():
    """验证批量从海量流量中按端点归类并推导多接口契约。"""
    records = [
        {"method": "GET", "path_or_endpoint": "/api/v1/users", "response_status_code": 200, "response_body": "{}"},
        {"method": "POST", "path_or_endpoint": "/api/v1/orders", "response_status_code": 200, "response_body": "{}"},
    ]

    report = batch_extract_contracts_from_traffic(records)
    assert report.total_traffic_analyzed == 2
    assert report.contracts_extracted_count == 2
    assert len(list_extracted_contracts()) == 2
