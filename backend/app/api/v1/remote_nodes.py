"""Remote Desktop Node Access Gateway: Liveness, Offline Defense & Proxy (D5)."""

from __future__ import annotations

import logging
import asyncio
import base64
import hashlib
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_engineer
from app.core.database import AsyncSessionLocal, get_db
from app.models.user import User, UserRole
from app.services.api_key_governance import validate_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/remote-nodes", tags=["在线远程受控访问"])

# In-memory node registry with heartbeat tracking
# Maps client_id -> {machine_name, origin, capabilities, last_seen, created_at}
_NODE_REGISTRY: dict[str, dict[str, Any]] = {}
_NODE_CHANNELS: dict[str, "NodeChannel"] = {}
HEARTBEAT_TIMEOUT_SECONDS = 60.0
MAX_PROXY_BYTES = 8 * 1024 * 1024


class DesktopNodeHeartbeatIn(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=64)
    machine_name: str = Field(..., max_length=64)
    local_api_origin: str | None = Field(default=None, max_length=256)
    capabilities: list[str] = Field(default_factory=list)


class DesktopNodeOut(BaseModel):
    client_id: str
    machine_name: str
    local_api_origin: str | None
    status: str  # "online" | "offline"
    last_seen_at: str
    capabilities: list[str]


class NodeChannel:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self.send_lock = asyncio.Lock()

    async def send_request(self, method: str, path: str, headers: dict[str, str], body: bytes) -> dict[str, Any]:
        request_id = uuid4().hex
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        try:
            async with self.send_lock:
                await self.websocket.send_json(
                    {
                        "type": "request",
                        "request_id": request_id,
                        "method": method,
                        "path": path,
                        "headers": headers,
                        "body": base64.b64encode(body).decode("ascii"),
                    }
                )
            return await asyncio.wait_for(future, timeout=30)
        finally:
            self.pending.pop(request_id, None)

    def close(self) -> None:
        for future in self.pending.values():
            if not future.done():
                future.set_exception(ConnectionError("Desktop node disconnected"))
        self.pending.clear()


async def _node_key_fingerprint(raw_key: str | None, db: AsyncSession, client_ip: str | None) -> str:
    if not raw_key:
        raise HTTPException(status_code=401, detail="Node API Key required")
    key = await validate_api_key(db, raw_key, client_ip=client_ip)
    user = await db.get(User, key.user_id) if key else None
    if user is None or not user.is_active or user.role != UserRole.admin:
        raise HTTPException(status_code=401, detail="Invalid node API Key")
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def require_node_key(request: Request, db: AsyncSession = Depends(get_db)) -> str:
    return await _node_key_fingerprint(
        request.headers.get("X-ATP-Api-Key"), db, request.client.host if request.client else None
    )


def _bind_node(client_id: str, fingerprint: str, machine_name: str, capabilities: list[str]) -> dict[str, Any]:
    existing = _NODE_REGISTRY.get(client_id)
    if existing and existing.get("key_fingerprint") != fingerprint:
        raise HTTPException(status_code=403, detail="Node identity is bound to another API Key")
    now_iso = datetime.now(timezone.utc).isoformat()
    entry = {
        "client_id": client_id,
        "key_fingerprint": fingerprint,
        "machine_name": machine_name,
        "local_api_origin": None,
        "capabilities": capabilities,
        "last_seen_ts": time.time(),
        "last_seen_at": now_iso,
        "created_at": existing["created_at"] if existing else now_iso,
    }
    _NODE_REGISTRY[client_id] = entry
    return entry


def _is_node_online(client_id: str, entry: dict[str, Any]) -> bool:
    return (
        client_id in _NODE_CHANNELS and time.time() - float(entry.get("last_seen_ts", 0)) <= HEARTBEAT_TIMEOUT_SECONDS
    )


def get_node_status(client_id: str) -> str:
    entry = _NODE_REGISTRY.get(client_id)
    if not entry:
        return "unknown"
    return "online" if _is_node_online(client_id, entry) else "offline"


@router.post("/heartbeat")
async def report_node_heartbeat(
    body: DesktopNodeHeartbeatIn,
    fingerprint: str = Depends(require_node_key),
) -> dict[str, Any]:
    """Refresh authenticated node metadata; only an active reverse channel is online."""
    entry = _bind_node(body.client_id, fingerprint, body.machine_name, body.capabilities)

    return {
        "status": "ok",
        "client_id": body.client_id,
        "node_status": get_node_status(body.client_id),
        "heartbeat_at": entry["last_seen_at"],
    }


