"""Unified iOS Device Asset and Online Heartbeat Management Service (T1.1).

Provides:
1. Unified device abstraction across Android and iOS platforms.
2. iOS device registration and periodic heartbeat renewal.
3. Stale iOS device offline convergence.
4. WebDriverAgent (WDA) and Appium health probe.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device, DeviceStatus
from app.models.ios import IosDevice, IosDeviceStatus

logger = logging.getLogger(__name__)

DEFAULT_IOS_HEARTBEAT_TIMEOUT_SECONDS = 120


async def register_or_heartbeat_ios_device(
    db: Any,
    *,
    udid: str,
    name: str | None = None,
    model: str | None = None,
    platform_version: str | None = None,
    appium_server_url: str = "http://127.0.0.1:4723",
    wda_local_port: int | None = None,
    ip_address: str | None = None,
    port: int | None = None,
    description: str | None = None,
) -> IosDevice:
    """Register a new iOS device or update the heartbeat/presence of an existing device."""
    now = datetime.now(timezone.utc)
    query = select(IosDevice).where(IosDevice.udid == udid)
    result = await db.execute(query)
    device = result.scalar_one_or_none()

    if device is None:
        device = IosDevice(
            udid=udid,
            name=name or f"iPhone ({udid[:8]})",
            model=model or "iPhone",
            platform_version=platform_version,
            appium_server_url=appium_server_url,
            wda_local_port=wda_local_port,
            ip_address=ip_address,
            port=port,
            description=description,
            status=IosDeviceStatus.online,
            last_seen_at=now,
        )
        db.add(device)
    else:
        if name:
            device.name = name
        if model:
            device.model = model
        if platform_version:
            device.platform_version = platform_version
        if appium_server_url:
            device.appium_server_url = appium_server_url
        if wda_local_port is not None:
            device.wda_local_port = wda_local_port
        if ip_address:
            device.ip_address = ip_address
        if port is not None:
            device.port = port
        if description:
            device.description = description

        # Retain busy state if currently under test; otherwise mark online
        if device.status != IosDeviceStatus.busy:
            device.status = IosDeviceStatus.online
        device.last_seen_at = now

    await db.flush()
    return device


async def mark_stale_ios_devices_offline(
    db: Any,
    *,
    timeout_seconds: int = DEFAULT_IOS_HEARTBEAT_TIMEOUT_SECONDS,
) -> int:
    """Scan and mark iOS devices whose heartbeat has expired as offline."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=timeout_seconds)

    query = select(IosDevice).where(
        IosDevice.status.in_([IosDeviceStatus.online, IosDeviceStatus.busy]),
        IosDevice.last_seen_at.is_not(None),
        IosDevice.last_seen_at < cutoff,
    )
    result = await db.execute(query)
    stale_devices = result.scalars().all()

    for device in stale_devices:
        device.status = IosDeviceStatus.offline

    if stale_devices:
        await db.flush()

    return len(stale_devices)


async def probe_ios_wda_health(appium_url: str, timeout_seconds: float = 3.0) -> dict[str, Any]:
    """Probe WDA / Appium status endpoint to verify WDA readiness."""
    endpoint = f"{appium_url.rstrip('/')}/status"
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.get(endpoint)
            if resp.status_code == 200:
                data = resp.json().get("value", {})
                ready = data.get("ready", True) if isinstance(data, dict) else True
                return {"healthy": True, "ready": ready, "data": data}
            return {"healthy": False, "ready": False, "status_code": resp.status_code}
    except Exception as exc:
        return {"healthy": False, "ready": False, "error": str(exc)}


def format_unified_device(device_item: Device | IosDevice, platform: str) -> dict[str, Any]:
    """Convert an Android Device or IosDevice ORM entity into a standardized unified device dict."""
    if platform == "ios":
        ios_dev: IosDevice = device_item  # type: ignore[assignment]
        return {
            "id": ios_dev.id,
            "platform": "ios",
            "name": ios_dev.name or ios_dev.model or f"iPhone-{ios_dev.id}",
            "brand": "Apple",
            "model": ios_dev.model or "iPhone",
            "identifier": ios_dev.udid,
            "os_version": ios_dev.platform_version or "-",
            "status": ios_dev.status.value,
            "appium_server_url": ios_dev.appium_server_url,
            "wda_local_port": ios_dev.wda_local_port,
            "ip_address": ios_dev.ip_address,
            "port": ios_dev.port,
            "last_seen_at": ios_dev.last_seen_at,
            "created_at": ios_dev.created_at,
            "updated_at": ios_dev.updated_at,
        }
    else:
        android_dev: Device = device_item  # type: ignore[assignment]
        return {
            "id": android_dev.id,
            "platform": "android",
            "name": android_dev.name or android_dev.model or android_dev.serial,
            "brand": android_dev.brand or "Android",
            "model": android_dev.model or "Generic Android",
            "identifier": android_dev.serial,
            "os_version": android_dev.os_version or "-",
            "status": android_dev.status.value,
            "appium_server_url": None,
            "wda_local_port": None,
            "ip_address": android_dev.ip_address,
            "port": android_dev.port,
            "last_seen_at": android_dev.last_seen_at,
            "created_at": android_dev.created_at,
            "updated_at": android_dev.updated_at,
        }


async def get_unified_device_list(
    db: Any,
    *,
    platform_filter: str | None = None,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve a consolidated list of devices across Android and iOS."""
    unified: list[dict[str, Any]] = []

    # 1. Fetch Android devices
    if platform_filter in (None, "all", "android"):
        query_android = select(Device).order_by(Device.status.asc(), Device.updated_at.desc())
        if status_filter:
            try:
                query_android = query_android.where(Device.status == DeviceStatus(status_filter))
            except ValueError:
                pass
        android_results = (await db.execute(query_android)).scalars().all()
        unified.extend(format_unified_device(d, "android") for d in android_results)

    # 2. Fetch iOS devices
    if platform_filter in (None, "all", "ios"):
        query_ios = select(IosDevice).order_by(IosDevice.status.asc(), IosDevice.updated_at.desc())
        if status_filter:
            try:
                query_ios = query_ios.where(IosDevice.status == IosDeviceStatus(status_filter))
            except ValueError:
                pass
        ios_results = (await db.execute(query_ios)).scalars().all()
        unified.extend(format_unified_device(d, "ios") for d in ios_results)

    return unified
