"""Remote node authentication, offline behavior, and reverse-channel tests."""

import base64
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from app.api.deps import require_admin, require_engineer
from app.api.v1.remote_nodes import _NODE_CHANNELS, _NODE_REGISTRY, require_node_key, router
from app.models.bootstrap import load_all_models
from app.models.user import User, UserRole
from app.services.remote_node_agent import _node_ws_url, _start_private_tunnel, dispatch_node_request

load_all_models()


@pytest.mark.asyncio
async def test_node_key_requires_active_cloud_admin(monkeypatch):
    from fastapi import HTTPException
    from app.api.v1.remote_nodes import _node_key_fingerprint

    class Db:
        def __init__(self, role):
            self.role = role

        async def get(self, *_args):
            return User(
                id=1, username="node", email="node@test.local", hashed_password="x", role=self.role, is_active=True
            )

    async def valid_key(*_args, **_kwargs):
        return SimpleNamespace(user_id=1)

    monkeypatch.setattr("app.api.v1.remote_nodes.validate_api_key", valid_key)
    with pytest.raises(HTTPException) as missing:
        await _node_key_fingerprint(None, Db(UserRole.admin), None)
    assert missing.value.status_code == 401
    with pytest.raises(HTTPException) as viewer:
        await _node_key_fingerprint("node-secret", Db(UserRole.viewer), None)
    assert viewer.value.status_code == 401
    fingerprint = await _node_key_fingerprint("node-secret", Db(UserRole.admin), None)
    assert fingerprint != "node-secret"
    assert len(fingerprint) == 64


@pytest.fixture
def node_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    admin = User(id=1, username="admin", email="admin@test.local", hashed_password="x", role=UserRole.admin)
    app.dependency_overrides[require_engineer] = lambda: admin
    app.dependency_overrides[require_admin] = lambda: admin
    yield app
    _NODE_REGISTRY.clear()
    _NODE_CHANNELS.clear()


@pytest.mark.asyncio
async def test_heartbeat_requires_key_binds_identity_and_does_not_trust_origin(node_app):
    body = {
        "client_id": "win-box-1",
        "machine_name": "DESKTOP-ALPHA",
        "local_api_origin": "http://127.0.0.1:8001",
    }
    async with AsyncClient(transport=ASGITransport(app=node_app), base_url="http://test") as client:
        assert (await client.post("/api/v1/remote-nodes/heartbeat", json=body)).status_code == 401
        node_app.dependency_overrides[require_node_key] = lambda: "first-key"
        heartbeat = await client.post("/api/v1/remote-nodes/heartbeat", json=body)
        assert heartbeat.status_code == 200
        assert heartbeat.json()["node_status"] == "offline"  # Heartbeat alone cannot create a proxy target.
        nodes = (await client.get("/api/v1/remote-nodes")).json()
        assert nodes[0]["local_api_origin"] is None
        node_app.dependency_overrides[require_node_key] = lambda: "different-key"
        assert (await client.post("/api/v1/remote-nodes/heartbeat", json=body)).status_code == 403


@pytest.mark.asyncio
async def test_offline_node_rejects_reads_and_writes(node_app):
    _NODE_REGISTRY["win-offline"] = {
        "machine_name": "PC",
        "last_seen_ts": 0,
        "last_seen_at": "2026-10-27T00:00:00Z",
        "capabilities": [],
    }
    async with AsyncClient(transport=ASGITransport(app=node_app), base_url="http://test") as client:
        assert (await client.get("/api/v1/remote-nodes/win-offline/proxy/api/v1/projects")).status_code == 503
        assert (await client.post("/api/v1/remote-nodes/win-offline/proxy/api/v1/projects")).status_code == 409


