"""Scrcpy 实时视频流与零延迟触控 API 路由。

- WebSocket: /ws/scrcpy/{serial}  全双工通道：
    * 下行 (binary): 推送 30~60 FPS 裸 H.264 Annex-B 视频流
    * 上行 (JSON text): 接收前端毫秒级触控 (touch)、按键 (key)、文本输入 (text)
- POST /devices/{serial}/touch    HTTP 备用触控接口
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from jwt import InvalidTokenError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_engineer
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.security import decode_token
from app.device_stream.manager import scrcpy_manager
from app.models.device import Device, DeviceStatus
from app.models.user import User, UserRole
from app.services.device_leases import get_active_device_lease, lease_is_active
from app.services.scrcpy_relay import (
    ScrcpyRelayError,
    open_remote_scrcpy_stream,
    request_remote_scrcpy_reconnect,
)

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


def _require_scrcpy_allowed() -> None:
    if settings.ANDROID_MULTI_NODE_ENABLED or (
        not settings.ATP_LOCAL_MODE and settings.ADB_SCAN_MODE.strip().lower() == "worker"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="multi_node_feature_disabled: 节点 Worker 模式下暂不支持 Scrcpy 直连流，请使用截图轮询",
        )


@rest_router.post("/devices/{serial}/touch")
def send_touch(serial: str, event: TouchEvent, _=Depends(require_engineer)):
    """向设备 scrcpy 控制通道毫秒级发送触控事件。"""
    _require_scrcpy_allowed()
    try:
        scrcpy_manager.send_touch_event(serial, event.action, event.x, event.y, event.w, event.h)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@rest_router.post("/devices/{serial}/reconnect")
def reconnect_scrcpy(serial: str, _=Depends(require_engineer)):
    """重新连接设备的 scrcpy 流。"""
    _require_scrcpy_allowed()
    scrcpy_manager.ensure_device_stream(serial)
    return {"status": "ok", "serial": serial}


def _use_remote_worker_stream() -> bool:
    if settings.ATP_LOCAL_MODE:
        return False
    return bool(settings.ANDROID_MULTI_NODE_ENABLED or settings.ADB_SCAN_MODE.strip().lower() == "worker")


async def _resolve_remote_worker_target(device: Device) -> tuple[str, int | None]:
    from app.services.android_worker_registry import (
        AndroidWorkerRegistryError,
        get_android_worker,
        list_android_workers,
    )

    claimed_worker = (getattr(device, "worker_id", None) or "").strip()
    if settings.ANDROID_MULTI_NODE_ENABLED:
        if not claimed_worker:
            raise ScrcpyRelayError("device_unclaimed", "设备尚未认领归属节点，请先在设备管理中认领")
        try:
            worker_info = await get_android_worker(claimed_worker)
        except AndroidWorkerRegistryError as exc:
            raise ScrcpyRelayError("worker_registry_unavailable", f"Worker 注册中心不可用: {exc}") from exc
        if not worker_info:
            raise ScrcpyRelayError("worker_offline", f"设备所属节点 '{claimed_worker}' 当前离线")
        raw_gen = worker_info.get("instance_generation")
        return claimed_worker, int(raw_gen) if raw_gen is not None else None

    if claimed_worker and claimed_worker != "local":
        try:
            worker_info = await get_android_worker(claimed_worker)
        except AndroidWorkerRegistryError as exc:
            raise ScrcpyRelayError("worker_registry_unavailable", f"Worker 注册中心不可用: {exc}") from exc
        if not worker_info:
            raise ScrcpyRelayError("worker_offline", f"设备所属节点 '{claimed_worker}' 当前离线")
        raw_gen = worker_info.get("instance_generation")
        return claimed_worker, int(raw_gen) if raw_gen is not None else None

    try:
        workers = await list_android_workers()
    except AndroidWorkerRegistryError as exc:
        raise ScrcpyRelayError("worker_registry_unavailable", f"Worker 注册中心不可用: {exc}") from exc
    if not workers:
        raise ScrcpyRelayError("worker_offline", "当前无在线的 Android Worker 节点")
    chosen = workers[0]
    raw_gen = chosen.get("instance_generation")
    return str(chosen["worker_id"]), int(raw_gen) if raw_gen is not None else None


def _http_exception_from_relay_error(exc: ScrcpyRelayError) -> HTTPException:
    if exc.code == "device_unclaimed":
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{exc.code}: {exc.message}")
    if exc.code == "scrcpy_reconnect_timeout":
        return HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=f"{exc.code}: {exc.message}")
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"{exc.code}: {exc.message}")


async def _verify_ws_control_permission(
    *,
    user: User,
    device_id: int,
    cmd: dict[str, Any],
    fallback_token: str | None,
    lease_cache: dict[str, Any],
) -> None:
    if user.role not in (UserRole.admin, UserRole.engineer):
        raise PermissionError("当前账号角色无权向设备发送实时控制指令")
    if settings.ATP_LOCAL_MODE:
        return

    token = str(cmd.get("lease_token") or fallback_token or "").strip()
    if not token:
        raise PermissionError("设备控制需要先获取有效租约")

    cmd_type = str(cmd.get("type") or "").strip().lower()
    is_drag_move = cmd_type == "touch" and int(cmd.get("action", 0)) == 2
    now_mono = time.monotonic()
    if is_drag_move and lease_cache.get("token") == token and now_mono < float(lease_cache.get("valid_until", 0.0)):
        return

    async with AsyncSessionLocal() as db:
        lease = await get_active_device_lease(db, device_id, token)
    if lease is None or not lease_is_active(lease):
        lease_cache.clear()
        raise PermissionError("设备租约不存在或已过期，请重新获取租约")

    lease_cache["token"] = token
    lease_cache["valid_until"] = now_mono + 2.0


@rest_router.post("/devices/by-id/{device_id}/stream/reconnect")
async def reconnect_scrcpy_by_device_id(
    device_id: int,
    force: bool = Query(default=True, description="是否强制重建底层 Scrcpy 推流会话"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    """按设备 ID 重新连接或重启 Scrcpy 极速流（支持本地直连与远程 Android Worker 中继）。"""
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    if device.status == DeviceStatus.offline:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="设备离线")

    if _use_remote_worker_stream():
        try:
            worker_id, generation = await _resolve_remote_worker_target(device)
            ack = await request_remote_scrcpy_reconnect(
                worker_id,
                device.serial,
                expected_generation=generation,
                force=force,
            )
        except ScrcpyRelayError as exc:
            raise _http_exception_from_relay_error(exc) from exc
        return {
            "status": "ok",
            "mode": "worker_relay",
            "device_id": device_id,
            "serial": device.serial,
            "worker_id": worker_id,
            "width": ack.get("width", 0),
            "height": ack.get("height", 0),
        }

    def _local_reconnect():
        if force:
            scrcpy_manager._cleanup_device(device.serial)
        return scrcpy_manager.ensure_device_stream(device.serial)

    try:
        dev_info = await asyncio.to_thread(_local_reconnect)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Scrcpy 重连失败: {exc}") from exc
    return {
        "status": "ok",
        "mode": "local",
        "device_id": device_id,
        "serial": device.serial,
        "width": getattr(dev_info, "screen_width", 0),
        "height": getattr(dev_info, "screen_height", 0),
    }


@ws_router.websocket("/ws/scrcpy/devices/{device_id}")
async def scrcpy_device_video_stream(
    websocket: WebSocket,
    device_id: int,
    lease_token: str | None = Query(default=None),
    reconnect: bool = Query(default=False),
):
    """按设备 ID 建立全双工 Scrcpy WebSocket（自动路由本地直连或远程 Android Worker Redis 中继）。"""
    user = await _get_ws_user(websocket)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    async with AsyncSessionLocal() as db:
        device = await db.get(Device, device_id)
    if device is None:
        await websocket.close(code=4004, reason="device_not_found")
        return
    if device.status == DeviceStatus.offline:
        await websocket.close(code=4009, reason="device_offline")
        return

    use_relay = _use_remote_worker_stream()
    await websocket.accept()
    logger.info(
        "Scrcpy 设备流连接建立: device_id=%s serial=%s mode=%s user=%s",
        device_id,
        device.serial,
        "relay" if use_relay else "local",
        user.username,
    )

    loop = asyncio.get_running_loop()
    remote_stream = None
    local_stream = None
    lease_cache: dict[str, Any] = {}
    force_restart = bool(reconnect and user.role in (UserRole.admin, UserRole.engineer))

    async def _send_ws_error_and_close(code: str, message: str, ws_code: int = 4008) -> None:
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "code": code, "message": message}, ensure_ascii=False)
            )
        except Exception:
            pass
        try:
            await websocket.close(code=ws_code, reason=code[:60])
        except Exception:
            pass

    try:
        if use_relay:
            try:
                worker_id, generation = await _resolve_remote_worker_target(device)
                remote_stream = await open_remote_scrcpy_stream(
                    worker_id,
                    device.serial,
                    expected_generation=generation,
                    force_restart=force_restart,
                )
            except ScrcpyRelayError as exc:
                logger.warning("Scrcpy 中继建立失败 device_id=%s (%s): %s", device_id, exc.code, exc.message)
                await _send_ws_error_and_close(
                    exc.code,
                    exc.message,
                    ws_code=4009 if exc.code == "device_unclaimed" else 4008,
                )
                return

            if remote_stream.metadata:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "metadata",
                            "device_id": device_id,
                            "serial": device.serial,
                            "worker_id": worker_id,
                            "width": int(remote_stream.metadata.get("width", 0) or 0),
                            "height": int(remote_stream.metadata.get("height", 0) or 0),
                            "device_name": str(remote_stream.metadata.get("device_name", "") or ""),
                        },
                        ensure_ascii=False,
                    )
                )
        else:

            def _open_local():
                if force_restart:
                    scrcpy_manager._cleanup_device(device.serial)
                return scrcpy_manager.create_client_stream(device.serial)

            try:
                local_stream = await loop.run_in_executor(None, _open_local)
            except Exception as exc:
                logger.warning("Scrcpy 本地流建立失败 device_id=%s: %s", device_id, exc)
                await _send_ws_error_and_close("scrcpy_start_failed", f"Scrcpy 启动失败: {exc}")
                return

            dev_info = getattr(local_stream, "dev_info", None)
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "metadata",
                        "device_id": device_id,
                        "serial": device.serial,
                        "width": int(getattr(dev_info, "screen_width", 0) or 0),
                        "height": int(getattr(dev_info, "screen_height", 0) or 0),
                        "device_name": str(getattr(dev_info, "device_name", "") or ""),
                    },
                    ensure_ascii=False,
                )
            )

        async def _send_video_loop() -> None:
            while True:
                if remote_stream is not None:
                    chunk = await remote_stream.recv_chunk(timeout=1.0)
                else:
                    assert local_stream is not None
                    chunk = await loop.run_in_executor(None, local_stream.get_chunk, 1.0)
                if chunk is None:
                    if remote_stream is not None and remote_stream.error_code:
                        await _send_ws_error_and_close(
                            remote_stream.error_code,
                            remote_stream.error_message or "Scrcpy 中继流已断开",
                        )
                    break
                if chunk:
                    await websocket.send_bytes(chunk)

        async def _recv_control_loop() -> None:
            while True:
                raw_text = await websocket.receive_text()
                try:
                    cmd = json.loads(raw_text)
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                if not isinstance(cmd, dict):
                    continue
                cmd_type = cmd.get("type")
                if cmd_type not in ("touch", "key", "text"):
                    continue
                try:
                    await _verify_ws_control_permission(
                        user=user,
                        device_id=device_id,
                        cmd=cmd,
                        fallback_token=lease_token,
                        lease_cache=lease_cache,
                    )
                    if remote_stream is not None:
                        if cmd_type == "touch":
                            await remote_stream.send_touch(
                                int(cmd.get("action", 0)),
                                int(cmd.get("x", 0)),
                                int(cmd.get("y", 0)),
                                cmd.get("w"),
                                cmd.get("h"),
                            )
                        elif cmd_type == "key":
                            await remote_stream.send_key(int(cmd.get("keycode", 0)))
                        elif cmd_type == "text":
                            text_val = str(cmd.get("text", ""))[:2000]
                            await remote_stream.send_text(text_val)
                    else:
                        if cmd_type == "touch":
                            await loop.run_in_executor(
                                None,
                                scrcpy_manager.send_touch_event,
                                device.serial,
                                int(cmd.get("action", 0)),
                                int(cmd.get("x", 0)),
                                int(cmd.get("y", 0)),
                                cmd.get("w"),
                                cmd.get("h"),
                            )
                        elif cmd_type == "key":
                            await loop.run_in_executor(
                                None,
                                scrcpy_manager.send_key_event,
                                device.serial,
                                int(cmd.get("keycode", 0)),
                            )
                        elif cmd_type == "text":
                            text_val = str(cmd.get("text", ""))[:2000]
                            await loop.run_in_executor(
                                None,
                                scrcpy_manager.send_text_event,
                                device.serial,
                                text_val,
                            )
                except PermissionError as auth_err:
                    try:
                        await websocket.send_text(
                            json.dumps(
                                {"type": "error", "code": "control_denied", "message": str(auth_err)},
                                ensure_ascii=False,
                            )
                        )
                    except Exception:
                        pass
                except Exception as ctrl_err:
                    logger.debug("Scrcpy 设备控制指令忽略 (device_id=%s): %s", device_id, ctrl_err)

        send_task = asyncio.create_task(_send_video_loop())
        recv_task = asyncio.create_task(_recv_control_loop())
        done, pending = await asyncio.wait({send_task, recv_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in pending:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                raise exc
    except WebSocketDisconnect:
        logger.info("Scrcpy 设备流客户端断开: device_id=%s serial=%s", device_id, device.serial)
    except Exception as exc:
        logger.warning("Scrcpy 设备流异常 device_id=%s: %s", device_id, exc)
        try:
            await websocket.close(code=4000)
        except Exception:
            pass
    finally:
        if remote_stream is not None:
            await remote_stream.close()
        if local_stream is not None:
            try:
                local_stream.close()
            except Exception:
                pass


@ws_router.websocket("/ws/scrcpy/{serial}")
async def scrcpy_video_stream(websocket: WebSocket, serial: str):
    """全双工 WebSocket：下行推送 60FPS H.264 视频流，上行毫秒级接收触控与按键。"""
    if settings.ANDROID_MULTI_NODE_ENABLED or (
        not settings.ATP_LOCAL_MODE and settings.ADB_SCAN_MODE.strip().lower() == "worker"
    ):
        await websocket.close(code=4009, reason="multi_node_feature_disabled")
        return
    user = await _get_ws_user(websocket)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if getattr(user, "role", None) not in (UserRole.admin, UserRole.engineer):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    serial_device_id: int | None = None
    lease_cache: dict[str, Any] = {}
    fallback_token = websocket.query_params.get("lease_token") if hasattr(websocket, "query_params") else None
    if not settings.ATP_LOCAL_MODE:
        try:
            async with AsyncSessionLocal() as db:
                dev_row = (await db.execute(select(Device).where(Device.serial == serial))).scalar_one_or_none()
                serial_device_id = getattr(dev_row, "id", None)
        except Exception:
            serial_device_id = None

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
                    if not isinstance(cmd, dict):
                        continue
                    cmd_type = cmd.get("type")
                    if cmd_type not in {"touch", "key", "text"}:
                        continue
                    if not settings.ATP_LOCAL_MODE and serial_device_id is None:
                        raise PermissionError("设备未在平台注册或缺少有效租约，无法发送实时控制指令")
                    await _verify_ws_control_permission(
                        user=user,
                        device_id=serial_device_id or 0,
                        cmd=cmd,
                        fallback_token=fallback_token,
                        lease_cache=lease_cache,
                    )
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
                except PermissionError as auth_err:
                    try:
                        await websocket.send_text(
                            json.dumps(
                                {"type": "error", "code": "control_denied", "message": str(auth_err)},
                                ensure_ascii=False,
                            )
                        )
                    except Exception:
                        pass
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
