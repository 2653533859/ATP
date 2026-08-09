"""Validate bounded Android device compatibility matrices."""

from __future__ import annotations

from typing import Any, Iterable


class DeviceCompatibilityError(ValueError):
    """Raised when a device matrix cannot be executed safely."""


MAX_DEVICE_MATRIX = 8
_MATCH_FIELDS = ("model", "os_version", "sdk_version", "resolution")


def build_android_device_matrix(
    requested: Iterable[Any],
    *,
    available_devices: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Normalize and validate device variants against the registered device pool."""
    entries = list(requested)
    if not entries:
        raise DeviceCompatibilityError("设备矩阵至少需要一个设备")
    if len(entries) > MAX_DEVICE_MATRIX:
        raise DeviceCompatibilityError(f"设备矩阵不能超过 {MAX_DEVICE_MATRIX} 个设备")

    available = {str(item.get("serial", "")): item for item in available_devices if isinstance(item, dict)}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(entries, start=1):
        if isinstance(raw, str):
            item = {"serial": raw}
        elif isinstance(raw, dict):
            item = dict(raw)
        else:
            raise DeviceCompatibilityError(f"第 {index} 个设备矩阵项格式无效")
        serial = str(item.get("serial", "")).strip()
        if not serial:
            raise DeviceCompatibilityError(f"第 {index} 个设备矩阵项缺少 serial")
        if serial in seen:
            raise DeviceCompatibilityError(f"设备矩阵包含重复设备: {serial}")
        seen.add(serial)

        registered = available.get(serial)
        if available and registered is None:
            raise DeviceCompatibilityError(f"设备未注册或不在当前设备池: {serial}")
        if registered:
            for field in _MATCH_FIELDS:
                expected = str(item.get(field, "")).strip()
                actual = str(registered.get(field, "")).strip()
                if expected and actual and expected != actual:
                    raise DeviceCompatibilityError(f"设备 {serial} 的 {field} 不匹配: 期望 {expected}，实际 {actual}")
            normalized = {
                "device_id": registered.get("id") or registered.get("device_id"),
                **{
                    field: registered.get(field)
                    for field in ("model", "brand", "os_version", "sdk_version", "resolution")
                },
            }
        else:
            normalized = {
                "device_id": item.get("device_id"),
                **{field: item.get(field) for field in ("model", "brand", "os_version", "sdk_version", "resolution")},
            }
        result.append(
            {"serial": serial, **{key: value for key, value in normalized.items() if value not in (None, "")}}
        )
    return result