@router.websocket("/connect/{client_id}")
async def connect_desktop_node(websocket: WebSocket, client_id: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            fingerprint = await _node_key_fingerprint(
                websocket.headers.get("X-ATP-Api-Key"),
                db,
                websocket.client.host if websocket.client else None,
            )
        _bind_node(client_id, fingerprint, client_id, [])
    except HTTPException:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    previous = _NODE_CHANNELS.get(client_id)
    channel = NodeChannel(websocket)
    _NODE_CHANNELS[client_id] = channel
    if previous:
        previous.close()
        try:
            await previous.websocket.close(code=4000)
        except RuntimeError:
            pass
    try:
        while True:
            frame = await websocket.receive_json()
            if frame.get("type") == "heartbeat":
                _bind_node(client_id, fingerprint, str(frame.get("machine_name") or client_id)[:64], [])
            elif frame.get("type") == "response":
                future = channel.pending.get(str(frame.get("request_id")))
                if future and not future.done():
                    future.set_result(frame)
    except WebSocketDisconnect:
        pass
    finally:
        channel.close()
        if _NODE_CHANNELS.get(client_id) is channel:
            _NODE_CHANNELS.pop(client_id, None)


@router.get("", response_model=list[DesktopNodeOut])
async def list_desktop_nodes(
    _user: User = Depends(require_engineer),
) -> list[DesktopNodeOut]:
    """List all registered desktop nodes and their online/offline state."""
    results: list[DesktopNodeOut] = []
    for cid, entry in list(_NODE_REGISTRY.items()):
        node_st = get_node_status(cid)
        results.append(
            DesktopNodeOut(
                client_id=cid,
                machine_name=entry["machine_name"],
                local_api_origin=None,
                status=node_st,
                last_seen_at=entry["last_seen_at"],
                capabilities=entry.get("capabilities", []),
            )
        )
    return results


@router.get("/{client_id}", response_model=DesktopNodeOut)
async def get_desktop_node(
    client_id: str,
    _user: User = Depends(require_engineer),
) -> DesktopNodeOut:
    """Query detail for a specific desktop node."""
    entry = _NODE_REGISTRY.get(client_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Desktop node not found")

    node_st = get_node_status(client_id)
    return DesktopNodeOut(
        client_id=client_id,
        machine_name=entry["machine_name"],
        local_api_origin=None,
        status=node_st,
        last_seen_at=entry["last_seen_at"],
        capabilities=entry.get("capabilities", []),
    )


@router.api_route(
    "/{client_id}/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def proxy_to_desktop_node(
    client_id: str,
    path: str,
    request: Request,
    _user: User = Depends(require_admin),
) -> Response:
    """Relay authorized requests over the node-initiated reverse channel."""
    entry = _NODE_REGISTRY.get(client_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Desktop node not found")

    is_online = _is_node_online(client_id, entry)
    method = request.method.upper()

    # D5 Invariant: Offline barrier
    if not is_online:
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="目标测试电脑处于离线状态，禁止执行写入操作，防止数据冲突与幽灵写入",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="目标测试电脑当前处于离线状态，无法实时读取本机项目数据与附件",
            )

    if not path.startswith("api/v1/") or ".." in path.split("/") or path.startswith("api/v1/remote-nodes"):
        raise HTTPException(status_code=400, detail="Unsupported node API path")
    body = await request.body()
    if len(body) > MAX_PROXY_BYTES:
        raise HTTPException(status_code=413, detail="Remote request exceeds channel limit")
    forward_headers = {key: val for key, val in request.headers.items() if key.lower() in {"accept", "content-type"}}
    full_path = f"/{path}"
    if request.url.query:
        full_path += f"?{request.url.query}"

    try:
        frame = await _NODE_CHANNELS[client_id].send_request(method, full_path, forward_headers, body)
        content = base64.b64decode(frame["body"], validate=True)
        if len(content) > MAX_PROXY_BYTES:
            raise ValueError("Node response exceeds channel limit")
        response_headers = {
            key: val
            for key, val in frame.get("headers", {}).items()
            if key.lower() in {"content-type", "content-disposition"}
        }
        return Response(content=content, status_code=int(frame["status"]), headers=response_headers)
    except (ConnectionError, asyncio.TimeoutError, KeyError, ValueError, RuntimeError, WebSocketDisconnect):
        raise HTTPException(status_code=502, detail="目标测试电脑通道不可用")
