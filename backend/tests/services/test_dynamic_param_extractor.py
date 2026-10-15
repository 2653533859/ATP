"""Unit tests for T1.2 Dynamic Parameter Dependency Extraction and Placeholder Replacement.

Tests:
1. _extract_leaf_candidates extracts nested keys and JSONPaths while filtering noise values
2. extract_and_parameterize_traffic_stream detects token in headers and replaces with placeholder
3. extract_and_parameterize_traffic_stream detects order_id in URL path and query params
4. extract_and_parameterize_traffic_stream detects parameter dependencies in JSON request bodies
5. Producer steps receive structured extraction rules (type=jsonpath, variable, expression)
"""

from __future__ import annotations

from app.services.dynamic_param_extractor import (
    _extract_leaf_candidates,
    extract_and_parameterize_traffic_stream,
)


def test_extract_leaf_candidates():
    payload = {
        "code": 200,
        "message": "success",
        "data": {
            "token": "eyJhbGciOiJIUzI1NiJ9.user_token_999",
            "user": {
                "user_id": 9527,
                "is_active": True,
                "status": "ok",
            },
            "roles": ["admin", "editor"],
        },
    }

    candidates = _extract_leaf_candidates(payload)
    paths = {c[0]: (c[1], c[2]) for c in candidates}

    # Token and user_id should be extracted
    assert "$.data.token" in paths
    assert paths["$.data.token"][0] == "eyJhbGciOiJIUzI1NiJ9.user_token_999"
    assert paths["$.data.token"][1] == "token"

    assert "$.data.user.user_id" in paths
    assert paths["$.data.user.user_id"][0] == 9527

    # Ignored values (200, "success", True, "ok") should be filtered
    assert "$.code" not in paths
    assert "$.message" not in paths
    assert "$.data.user.is_active" not in paths
    assert "$.data.user.status" not in paths


def test_extract_and_parameterize_auth_token_header():
    # Step 0: Login -> returns token
    # Step 1: User Profile -> uses Bearer <token> in Authorization header
    entries = [
        {
            "method": "POST",
            "path": "/api/v1/auth/login",
            "url": "https://api.example.com/api/v1/auth/login",
            "request_body": {"username": "alice", "password": "password"},
            "response_body": {
                "code": 0,
                "data": {"token": "secure_token_secret_xyz123"},
            },
        },
        {
            "method": "GET",
            "path": "/api/v1/user/profile",
            "url": "https://api.example.com/api/v1/user/profile",
            "headers": {"Authorization": "Bearer secure_token_secret_xyz123"},
            "response_body": {"username": "alice", "tier": "gold"},
        },
    ]

    res = extract_and_parameterize_traffic_stream(entries)
    deps = res["discovered_dependencies"]
    assert len(deps) == 1
    assert deps[0]["producer_step"] == 0
    assert deps[0]["consumer_step"] == 1
    assert deps[0]["variable"] == "token"
    assert deps[0]["jsonpath"] == "$.data.token"
    assert deps[0]["location"] == "header(Authorization)"

    # Check that downstream consumer header was parameterized
    consumer = res["parameterized_entries"][1]
    assert consumer["headers"]["Authorization"] == "Bearer {{token}}"

    # Check that producer has extraction configured
    producer = res["parameterized_entries"][0]
    assert len(producer["extractions"]) == 1
    assert producer["extractions"][0]["variable"] == "token"
    assert producer["extractions"][0]["expression"] == "$.data.token"


def test_extract_and_parameterize_order_id_in_path_and_query():
    # Step 0: Create Order -> returns {"order_id": 888999}
    # Step 1: Order Details -> GET /api/v1/orders/888999
    # Step 2: Payment Query -> GET /api/v1/payments?order_ref=888999
    entries = [
        {
            "method": "POST",
            "path": "/api/v1/orders",
            "url": "https://api.example.com/api/v1/orders",
            "response_body": {"order_id": 888999, "status": "created"},
        },
        {
            "method": "GET",
            "path": "/api/v1/orders/888999",
            "url": "https://api.example.com/api/v1/orders/888999",
            "response_body": {"id": 888999, "items": []},
        },
        {
            "method": "GET",
            "path": "/api/v1/payments",
            "url": "https://api.example.com/api/v1/payments?order_ref=888999",
            "query_params": {"order_ref": "888999"},
            "response_body": {"paid": False},
        },
    ]

    res = extract_and_parameterize_traffic_stream(entries)
    param_entries = res["parameterized_entries"]

    # Step 1 path and url should be parameterized
    assert param_entries[1]["path"] == "/api/v1/orders/{{order_id}}"
    assert param_entries[1]["url"] == "https://api.example.com/api/v1/orders/{{order_id}}"

    # Step 2 query param should be parameterized
    assert param_entries[2]["query_params"]["order_ref"] == "{{order_id}}"

    # Step 0 producer has extractions
    assert param_entries[0]["extractions"][0]["variable"] == "order_id"
    assert param_entries[0]["extractions"][0]["expression"] == "$.order_id"


def test_extract_and_parameterize_body_nested_dependency():
    # Step 0: Create Item -> returns {"item_code": "ITEM-PROD-2026"}
    # Step 1: Checkout -> POST request_body has {"items": [{"code": "ITEM-PROD-2026", "qty": 1}]}
    entries = [
        {
            "method": "POST",
            "path": "/api/v1/items",
            "response_body": {"item_code": "ITEM-PROD-2026"},
        },
        {
            "method": "POST",
            "path": "/api/v1/checkout",
            "request_body": {
                "items": [{"code": "ITEM-PROD-2026", "qty": 1}],
                "payment": "alipay",
            },
            "response_body": {"success": True},
        },
    ]

    res = extract_and_parameterize_traffic_stream(entries)
    consumer_body = res["parameterized_entries"][1]["request_body"]
    assert consumer_body["items"][0]["code"] == "{{item_code}}"
    assert res["discovered_dependencies"][0]["location"] == "request_body"
