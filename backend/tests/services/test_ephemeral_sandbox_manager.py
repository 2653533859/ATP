"""Unit tests for C3.1 Ephemeral Multi-Protocol Mock Sandbox & Dynamic Port Manager.

Tests:
1. EphemeralPortManager conflict-free port allocation and OS socket probing
2. EphemeralSandboxInstance provisioning across HTTP, gRPC, and WebSocket schemes
3. Graceful sandbox termination and port deallocation
4. Automatic TTL expiration reaper
5. Isolated mock routing engine matching and fallback
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.services.ephemeral_sandbox_manager import (
    _PORT_MANAGER,
    _SANDBOXES,
    EphemeralPortManager,
    dispatch_sandbox_mock_request,
    list_sandboxes,
    provision_ephemeral_sandbox,
    reap_expired_sandboxes,
    terminate_ephemeral_sandbox,
)


@pytest.fixture(autouse=True)
def clean_sandbox_state():
    _SANDBOXES.clear()
    _PORT_MANAGER.allocated_ports.clear()
    yield
    _SANDBOXES.clear()
    _PORT_MANAGER.allocated_ports.clear()


def test_ephemeral_port_manager_allocation_and_release():
    mgr = EphemeralPortManager(range_start=25000, range_end=25010)

    # 1. Allocate port
    p1 = mgr.allocate_port()
    assert 25000 <= p1 <= 25010
    assert p1 in mgr.allocated_ports

    # 2. Next allocation yields different port
    p2 = mgr.allocate_port()
    assert p2 != p1
    assert p2 in mgr.allocated_ports

    # 3. Release p1
    mgr.release_port(p1)
    assert p1 not in mgr.allocated_ports


def test_provision_ephemeral_sandbox_protocols():
    # 1. HTTP Sandbox
    sbx_http = provision_ephemeral_sandbox(
        "Order Service Mock",
        protocol="http",
        ttl_seconds=120.0,
        mock_rules=[
            {
                "method": "GET",
                "path": "/api/v1/orders/101",
                "status_code": 200,
                "body": {"order_id": "ord_101", "status": "shipped"},
            }
        ],
    )
    assert sbx_http.protocol == "http"
    assert sbx_http.base_url.startswith("http://127.0.0.1:")
    assert sbx_http.status == "ready"
    assert sbx_http.is_expired is False

    # 2. WebSocket Sandbox
    sbx_ws = provision_ephemeral_sandbox("Live Stream WS Mock", protocol="websocket")
    assert sbx_ws.base_url.startswith("ws://127.0.0.1:")

    # 3. gRPC Sandbox
    sbx_grpc = provision_ephemeral_sandbox("Payment gRPC Mock", protocol="grpc")
    assert sbx_grpc.base_url.startswith("grpc://127.0.0.1:")


def test_terminate_ephemeral_sandbox():
    sbx = provision_ephemeral_sandbox("Temp Mock Sandbox", ttl_seconds=300.0)
    port = sbx.allocated_port
    assert port in _PORT_MANAGER.allocated_ports

    terminated = terminate_ephemeral_sandbox(sbx.sandbox_id)
    assert terminated.status == "terminated"
    # Port must be released
    assert port not in _PORT_MANAGER.allocated_ports

    # Terminating again is idempotent
    terminate_ephemeral_sandbox(sbx.sandbox_id)
    assert port not in _PORT_MANAGER.allocated_ports


def test_reap_expired_sandboxes():
    sbx_active = provision_ephemeral_sandbox("Active Sandbox", ttl_seconds=300.0)
    sbx_expired = provision_ephemeral_sandbox("Expired Sandbox", ttl_seconds=60.0)

    # Fast-forward expiration timestamp
    sbx_expired.expires_at = datetime.now(timezone.utc).timestamp() - 10.0
    assert sbx_expired.is_expired is True

    reaped_count = reap_expired_sandboxes()
    assert reaped_count >= 1
    assert sbx_expired.status == "expired"
    assert sbx_expired.allocated_port not in _PORT_MANAGER.allocated_ports

    # Active sandbox remains ready
    assert sbx_active.status == "ready"
    assert sbx_active.allocated_port in _PORT_MANAGER.allocated_ports

    active_list = list_sandboxes(only_active=True)
    active_ids = [s.sandbox_id for s in active_list]
    assert sbx_active.sandbox_id in active_ids
    assert sbx_expired.sandbox_id not in active_ids


def test_dispatch_sandbox_mock_request():
    sbx = provision_ephemeral_sandbox(
        "Catalog Mock",
        protocol="http",
        mock_rules=[
            {
                "method": "GET",
                "path": "/products/100",
                "status_code": 200,
                "body": {"id": 100, "name": "智能降噪耳机"},
            }
        ],
    )

    # 1. Matched request
    res = dispatch_sandbox_mock_request(sbx.sandbox_id, "GET", "/products/100")
    assert res["matched"] is True
    assert res["status_code"] == 200
    assert res["body"]["name"] == "智能降噪耳机"

    # 2. Unmatched path -> returns 404
    res_404 = dispatch_sandbox_mock_request(sbx.sandbox_id, "GET", "/unknown/path")
    assert res_404["matched"] is False
    assert res_404["status_code"] == 404

    # 3. Terminate sandbox -> dispatch fails
    terminate_ephemeral_sandbox(sbx.sandbox_id)
    with pytest.raises(RuntimeError, match="已终止或过期"):
        dispatch_sandbox_mock_request(sbx.sandbox_id, "GET", "/products/100")
