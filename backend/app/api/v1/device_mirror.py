"""
设备屏幕镜像 API

GET /api/v1/devices/{device_id}/screen  MJPEG 截图流
GET  /api/v1/devices/{device_id}/screenshot  单帧截图（PNG）
POST /api/v1/devices/{device_id}/tap         实时点击
POST /api/v1/devices/{device_id}/swipe       实时滑动
"""

import asyncio
import base64
import logging
import re
import subprocess
from defusedxml import ElementTree as ET
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.models.device import Device, DeviceStatus
from app.api.deps import get_current_user, require_engineer
from app.services.device_leases import get_active_device_lease
from app.schemas.device import DeviceSwipeIn, DeviceTapIn

logger = logging.getLogger(__name__)

router = APIRouter(tags=["设备镜像"])

_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _extract_hierarchy_xml(output: str) -> str | None:
    """从 uiautomator 的混合输出中提取完整 hierarchy XML。"""
    start = output.find("<hierarchy")
    if start < 0:
        return None
    end_marker = "</hierarchy>"
    end = output.find(end_marker, start)
    if end < 0:
        return None
    return output[start : end + len(end_marker)]


def _parse_bounds(value: str | None) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    match = _BOUNDS_RE.fullmatch(value.strip())
    if not match:
        return None
    left, top, right, bottom = (int(item) for item in match.groups())
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _parse_ui_target(output: str, x: int, y: int) -> dict[str, object] | None:
    """返回点击点命中的最佳可定位节点，无法解析时返回 None。"""
    hierarchy_xml = _extract_hierarchy_xml(output)
    if not hierarchy_xml:
        return None

    try:
        root = ET.fromstring(hierarchy_xml)
    except ET.ParseError:
        return None

    candidates: list[tuple[tuple[int, int, int, int], dict[str, object]]] = []
    for node in root.iter("node"):
        bounds = _parse_bounds(node.attrib.get("bounds"))
        if not bounds:
            continue
        left, top, right, bottom = bounds
        if not (left <= x <= right and top <= y <= bottom):
            continue
        if node.attrib.get("visible-to-user") == "false":
            continue

        text = node.attrib.get("text", "").strip()
        resource_id = node.attrib.get("resource-id", "").strip()
        content_desc = node.attrib.get("content-desc", "").strip()
        clickable = node.attrib.get("clickable") == "true"
        enabled = node.attrib.get("enabled", "true") != "false"
        meaningful = bool(text or resource_id or content_desc)
        area = (right - left) * (bottom - top)
        target = {
            "text": text or None,
            "resourceId": resource_id or None,
            "contentDesc": content_desc or None,
            "className": node.attrib.get("class", "").strip() or None,
            "bounds": {"left": left, "top": top, "right": right, "bottom": bottom},
            "clickable": clickable,
            "enabled": enabled,
        }
        # 优先可点击且有语义的节点，再选面积更小的深层节点，避免把整个页面当成目标。
        rank = (int(clickable and meaningful), int(meaningful), int(clickable), -area)
        candidates.append((rank, target))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    target = candidates[0][1]
    if not any(target.get(key) for key in ("text", "resourceId", "contentDesc")):
        return None
    return target


