"""Remote Desktop Node Access Gateway: Liveness, Offline Defense & Proxy (D5)."""

from __future__ import annotations

import logging
import asyncio
import base64
import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin, require_engineer
from app.core.database import AsyncSessionLocal, get_db
from app.models.audit import AuditLog
from app.models.project import Project
from app.models.remote_node_grant import RemoteNodeGrant
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject
from app.services.api_key_governance import validate_api_key
from app.services.audit import write_audit_log

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


class NodeGrantCreateIn(BaseModel):
    subject_type: Literal["user", "project"]
    subject_id: int = Field(..., ge=1)
    access_level: Literal["read_only", "read_write"]


class NodeGrantOut(BaseModel):
    id: int
    node_client_id: str
    subject_type: str
    subject_id: int
    subject_name: str
    access_level: str
    created_by: str
    created_at: str
    revoked_at: str | None = None
    revoked_by: str | None = None


# D5 授权模型：GET/HEAD/OPTIONS 为读，其余为写（与离线屏障的写入集合一致）。
GRANT_READ_ONLY = "read_only"
GRANT_READ_WRITE = "read_write"
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


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


async def _write_node_audit(*, action: str, user: User | None, client_id: str, detail: str) -> None:
    """Best-effort audit for node authorization decisions (own session, own commit)."""
    try:
        async with AsyncSessionLocal() as audit_db:
            audit_db.add(
                AuditLog(
                    action=action,
                    resource_type="remote_node",
                    user_id=user.id if user else None,
                    username=user.username if user else "",
                    detail=f"node_client_id={client_id}; {detail}",
                )
            )
            await audit_db.commit()
    except Exception:
        logger.warning("Failed to persist remote node audit entry", exc_info=True)


async def _effective_node_access(db: AsyncSession, user: User, client_id: str) -> str | None:
    """Resolve the highest active access level for one user on one node.

    Admin passes globally. Otherwise active direct grants and grants of the
    user's projects are unioned; a viewer (global or project member) is
    clamped to read-only.
    """
    if user.role == UserRole.admin:
        return GRANT_READ_WRITE
    levels = list(
        (
            await db.scalars(
                select(RemoteNodeGrant.access_level).where(
                    RemoteNodeGrant.node_client_id == client_id,
                    RemoteNodeGrant.revoked_at.is_(None),
                    RemoteNodeGrant.user_id == user.id,
                )
            )
        ).all()
    )
    project_rows = (
        await db.execute(
            select(RemoteNodeGrant.access_level, UserProject.role)
            .join(UserProject, UserProject.project_id == RemoteNodeGrant.project_id)
            .where(
                RemoteNodeGrant.node_client_id == client_id,
                RemoteNodeGrant.revoked_at.is_(None),
                UserProject.user_id == user.id,
            )
        )
    ).all()
    for level, project_role in project_rows:
        if project_role == ProjectRole.viewer and level == GRANT_READ_WRITE:
            levels.append(GRANT_READ_ONLY)
        else:
            levels.append(level)
    if not levels:
        return None
    if user.role == UserRole.viewer:
        return GRANT_READ_ONLY
    return GRANT_READ_WRITE if GRANT_READ_WRITE in levels else GRANT_READ_ONLY


