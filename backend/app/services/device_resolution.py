"""Unified device identity resolution for multi-node Android execution.

All platform-internal paths should identify devices by ``device_id``.
Legacy ``serial``-only references are resolved only when they match a single
registered device; zero or multiple matches fail explicitly without guessing.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.device import Device


class DeviceResolutionError(ValueError):
    """Raised when a device cannot be uniquely or safely resolved."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _extract_result_rows(result: Any) -> list[Any]:
    scalars_fn = getattr(result, "scalars", None)
    if callable(scalars_fn):
        scalars_obj = scalars_fn()
        all_fn = getattr(scalars_obj, "all", None)
        if callable(all_fn):
            return list(all_fn())
    scalar_one = getattr(result, "scalar_one_or_none", None)
    if callable(scalar_one):
        item = scalar_one()
        return [] if item is None else [item]
    return []


def _validate_resolved_device(
    device: Device | None,
    *,
    device_id: int | None,
    serial: str | None,
    require_claimed: bool,
) -> Device:
    if device is None:
        target = f"id={device_id}" if device_id is not None else f"serial={serial}"
        raise DeviceResolutionError("device_not_found", f"设备未注册: {target}")

    normalized_serial = str(serial).strip() if serial else ""
    actual_serial = getattr(device, "serial", None)
    if normalized_serial and isinstance(actual_serial, str) and actual_serial != normalized_serial:
        raise DeviceResolutionError(
            "device_identity_mismatch",
            f"设备 {device.id} 的序列号不匹配（期望 {normalized_serial}，实际 {actual_serial}）",
        )

    if require_claimed and not (getattr(device, "worker_id", None) or "").strip():
        raise DeviceResolutionError(
            "device_unclaimed",
            f"设备 {actual_serial or ''} (id={device.id}) 尚未认领归属节点，请先在设备管理中认领",
        )
    return device


async def resolve_device_async(
    db: AsyncSession,
    *,
    device_id: int | None = None,
    serial: str | None = None,
    require_claimed: bool = False,
) -> Device:
    """Resolve a unique ``Device`` asynchronously by ``device_id`` or unambiguous ``serial``."""
    if device_id is not None:
        if hasattr(db, "execute"):
            res = await db.execute(select(Device).where(Device.id == int(device_id)))
            rows = _extract_result_rows(res)
            device = rows[0] if rows else None
        else:
            device = await db.get(Device, int(device_id))
        return _validate_resolved_device(
            device,
            device_id=int(device_id),
            serial=serial,
            require_claimed=require_claimed,
        )

    normalized_serial = str(serial).strip() if serial else ""
    if not normalized_serial:
        raise DeviceResolutionError("device_not_found", "未指定目标设备")

    result = await db.execute(select(Device).where(Device.serial == normalized_serial))
    matches = _extract_result_rows(result)
    if len(matches) > 1:
        raise DeviceResolutionError(
            "device_serial_ambiguous",
            f"序列号 {normalized_serial} 在多个节点中同时存在，请明确指定具体设备 ID",
        )
    return _validate_resolved_device(
        matches[0] if matches else None,
        device_id=None,
        serial=normalized_serial,
        require_claimed=require_claimed,
    )


def resolve_device_sync(
    session: Session,
    *,
    device_id: int | None = None,
    serial: str | None = None,
    require_claimed: bool = False,
) -> Device:
    """Resolve a unique ``Device`` synchronously by ``device_id`` or unambiguous ``serial``."""
    if device_id is not None:
        device = session.get(Device, int(device_id))
        return _validate_resolved_device(
            device,
            device_id=int(device_id),
            serial=serial,
            require_claimed=require_claimed,
        )

    normalized_serial = str(serial).strip() if serial else ""
    if not normalized_serial:
        raise DeviceResolutionError("device_not_found", "未指定目标设备")

    matches = list(session.scalars(select(Device).where(Device.serial == normalized_serial)).all())
    if len(matches) > 1:
        raise DeviceResolutionError(
            "device_serial_ambiguous",
            f"序列号 {normalized_serial} 在多个节点中同时存在，请明确指定具体设备 ID",
        )
    return _validate_resolved_device(
        matches[0] if matches else None,
        device_id=None,
        serial=normalized_serial,
        require_claimed=require_claimed,
    )


def extract_device_id(mapping: dict[str, Any] | None) -> int | None:
    """Safely extract an integer ``device_id`` from a config/request mapping."""
    if not isinstance(mapping, dict):
        return None
    raw = mapping.get("device_id")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = int(raw)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def extract_target_device_spec(
    config: dict[str, Any] | None,
    extra_vars: dict[str, Any] | None = None,
) -> tuple[int | None, str | None]:
    """Resolve target ``(device_id, device_serial)`` with ``extra_vars`` overriding ``config``.

    When ``extra_vars`` specifies ``device_id`` or ``device_serial``, stale
    fields on ``config`` are not mixed into the override.
    """
    ext_id = extract_device_id(extra_vars)
    ext_serial_raw = extra_vars.get("device_serial") if isinstance(extra_vars, dict) else None
    ext_serial = str(ext_serial_raw).strip() if ext_serial_raw else None
    if ext_id is not None or ext_serial:
        return ext_id, ext_serial

    cfg_id = extract_device_id(config)
    cfg_serial_raw = config.get("device_serial") if isinstance(config, dict) else None
    cfg_serial = str(cfg_serial_raw).strip() if cfg_serial_raw else None
    return cfg_id, cfg_serial
