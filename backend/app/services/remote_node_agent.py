"""Windows-initiated, authenticated reverse channel to the cloud gateway."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.local_machine_identity import get_machine_id, get_machine_name
from app.core.security import create_access_token
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)
MAX_PROXY_BYTES = 8 * 1024 * 1024


def _node_ws_url(origin: str, client_id: str) -> str:
    parsed = urlsplit(origin.rstrip("/"))
    if parsed.scheme == "https":
        scheme = "wss"
    elif parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
        scheme = "ws"
    else:
        raise ValueError("Remote node access requires HTTPS or a loopback development endpoint")
    if not parsed.netloc or parsed.username or parsed.password or parsed.path not in {"", "/"}:
        raise ValueError("CLOUD_SYNC_URL must be an origin without credentials or path")
    return f"{scheme}://{parsed.netloc}/api/v1/remote-nodes/connect/{client_id}"


async def _start_private_tunnel() -> asyncio.subprocess.Process | None:
    """Open an SSH local forward without exposing the cloud API key or a Windows port."""
    if not settings.REMOTE_NODE_SSH_HOST:
        return None
    target = urlsplit(settings.CLOUD_SYNC_URL)
    if target.hostname not in {"127.0.0.1", "localhost"} or target.port != settings.REMOTE_NODE_TUNNEL_PORT:
        raise ValueError("CLOUD_SYNC_URL must match the configured loopback SSH tunnel")
    key_file = Path(settings.REMOTE_NODE_SSH_KEY_FILE)
    known_hosts = Path(settings.REMOTE_NODE_SSH_KNOWN_HOSTS)
    if not settings.REMOTE_NODE_SSH_USER or not key_file.is_file() or not known_hosts.is_file():
        raise ValueError("Remote node SSH identity or known_hosts is missing")
    try:
        _, existing = await asyncio.open_connection("127.0.0.1", settings.REMOTE_NODE_TUNNEL_PORT)
    except OSError:
        pass
    else:
        existing.close()
        await existing.wait_closed()
        raise ValueError("SSH tunnel port is already occupied")
    args = (
        "ssh",
        "-N",
        "-L",
        f"127.0.0.1:{settings.REMOTE_NODE_TUNNEL_PORT}:127.0.0.1:8000",
        "-p",
        str(settings.REMOTE_NODE_SSH_PORT),
        "-i",
        str(key_file),
        "-o",
        "BatchMode=yes",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=3",
        f"{settings.REMOTE_NODE_SSH_USER}@{settings.REMOTE_NODE_SSH_HOST}",
    )
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        creationflags=flags,
    )
    for _ in range(20):
        if process.returncode is not None:
            raise ConnectionError("SSH tunnel exited before opening its local port")
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", settings.REMOTE_NODE_TUNNEL_PORT)
            writer.close()
            await writer.wait_closed()
            return process
        except OSError:
            await asyncio.sleep(0.25)
    process.terminate()
    await process.wait()
    raise ConnectionError("SSH tunnel did not become ready")


async def _local_admin_token() -> str:
    """Mint a short-lived token signed by this Windows node, never by the cloud."""
    async with AsyncSessionLocal() as db:
        user = await db.scalar(
            select(User).where(User.role == UserRole.admin, User.is_active.is_(True)).order_by(User.id)
        )
    if user is None:
        raise RuntimeError("No active local admin for remote node access")
    return create_access_token(user.username)


async def dispatch_node_request(app: FastAPI, frame: dict) -> dict:
    """Execute a cloud-authorized request in the local app with local credentials."""
    request_id = str(frame.get("request_id", ""))
    path = str(frame.get("path", ""))
    parsed = urlsplit(path)
    if (
        not path.startswith("/api/v1/")
        or parsed.scheme
        or parsed.netloc
        or ".." in parsed.path.split("/")
        or parsed.path.startswith("/api/v1/remote-nodes")
    ):
        return {"type": "response", "request_id": request_id, "status": 400, "headers": {}, "body": ""}
    try:
        body = base64.b64decode(frame.get("body", ""), validate=True)
        if len(body) > MAX_PROXY_BYTES:
            raise ValueError("Request exceeds channel limit")
        token = await _local_admin_token()
        headers = {
            key: val for key, val in frame.get("headers", {}).items() if key.lower() in {"accept", "content-type"}
        }
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Requested-With"] = "XMLHttpRequest"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://local-node") as client:
            response = await client.request(
                str(frame.get("method", "GET")), path, headers=headers, content=body, timeout=30
            )
        if len(response.content) > MAX_PROXY_BYTES:
            raise ValueError("Response exceeds channel limit")
        response_headers = {
            key: val for key, val in response.headers.items() if key.lower() in {"content-type", "content-disposition"}
        }
        return {
            "type": "response",
            "request_id": request_id,
            "status": response.status_code,
            "headers": response_headers,
            "body": base64.b64encode(response.content).decode("ascii"),
        }
    except (httpx.TimeoutException, asyncio.TimeoutError):
        return {"type": "response", "request_id": request_id, "status": 504, "headers": {}, "body": ""}
    except Exception:
        logger.warning("Local dispatch of remote request %s failed", request_id, exc_info=True)
        return {"type": "response", "request_id": request_id, "status": 502, "headers": {}, "body": ""}


async def run_local_node_agent(app: FastAPI, stop_event: asyncio.Event) -> None:
    """Maintain an outbound channel; no inbound Windows port is exposed."""
    if not settings.CLOUD_SYNC_URL or not settings.CLOUD_SYNC_API_KEY:
        return
    from websockets.asyncio.client import connect

    try:
        url = _node_ws_url(settings.CLOUD_SYNC_URL, get_machine_id())
    except ValueError:
        logger.warning("Remote node channel disabled: configure an HTTPS cloud origin")
        return

    async def pause() -> None:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=5)
        except TimeoutError:
            pass

    while not stop_event.is_set():
        tunnel: asyncio.subprocess.Process | None = None
        try:
            tunnel = await _start_private_tunnel()
            async with connect(url, additional_headers={"X-ATP-Api-Key": settings.CLOUD_SYNC_API_KEY}) as ws:

                async def heartbeat() -> None:
                    while not stop_event.is_set():
                        await ws.send(json.dumps({"type": "heartbeat", "machine_name": get_machine_name()}))
                        try:
                            await asyncio.wait_for(stop_event.wait(), timeout=20)
                        except TimeoutError:
                            pass

                heartbeat_task = asyncio.create_task(heartbeat())
                try:
                    async for raw in ws:
                        frame = json.loads(raw)
                        if frame.get("type") == "request":
                            response = await dispatch_node_request(app, frame)
                            await ws.send(json.dumps(response))
                        if stop_event.is_set():
                            break
                finally:
                    heartbeat_task.cancel()
                    await asyncio.gather(heartbeat_task, return_exceptions=True)
        except Exception:
            logger.warning("Remote node channel disconnected; retrying", exc_info=True)
        finally:
            if tunnel is not None and tunnel.returncode is None:
                tunnel.terminate()
                try:
                    await asyncio.wait_for(tunnel.wait(), timeout=5)
                except TimeoutError:
                    tunnel.kill()
                    await tunnel.wait()
        await pause()