async def require_node_proxy_access(
    request: Request,
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """D5 authorization: admins pass; others need an active grant; writes need read-write."""
    method = request.method.upper()
    if current_user.role == UserRole.admin:
        return current_user
    level = await _effective_node_access(db, current_user, client_id)
    if level is None:
        await _write_node_audit(
            action="remote_node_access_denied",
            user=current_user,
            client_id=client_id,
            detail=f"{method} {request.url.path} denied: no active grant",
        )
        raise HTTPException(status_code=403, detail="No authorization to access this desktop node")
    if method in WRITE_METHODS and level != GRANT_READ_WRITE:
        await _write_node_audit(
            action="remote_node_access_denied",
            user=current_user,
            client_id=client_id,
            detail=f"{method} {request.url.path} denied: read-only grant",
        )
        raise HTTPException(status_code=403, detail="Read-only authorization cannot perform write operations")
    return current_user


async def _node_key_fingerprint(raw_key: str | None, db: AsyncSession, client_ip: str | None) -> str:
    if not raw_key:
        raise HTTPException(status_code=401, detail="Node API Key required")
    key = await validate_api_key(db, raw_key, client_ip=client_ip)
    user = await db.get(User, key.user_id) if key else None
    if (
        user is None
        or not user.is_active
        or user.role != UserRole.admin
        or key.role != "admin"
        or key.project_id is not None
        or key.environment_id is not None
    ):
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
    current_user: User = Depends(require_node_proxy_access),
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
    body_parts: list[bytes] = []
    body_size = 0
    async for chunk in request.stream():
        body_size += len(chunk)
        if body_size > MAX_PROXY_BYTES:
            raise HTTPException(status_code=413, detail="Remote request exceeds channel limit")
        body_parts.append(chunk)
    body = b"".join(body_parts)
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
        response = Response(content=content, status_code=int(frame["status"]), headers=response_headers)
    except (ConnectionError, asyncio.TimeoutError, KeyError, ValueError, RuntimeError, WebSocketDisconnect):
        raise HTTPException(status_code=502, detail="目标测试电脑通道不可用")

    # Traceability: every relayed write is audited with the node-side status code.
    if method in WRITE_METHODS:
        await _write_node_audit(
            action="remote_node_proxy_write",
            user=current_user,
            client_id=client_id,
            detail=f"{method} /{path} -> {response.status_code}",
        )
    return response


def _grant_subject_type(grant: RemoteNodeGrant) -> str:
    return "user" if grant.user_id is not None else "project"


def _grant_out(grant: RemoteNodeGrant, *, subject_name: str, creator: str, revoker: str | None) -> NodeGrantOut:
    return NodeGrantOut(
        id=grant.id,
        node_client_id=grant.node_client_id,
        subject_type=_grant_subject_type(grant),
        subject_id=grant.user_id if grant.user_id is not None else int(grant.project_id or 0),
        subject_name=subject_name,
        access_level=grant.access_level,
        created_by=creator,
        created_at=grant.created_at.isoformat() if grant.created_at else "",
        revoked_at=grant.revoked_at.isoformat() if grant.revoked_at else None,
        revoked_by=revoker,
    )


async def _grant_outputs(db: AsyncSession, grants: list[RemoteNodeGrant]) -> list[NodeGrantOut]:
    user_ids = {g.user_id for g in grants if g.user_id is not None}
    user_ids |= {g.created_by_id for g in grants if g.created_by_id is not None}
    user_ids |= {g.revoked_by_id for g in grants if g.revoked_by_id is not None}
    project_ids = {g.project_id for g in grants if g.project_id is not None}
    names: dict[int, str] = {}
    if user_ids:
        names = {user.id: user.username for user in (await db.scalars(select(User).where(User.id.in_(user_ids)))).all()}
    project_names: dict[int, str] = {}
    if project_ids:
        project_names = {
            project.id: project.name
            for project in (await db.scalars(select(Project).where(Project.id.in_(project_ids)))).all()
        }
    results: list[NodeGrantOut] = []
    for grant in grants:
        if grant.user_id is not None:
            subject_name = names.get(grant.user_id, f"user#{grant.user_id}")
        else:
            subject_name = project_names.get(int(grant.project_id or 0), f"project#{grant.project_id}")
        creator = names.get(grant.created_by_id, "") if grant.created_by_id is not None else ""
        revoker = names.get(grant.revoked_by_id) if grant.revoked_by_id is not None else None
        results.append(_grant_out(grant, subject_name=subject_name, creator=creator, revoker=revoker))
    return results


@router.get("/{client_id}/grants", response_model=list[NodeGrantOut])
async def list_node_grants(
    client_id: str,
    include_revoked: bool = False,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
) -> list[NodeGrantOut]:
    """List grants of one desktop node (active only unless include_revoked is set)."""
    stmt = select(RemoteNodeGrant).where(RemoteNodeGrant.node_client_id == client_id)
    if not include_revoked:
        stmt = stmt.where(RemoteNodeGrant.revoked_at.is_(None))
    grants = list((await db.scalars(stmt.order_by(RemoteNodeGrant.created_at, RemoteNodeGrant.id))).all())
    return await _grant_outputs(db, grants)


@router.post("/{client_id}/grants", response_model=NodeGrantOut, status_code=status.HTTP_201_CREATED)
async def create_node_grant(
    client_id: str,
    body: NodeGrantCreateIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> NodeGrantOut:
    """Grant read-only or read-write access on one node to a user or a whole project."""
    if client_id not in _NODE_REGISTRY:
        raise HTTPException(status_code=404, detail="Desktop node not found")
    if body.subject_type == "user":
        subject = await db.get(User, body.subject_id)
        if subject is None:
            raise HTTPException(status_code=404, detail="User not found")
        if not subject.is_active:
            raise HTTPException(status_code=400, detail="Inactive users cannot be authorized")
        if subject.role == UserRole.viewer and body.access_level == GRANT_READ_WRITE:
            raise HTTPException(status_code=400, detail="Viewer-role users can only be granted read-only access")
        duplicate = await db.scalar(
            select(RemoteNodeGrant.id).where(
                RemoteNodeGrant.node_client_id == client_id,
                RemoteNodeGrant.revoked_at.is_(None),
                RemoteNodeGrant.user_id == body.subject_id,
            )
        )
        grant = RemoteNodeGrant(
            node_client_id=client_id,
            user_id=body.subject_id,
            access_level=body.access_level,
            created_by_id=current_user.id,
        )
        subject_name = subject.username
    else:
        project = await db.get(Project, body.subject_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        duplicate = await db.scalar(
            select(RemoteNodeGrant.id).where(
                RemoteNodeGrant.node_client_id == client_id,
                RemoteNodeGrant.revoked_at.is_(None),
                RemoteNodeGrant.project_id == body.subject_id,
            )
        )
        grant = RemoteNodeGrant(
            node_client_id=client_id,
            project_id=body.subject_id,
            access_level=body.access_level,
            created_by_id=current_user.id,
        )
        subject_name = project.name
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="An active grant already exists for this subject")
    db.add(grant)
    await write_audit_log(
        db,
        action="remote_node_grant_created",
        resource_type="remote_node",
        user_id=current_user.id,
        username=current_user.username,
        detail=(
            f"node_client_id={client_id}; {body.subject_type}_id={body.subject_id}; "
            f"access_level={body.access_level}"
        ),
        ip_address=request.client.host if request.client else "",
    )
    await db.commit()
    await db.refresh(grant)
    return _grant_out(grant, subject_name=subject_name, creator=current_user.username, revoker=None)


@router.delete("/{client_id}/grants/{grant_id}", response_model=NodeGrantOut)
async def revoke_node_grant(
    client_id: str,
    grant_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> NodeGrantOut:
    """Revoke one grant (soft delete, fully auditable); the record stays queryable."""
    grant = await db.get(RemoteNodeGrant, grant_id)
    if grant is None or grant.node_client_id != client_id:
        raise HTTPException(status_code=404, detail="Grant not found")
    if grant.revoked_at is not None:
        raise HTTPException(status_code=409, detail="Grant is already revoked")
    grant.revoked_at = datetime.now(timezone.utc)
    grant.revoked_by_id = current_user.id
    await write_audit_log(
        db,
        action="remote_node_grant_revoked",
        resource_type="remote_node",
        user_id=current_user.id,
        username=current_user.username,
        detail=f"node_client_id={client_id}; grant_id={grant_id}",
        ip_address=request.client.host if request.client else "",
    )
    await db.commit()
    await db.refresh(grant)
    outputs = await _grant_outputs(db, [grant])
    return outputs[0]
