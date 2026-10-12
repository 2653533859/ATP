"""远程设备接入点（Device Agent）API 与 Agent WebSocket 端点。

- ``WS /ws/device-agent``：B 机 Agent 的反向隧道长连接
- ``GET /device-agents/``：接入点列表（前端设备中心展示）
- ``DELETE /device-agents/{agent_id}``：删除离线接入点并释放隧道端口映射
- ``POST /device-agents/{agent_id}/link-probe``：主动测量 B→A 吞吐
- ``GET /device-agents/agent-script``：下载 Agent 脚本
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocket

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import sync_engine as engine
from app.core.security import decode_token
from app.device_agents.tunnel_hub import tunnel_hub
from app.models.device_agent import RemoteAgent, RemoteAgentDevice
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()
ws_router = APIRouter()

AGENT_SCRIPT_PATH = Path(__file__).resolve().parents[4] / "scripts" / "device_agent.py"


def _authenticate_ws_token(websocket: WebSocket) -> Optional[str]:
    """校验 WS 握手头或 Query 参数中的认证 Token。"""
    auth_header = websocket.headers.get("authorization") or ""
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "token" in websocket.query_params:
        token = websocket.query_params["token"].strip()

    if not token:
        if settings.ATP_LOCAL_MODE:
            return "local_admin"
        return None

    if token == settings.APP_SECRET_KEY:
        return "admin"

    try:
        payload = decode_token(token)
        sub = payload.get("sub")
        if sub:
            return str(sub)
    except Exception:
        pass

    if settings.ATP_LOCAL_MODE:
        return "local_agent_user"
    return None


@ws_router.websocket("/ws/device-agent")
async def device_agent_ws(websocket: WebSocket):
    """Agent 反向隧道长连接：鉴权通过后交由 TunnelHub 托管。"""
    username = _authenticate_ws_token(websocket)
    await websocket.accept()
    if username is None:
        try:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": (
                            "鉴权失败：请在启动 Agent 时提供有效的认证 Token"
                            "（Authorization: Bearer <token> 或 --token <token>）"
                        ),
                    },
                    ensure_ascii=False,
                )
            )
        except Exception:
            pass
        await websocket.close(code=4401)
        return
    await tunnel_hub.handle_session(websocket, token_user=username)


@router.get("/")
def list_device_agents(current_user: User = Depends(get_current_user)):
    """接入点列表（数据库记录 + 在线会话状态叠加）。"""
    del current_user
    return {"items": tunnel_hub.list_agents()}


@router.post("/{agent_id}/link-probe")
async def probe_device_agent_link(agent_id: int, current_user: User = Depends(get_current_user)):
    """主动测量该接入点 B→A 上行吞吐。"""
    del current_user
    try:
        return await tunnel_hub.probe_agent_bandwidth(agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc))
    except ConnectionError as exc:
        raise HTTPException(status_code=400, detail=f"探测中断：{exc}")


@router.get("/agent-script")
def download_agent_script(current_user: User = Depends(get_current_user)):
    """下载设备接入助手脚本（B 机运行）。"""
    del current_user
    if not AGENT_SCRIPT_PATH.exists():
        raise HTTPException(status_code=404, detail="Agent 脚本不存在")
    return FileResponse(
        path=str(AGENT_SCRIPT_PATH),
        media_type="text/x-python",
        filename="device_agent.py",
    )


@router.delete("/{agent_id}")
def delete_device_agent(
    agent_id: int,
    current_user: User = Depends(get_current_user),
):
    """删除离线接入点及其设备端口映射（释放隧道端口）。"""
    with Session(engine) as session:
        agent = session.scalar(select(RemoteAgent).where(RemoteAgent.id == agent_id))
        if agent is None:
            raise HTTPException(status_code=404, detail="接入点不存在")
        if tunnel_hub.is_agent_online(agent.name):
            raise HTTPException(
                status_code=400,
                detail="接入点当前在线，无法删除；请先停止 B 机上的 Agent 进程",
            )

        agent_name = str(agent.name)
        operator = str(getattr(current_user, "username", "?") or "?")
        mappings = session.scalars(select(RemoteAgentDevice).where(RemoteAgentDevice.agent_id == agent_id)).all()
        released_ports = sorted(int(m.tunnel_port) for m in mappings)
        for mapping in mappings:
            session.delete(mapping)
        session.delete(agent)
        session.commit()

        logger.info(
            "删除远程接入点: id=%s name=%s released_ports=%s by=%s",
            agent_id,
            agent_name,
            released_ports,
            operator,
        )
        return {
            "message": f"接入点 {agent_name} 已删除",
            "released_ports": released_ports,
        }