@pytest.mark.asyncio
async def test_online_proxy_uses_channel_without_forwarding_cloud_credentials(node_app):
    _NODE_REGISTRY["win-live"] = {
        "machine_name": "PC",
        "last_seen_ts": time.time(),
        "last_seen_at": "2026-10-27T00:00:00Z",
        "capabilities": [],
    }

    class Channel:
        async def send_request(self, method, path, headers, body):
            assert method == "GET"
            assert path == "/api/v1/projects"
            assert not {"cookie", "authorization"}.intersection(key.lower() for key in headers)
            assert body == b""
            return {
                "status": 200,
                "headers": {"content-type": "application/json"},
                "body": base64.b64encode(b'[{"id":1}]').decode("ascii"),
            }

    _NODE_CHANNELS["win-live"] = Channel()
    async with AsyncClient(transport=ASGITransport(app=node_app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/remote-nodes/win-live/proxy/api/v1/projects",
            headers={"Authorization": "Bearer cloud-token", "Cookie": "session=cloud"},
        )
        assert response.status_code == 200
        assert response.json() == [{"id": 1}]


@pytest.mark.asyncio
async def test_local_dispatch_uses_node_signed_token(monkeypatch):
    app = FastAPI()

    @app.get("/api/v1/projects")
    async def protected(request: Request):
        return {"authorization": request.headers.get("Authorization"), "cloud_cookie": request.headers.get("Cookie")}

    async def token():
        return "local-signed-token"

    monkeypatch.setattr("app.services.remote_node_agent._local_admin_token", token)
    frame = {
        "request_id": "request-1",
        "method": "GET",
        "path": "/api/v1/projects",
        "headers": {"Authorization": "Bearer cloud-token", "Cookie": "session=cloud"},
        "body": "",
    }
    result = await dispatch_node_request(app, frame)
    assert result["status"] == 200
    content = base64.b64decode(result["body"])
    assert b"local-signed-token" in content
    assert b"cloud-token" not in content
    assert b"session=cloud" not in content


def test_remote_channel_requires_tls_outside_loopback():
    assert _node_ws_url("https://cloud.example.test", "win-1").startswith("wss://")
    assert _node_ws_url("http://127.0.0.1:8000", "win-1").startswith("ws://")
    with pytest.raises(ValueError):
        _node_ws_url("http://192.168.3.196:8000", "win-1")


@pytest.mark.asyncio
async def test_private_tunnel_requires_matching_loopback_origin(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "REMOTE_NODE_SSH_HOST", "cloud.example.test")
    monkeypatch.setattr(settings, "REMOTE_NODE_TUNNEL_PORT", 18000)
    monkeypatch.setattr(settings, "CLOUD_SYNC_URL", "http://192.168.3.196:8000")
    with pytest.raises(ValueError, match="loopback"):
        await _start_private_tunnel()


def test_reverse_websocket_roundtrip(node_app, monkeypatch):
    """A cloud request reaches the connected node and receives its reply."""

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    async def fingerprint(*_args):
        return "node-key-fingerprint"

    monkeypatch.setattr("app.api.v1.remote_nodes.AsyncSessionLocal", Session)
    monkeypatch.setattr("app.api.v1.remote_nodes._node_key_fingerprint", fingerprint)
    with TestClient(node_app) as client:
        with client.websocket_connect(
            "/api/v1/remote-nodes/connect/win-roundtrip",
            headers={"X-ATP-Api-Key": "private-node-key"},
        ) as websocket:
            websocket.send_json({"type": "heartbeat", "machine_name": "WINDOWS-PC"})
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(client.get, "/api/v1/remote-nodes/win-roundtrip/proxy/api/v1/projects")
                request = websocket.receive_json()
                assert request["type"] == "request"
                assert request["path"] == "/api/v1/projects"
                websocket.send_json(
                    {
                        "type": "response",
                        "request_id": request["request_id"],
                        "status": 200,
                        "headers": {"content-type": "application/json"},
                        "body": base64.b64encode(b'{"from":"windows"}').decode("ascii"),
                    }
                )
                response = future.result(timeout=5)
                assert response.status_code == 200
                assert response.json() == {"from": "windows"}
