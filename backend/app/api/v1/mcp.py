"""FastAPI router exposing MCP (Model Context Protocol) endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.mcp import TOOLS_MANIFEST, atp_mcp_server
from app.models.user import User

router = APIRouter(prefix="/mcp", tags=["MCP 智能体工具协议"])


@router.get("/status")
def get_mcp_status() -> dict[str, Any]:
    """查询 ATP MCP Server 的协议版本与就绪状态。"""
    return {
        "server": atp_mcp_server.name,
        "version": atp_mcp_server.version,
        "protocol_version": "2024-11-05",
        "tools_count": len(TOOLS_MANIFEST),
    }


@router.get("/tools")
def list_mcp_tools(_: User = Depends(get_current_user)) -> dict[str, Any]:
    """查询 ATP 当前开放的 MCP 标准工具清单及 JSON Schema。"""
    return {"tools": TOOLS_MANIFEST}


@router.post("/rpc")
async def handle_mcp_rpc(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """处理 MCP 标准 JSON-RPC 2.0 请求（支持 initialize, ping, tools/list, tools/call）。"""
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid JSON payload: {exc}") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JSON-RPC payload must be a JSON object")

    rpc_response = await atp_mcp_server.handle_request(db, current_user, payload)
    if rpc_response is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return None

    return rpc_response
