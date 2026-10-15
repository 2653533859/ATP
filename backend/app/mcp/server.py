"""ATP MCP (Model Context Protocol) Server implementation.

Implements JSON-RPC 2.0 request handling for:
- initialize
- ping
- tools/list
- tools/call

Can be mounted into FastAPI HTTP endpoints or run in stdio mode via `python -m app.mcp`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.mcp.tools import TOOLS_MANIFEST, execute_tool
from app.models.user import User

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "atp-mcp-server"
SERVER_VERSION = "2.5.0"

# JSON-RPC 2.0 standard error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class MCPServer:
    """Core Model Context Protocol engine."""

    def __init__(self, name: str = SERVER_NAME, version: str = SERVER_VERSION):
        self.name = name
        self.version = version

    async def handle_request(self, db: AsyncSession, user: User, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Process a single JSON-RPC 2.0 request or notification."""
        req_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") or {}

        # Notifications (no id)
        if req_id is None:
            if method == "notifications/initialized":
                logger.info("MCP client initialized notification received")
            return None

        if not method or not isinstance(method, str):
            return self._build_error(req_id, INVALID_REQUEST, "Invalid request: missing method")

        try:
            if method == "initialize":
                return self._build_success(req_id, self._handle_initialize(params))
            if method == "ping":
                return self._build_success(req_id, {})
            if method == "tools/list":
                return self._build_success(req_id, {"tools": TOOLS_MANIFEST})
            if method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments") or {}
                if not tool_name:
                    return self._build_error(req_id, INVALID_PARAMS, "Missing tool name in tools/call")
                result = await execute_tool(db, user, tool_name, arguments)
                return self._build_success(req_id, result)

            return self._build_error(req_id, METHOD_NOT_FOUND, f"Method not found: {method}")

        except Exception as exc:
            logger.exception("MCP server error processing method %s: %s", method, exc)
            return self._build_error(req_id, INTERNAL_ERROR, f"Internal error: {str(exc)}")

    def _handle_initialize(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {
                    "listChanged": False,
                }
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
        }

    @staticmethod
    def _build_success(req_id: Any, result: Any) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }

    @staticmethod
    def _build_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    async def run_stdio(self) -> None:
        """Run MCP server in stdio mode (line-delimited JSON-RPC)."""
        logger.info("Starting ATP MCP Server in stdio mode...")
        loop = asyncio.get_running_loop()

        # In standalone stdio mode, resolve administrative user for tool execution
        from app.models.user import UserRole

        admin_user = User(
            id=1,
            username="mcp-agent",
            email="mcp@atp.local",
            role=UserRole.admin,
            hashed_password="***",
            is_active=True,
        )

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            line_bytes = await reader.readline()
            if not line_bytes:
                break

            line_str = line_bytes.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                payload = json.loads(line_str)
            except json.JSONDecodeError:
                err_resp = self._build_error(None, PARSE_ERROR, "Parse error: invalid JSON")
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
                continue

            async with AsyncSessionLocal() as db:
                response = await self.handle_request(db, admin_user, payload)
                if response is not None:
                    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                    sys.stdout.flush()


atp_mcp_server = MCPServer()
