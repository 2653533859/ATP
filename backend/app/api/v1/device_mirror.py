"""
设备屏幕镜像 API

GET /api/v1/devices/{device_id}/screen  MJPEG 截图流
GET /api/v1/devices/{device_id}/screenshot  单帧截图（PNG）
"""
import asyncio
import logging
import subprocess
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.device import Device, DeviceStatus
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["设备镜像"])


def _adb_screenshot(serial: str, timeout: int = 10) -> bytes | None:
    """通过 adb 截图，返回 PNG 字节"""
    cmd = ["adb", "-s", serial, "exec-out", "screencap", "-p"]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=timeout
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.warning("adb screenshot failed for %s: %s", serial, e)
        return None


@router.get("/devices/{device_id}/screenshot")
async def device_screenshot(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """获取设备当前屏幕单帧截图（PNG）"""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.status == DeviceStatus.offline:
        raise HTTPException(status_code=400, detail="设备离线")

    data = await asyncio.get_event_loop().run_in_executor(
        None, _adb_screenshot, device.serial
    )
    if not data:
        raise HTTPException(status_code=503, detail="截图失败，请检查设备连接")

    return Response(content=data, media_type="image/png")


async def _mjpeg_generator(serial: str, fps: float = 2.0):
    """生成 MJPEG 帧流"""
    interval = 1.0 / fps
    while True:
        data = await asyncio.get_event_loop().run_in_executor(
            None, _adb_screenshot, serial
        )
        if data:
            # MJPEG boundary frame (PNG → 直接推送，前端用 img 标签轮询更简单)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/png\r\n"
                b"Content-Length: " + str(len(data)).encode() + b"\r\n\r\n"
                + data + b"\r\n"
            )
        await asyncio.sleep(interval)


@router.get("/devices/{device_id}/screen")
async def device_screen_stream(
    device_id: int,
    fps: float = 2.0,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """MJPEG 设备屏幕实时流"""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.status == DeviceStatus.offline:
        raise HTTPException(status_code=400, detail="设备离线")

    fps = max(0.5, min(fps, 5.0))

    return StreamingResponse(
        _mjpeg_generator(device.serial, fps),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
