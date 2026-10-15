"""Scrcpy 实时视频流与零延迟触控 API 路由。

- WebSocket: /ws/scrcpy/{serial}  全双工通道：
    * 下行 (binary): 推送 30~60 FPS 裸 H.264 Annex-B 视频流
    * 上行 (JSON text): 接收前端毫秒级触控 (touch)、按键 (key)、文本输入 (text)
- POST /devices/{serial}/touch    HTTP 备用触控接口
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from jwt import InvalidTokenError
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.device_stream.manager import scrcpy_manager
from app.models.user import User

logger = logging.getLogger(__name__)

rest_router = APIRouter(tags=["devices", "device-stream"], dependencies=[Depends(get_current_user)])
ws_router = APIRouter()


async def _get_ws_user(websocket: WebSocket) -> Optional[User]:
    """校验 WebSocket 携带的 HttpOnly Cookie 或 query token。"""
    token = getattr(websocket, "cookies", {}).get(settings.ACCESS_COOKIE_NAME) or websocket.query_params.get("token")
    if not token:
        return None

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        username = payload.get("sub")
        if not username:
            return None
    except (InvalidTokenError, KeyError):
        return None

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()
            if user is None or not user.is_active:
                return None
            return user
    except Exception:
        return None


class TouchEvent(BaseModel):
    action: int = 0  # 0=down, 1=up, 2=move
    x: int
    y: int
    w: Optional[int] = None
    h: Optional[int] = None


@rest_router.post("/devices/{serial}/touch")
def send_touch(serial: str, event: TouchEvent):
    """向设备 scrcpy 控制通道毫秒级发送触控事件。"""
    try:
        scrcpy_manager.send_touch_event(serial, event.action, event.x, event.y, event.w, event.h)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@rest_router.post("/devices/{serial}/reconnect")
def reconnect_scrcpy(serial: str):
    """重新连接设备的 scrcpy 流。"""
    scrcpy_manager.ensure_device_stream(serial)
    return {"status": "ok", "serial": serial}


@ws_router.websocket("/ws/scrcpy/{serial}")
async def scrcpy_video_stream(websocket: WebSocket, serial: str):
    """全双工 WebSocket：下行推送 60FPS H.264 视频流，上行毫秒级接收触控与按键。"""
    user = await _get_ws_user(websocket)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    logger.info("Scrcpy 视频流客户端已连接: %s (user=%s)", serial, user.username)

    loop = asyncio.get_running_loop()
    stream = None

    try:
        stream = await loop.run_in_executor(None, scrcpy_manager.create_client_stream, serial)

        async def _send_video_loop():
            while True:
                chunk = await loop.run_in_executor(None, stream.get_chunk, 1.0)
                if chunk is None:
                    break
                if chunk:
                    await websocket.send_bytes(chunk)

        async def _recv_control_loop():
            while True:
                raw_text = await websocket.receive_text()
                try:
                    cmd = json.loads(raw_text)
                    cmd_type = cmd.get("type")
                    if cmd_type == "touch":
                        scrcpy_manager.send_touch_event(
                            serial,
                            int(cmd.get("action", 0)),
                            int(cmd.get("x", 0)),
                            int(cmd.get("y", 0)),
                            cmd.get("w"),
                            cmd.get("h"),
                        )
                    elif cmd_type == "key":
                        await loop.run_in_executor(
                            None, scrcpy_manager.send_key_event, serial, int(cmd.get("keycode", 0))
                        )
                    elif cmd_type == "text":
                        await loop.run_in_executor(
                            None, scrcpy_manager.send_text_event, serial, str(cmd.get("text", ""))
                        )
                except Exception as ctrl_err:
                    logger.debug("Scrcpy 控制指令处理忽略: %s", ctrl_err)

        send_task = asyncio.create_task(_send_video_loop())
        recv_task = asyncio.create_task(_recv_control_loop())

        done, pending = await asyncio.wait(
            [send_task, recv_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, (WebSocketDisconnect, asyncio.CancelledError)):
                raise exc

    except WebSocketDisconnect:
        logger.info("Scrcpy 视频流客户端断开: %s", serial)
    except Exception as e:
        logger.warning("Scrcpy 视频流异常: %s %s", serial, e)
        try:
            await websocket.close(code=4000)
        except Exception:
            pass
    finally:
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
