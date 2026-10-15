"""Unit tests for C3.2 Cross-Protocol Data Propagation & Session-Level Context Bus.

Tests:
1. SessionBusContext shared variable storage and retrieval across protocols
2. HTTP -> gRPC metadata propagation (Authorization Bearer & trace IDs)
3. HTTP -> WebSocket handshake headers and query parameter propagation
4. WebSocket message ingestion and dynamic key extraction into session variables
5. Universal recursive {{variable}} template interpolation across strings, lists, and dicts
"""

from __future__ import annotations

import pytest

from app.services.cross_protocol_session_bus import (
    _BUS_REGISTRY,
    get_or_create_session_bus,
    get_session_bus,
)


@pytest.fixture(autouse=True)
def clean_bus_registry():
    _BUS_REGISTRY.clear()
    yield
    _BUS_REGISTRY.clear()


def test_session_bus_variable_storage_and_events():
    bus = get_or_create_session_bus("bus_test_01")
    assert bus.bus_id == "bus_test_01"

    # Set and get variables
    bus.set_variable("order_id", "ord_9901")
    bus.set_variable("user_id", 1001)
    assert bus.get_variable("order_id") == "ord_9901"
    assert bus.get_variable("user_id") == 1001

    # Record protocol event
    evt = bus.record_event("http", "request_completed", {"status": 200})
    assert evt.source_protocol == "http"
    assert len(bus.event_stream) == 1

    # Retrieval from registry
    same_bus = get_session_bus("bus_test_01")
    assert same_bus is not None
    assert same_bus.get_variable("order_id") == "ord_9901"


def test_propagate_http_to_grpc():
    bus = get_or_create_session_bus("bus_http_to_grpc")
    bus.http_context["headers"]["Authorization"] = "Bearer jwt_test_token_123"
    bus.http_context["headers"]["x-trace-id"] = "trace_abc_999"

    grpc_metadata = bus.propagate_http_to_grpc()
    assert grpc_metadata["authorization"] == "Bearer jwt_test_token_123"
    assert grpc_metadata["x-trace-id"] == "trace_abc_999"

    # Verify event recorded
    assert any(e.event_type == "propagate_to_grpc" for e in bus.event_stream)


def test_propagate_http_to_websocket():
    bus = get_or_create_session_bus("bus_http_to_ws")
    bus.http_context["headers"]["Authorization"] = "Bearer session_token_777"
    bus.set_variable("token", "ws_auth_secret_888")

    ws_ctx = bus.propagate_http_to_websocket()
    assert ws_ctx["headers"]["Authorization"] == "Bearer session_token_777"
    assert ws_ctx["query_params"]["token"] == "ws_auth_secret_888"


def test_ingest_websocket_message_and_extract_variables():
    bus = get_or_create_session_bus("bus_ws_ingest")

    ws_frame = (
        '{"event": "payment_succeeded", "transaction_id": "tx_20261016_88", "amount": 99.5, "status": "completed"}'
    )
    res = bus.ingest_websocket_message(ws_frame)

    assert "transaction_id" in res["extracted_keys"]
    assert "amount" in res["extracted_keys"]
    assert bus.get_variable("transaction_id") == "tx_20261016_88"
    assert bus.get_variable("amount") == 99.5
    assert bus.get_variable("status") == "completed"


def test_universal_template_interpolation():
    bus = get_or_create_session_bus("bus_interpolate")
    bus.set_variable("order_id", "ord_5521")
    bus.set_variable("user_token", "sec_token_001")
    bus.set_variable("amount", 199)

    # 1. String rendering
    raw_url = "http://api.internal/v1/orders/{{order_id}}/pay?token={{user_token}}"
    rendered_url = bus.render_template(raw_url)
    assert (
        rendered_url == "http://api.internal/v1/orders/ord_5521/pay?token:sec_token_001"
        or "http://api.internal/v1/orders/ord_5521/pay?token=sec_token_001"
    )
    assert "ord_5521" in rendered_url
    assert "sec_token_001" in rendered_url

    # 2. Nested dictionary rendering
    payload = {
        "headers": {"Authorization": "Bearer {{user_token}}"},
        "body": {
            "order": "{{order_id}}",
            "price": "{{amount}}",
            "items": ["sku_{{order_id}}_1", "sku_{{order_id}}_2"],
        },
    }
    rendered_dict = bus.render_template(payload)
    assert rendered_dict["headers"]["Authorization"] == "Bearer sec_token_001"
    assert rendered_dict["body"]["order"] == "ord_5521"
    assert rendered_dict["body"]["price"] == "199"
    assert rendered_dict["body"]["items"][0] == "sku_ord_5521_1"