def _adb_screenshot(serial: str, timeout: int = 10) -> bytes | None:
    """通过 adb 截图，返回 PNG 字节"""
    cmd = ["adb", "-s", serial, "exec-out", "screencap", "-p"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.warning("adb screenshot failed for %s: %s", serial, e)
        return None


def _adb_input(serial: str, *args: str, timeout: int = 10) -> bool:
    """通过 adb shell input 执行实时交互。"""
    cmd = ["adb", "-s", serial, "shell", "input", *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.warning("adb input failed for %s: %s", serial, e)
        return False


def _ui_target_diagnostic(status: str, code: str | None = None) -> dict[str, str | None]:
    """构造不包含 ADB 原始输出的控件属性诊断。"""
    return {"status": status, "code": code}


def _adb_ui_target_diagnostic(
    serial: str, x: int, y: int, timeout: int = 10
) -> tuple[dict[str, object] | None, dict[str, str | None]]:
    """通过 UIAutomator dump 查找控件，并返回可供前端解释的脱敏状态。"""
    hierarchy_path = "/sdcard/atp-ui-hierarchy.xml"
    dump_cmd = ["adb", "-s", serial, "shell", "uiautomator", "dump", hierarchy_path]
    cat_cmd = ["adb", "-s", serial, "shell", "cat", hierarchy_path]
    try:
        dump_proc = subprocess.run(dump_cmd, capture_output=True, timeout=timeout)
        if dump_proc.returncode != 0:
            output = ((dump_proc.stdout or b"") + (dump_proc.stderr or b"")).decode("utf-8", errors="replace")
            logger.warning("adb ui hierarchy dump failed for %s: %s", serial, output[-500:])
            return None, _ui_target_diagnostic("unavailable", "uiautomator_dump_failed")

        cat_proc = subprocess.run(cat_cmd, capture_output=True, timeout=timeout)
        if cat_proc.returncode != 0:
            logger.warning("adb ui hierarchy read failed for %s", serial)
            return None, _ui_target_diagnostic("unavailable", "uiautomator_read_failed")
        output = ((cat_proc.stdout or b"") + (cat_proc.stderr or b"")).decode("utf-8", errors="replace")
        target = _parse_ui_target(output, x, y)
        return target, _ui_target_diagnostic("found" if target else "not_found", None if target else "target_not_found")
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.warning("adb ui hierarchy failed for %s: %s", serial, e)
        return None, _ui_target_diagnostic("unavailable", "uiautomator_request_failed")


def _adb_ui_target(serial: str, x: int, y: int, timeout: int = 10) -> dict[str, object] | None:
    """兼容旧调用方：只返回控件，不暴露诊断字段。"""
    target, _ = _adb_ui_target_diagnostic(serial, x, y, timeout)
    return target


def _use_android_worker() -> bool:
    return settings.ADB_SCAN_MODE.strip().lower() == "worker"


async def _dispatch_worker_operation(operation: str, serial: str, params: dict | None = None) -> dict:
    """将设备操作派发到 Windows Android Worker，并等待受控结果。"""
    from app.worker.tasks_device import run_android_device_operation

    queue = settings.ANDROID_WORKER_QUEUE.strip() or "mobile_special"
    try:
        async_result = run_android_device_operation.apply_async(
            args=[operation, serial, params or {}],
            queue=queue,
            ignore_result=False,
        )
        result = await asyncio.to_thread(async_result.get, timeout=15)
    except Exception as exc:
        logger.warning("Android Worker operation failed: %s %s: %s", operation, serial, exc)
        raise HTTPException(status_code=503, detail="Android Worker 不可用或设备操作超时") from exc

    if not isinstance(result, dict) or not result.get("ok"):
        detail = result.get("error") if isinstance(result, dict) else "Worker 返回结果无效"
        raise HTTPException(status_code=503, detail=str(detail or "Android Worker 操作失败"))
    return result


async def _screenshot(serial: str) -> bytes | None:
    if not _use_android_worker():
        return await asyncio.to_thread(_adb_screenshot, serial)
    result = await _dispatch_worker_operation("screenshot", serial)
    encoded = result.get("data_base64")
    if not isinstance(encoded, str) or not encoded:
        return None
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        logger.warning("Android Worker returned invalid screenshot for %s", serial)
        return None


async def _get_online_device(device_id: int, db: AsyncSession) -> Device:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.status == DeviceStatus.offline:
        raise HTTPException(status_code=400, detail="设备离线")
    return device


async def _require_control_lease(db: AsyncSession, device_id: int, lease_token: str | None) -> None:
    """设备写操作必须使用当前租约，避免绕过工作台直接控制真机。"""
    if not lease_token:
        raise HTTPException(status_code=409, detail="设备控制需要先获取有效租约")
    lease = await get_active_device_lease(db, device_id, lease_token)
    if lease is None:
        raise HTTPException(status_code=409, detail="设备租约不存在或已过期，请重新获取租约")


@router.get("/devices/{device_id}/screenshot")
async def device_screenshot(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """获取设备当前屏幕单帧截图（PNG）"""
    device = await _get_online_device(device_id, db)

    data = await _screenshot(device.serial)
    if not data:
        raise HTTPException(status_code=503, detail="截图失败，请检查设备连接")

    return Response(content=data, media_type="image/png")


@router.post("/devices/{device_id}/tap")
async def device_tap(
    device_id: int,
    body: DeviceTapIn,
    db: AsyncSession = Depends(get_db),
    lease_token: str | None = Header(default=None, alias="X-Device-Lease-Token"),
    _=Depends(require_engineer),
):
    """在设备屏幕坐标执行实时点击。"""
    device = await _get_online_device(device_id, db)
    await _require_control_lease(db, device_id, lease_token)
    if _use_android_worker():
        await _dispatch_worker_operation("tap", device.serial, {"x": body.x, "y": body.y})
        return {"success": True}
    ok = await asyncio.to_thread(_adb_input, device.serial, "tap", str(body.x), str(body.y))
    if not ok:
        raise HTTPException(status_code=503, detail="点击失败，请检查设备连接")
    return {"success": True}


@router.get("/devices/{device_id}/ui-target")
async def device_ui_target(
    device_id: int,
    x: int = Query(..., ge=0),
    y: int = Query(..., ge=0),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """根据屏幕坐标返回 UIAutomator 中对应的可定位控件。"""
    device = await _get_online_device(device_id, db)
    if _use_android_worker():
        result = await _dispatch_worker_operation("ui_target", device.serial, {"x": x, "y": y})
        response: dict[str, object] = {"target": result.get("target")}
        if result.get("diagnostic") is not None:
            response["diagnostic"] = result["diagnostic"]
        return response
    target, diagnostic = await asyncio.to_thread(_adb_ui_target_diagnostic, device.serial, x, y)
    return {"target": target, "diagnostic": diagnostic}


@router.post("/devices/{device_id}/swipe")
async def device_swipe(
    device_id: int,
    body: DeviceSwipeIn,
    db: AsyncSession = Depends(get_db),
    lease_token: str | None = Header(default=None, alias="X-Device-Lease-Token"),
    _=Depends(require_engineer),
):
    """在设备屏幕坐标执行实时滑动。"""
    device = await _get_online_device(device_id, db)
    await _require_control_lease(db, device_id, lease_token)
    duration_ms = max(100, min(body.duration_ms, 5000))
    if _use_android_worker():
        await _dispatch_worker_operation(
            "swipe",
            device.serial,
            {"x1": body.x1, "y1": body.y1, "x2": body.x2, "y2": body.y2, "duration_ms": duration_ms},
        )
        return {"success": True}
    ok = await asyncio.to_thread(
        _adb_input,
        device.serial,
        "swipe",
        str(body.x1),
        str(body.y1),
        str(body.x2),
        str(body.y2),
        str(duration_ms),
    )
    if not ok:
        raise HTTPException(status_code=503, detail="滑动失败，请检查设备连接")
    return {"success": True}


async def _mjpeg_generator(serial: str, fps: float = 2.0):
    """生成 MJPEG 帧流"""
    interval = 1.0 / fps
    while True:
        try:
            data = await _screenshot(serial)
        except HTTPException:
            data = None
        if data:
            # MJPEG boundary frame (PNG → 直接推送，前端用 img 标签轮询更简单)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/png\r\n"
                b"Content-Length: " + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n"
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
    device = await _get_online_device(device_id, db)

    fps = max(0.5, min(fps, 5.0))

    return StreamingResponse(
        _mjpeg_generator(device.serial, fps),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
