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

    available_list = [item for item in available_devices if isinstance(item, dict)]
    by_id: dict[int, dict[str, Any]] = {}
    by_serial: dict[str, list[dict[str, Any]]] = {}
    for item in available_list:
        raw_id = item.get("id") or item.get("device_id")
        if raw_id is not None and not isinstance(raw_id, bool):
            try:
                by_id[int(raw_id)] = item
            except (TypeError, ValueError):
                pass
        ser = str(item.get("serial", "")).strip()
        if ser:
            by_serial.setdefault(ser, []).append(item)

    result: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, Any]] = set()
    for index, raw in enumerate(entries, start=1):
        if isinstance(raw, str):
            item = {"serial": raw}
        elif isinstance(raw, dict):
            item = dict(raw)
        else:
            raise DeviceCompatibilityError(f"第 {index} 个设备矩阵项格式无效")

        raw_dev_id = item.get("device_id")
        dev_id: int | None = None
        if raw_dev_id is not None and not isinstance(raw_dev_id, bool):
            try:
                dev_id = int(raw_dev_id)
            except (TypeError, ValueError):
                raise DeviceCompatibilityError(f"第 {index} 个设备矩阵项 device_id 无效") from None

        serial = str(item.get("serial", "")).strip()
        if not serial and dev_id is None:
            raise DeviceCompatibilityError(f"第 {index} 个设备矩阵项缺少 serial")

        registered: dict[str, Any] | None = None
        if available_list:
            if dev_id is not None:
                registered = by_id.get(dev_id)
                if registered is None:
                    raise DeviceCompatibilityError(f"设备未注册或不在当前设备池: id={dev_id}")
                if serial and str(registered.get("serial", "")).strip() != serial:
                    raise DeviceCompatibilityError(f"设备 id={dev_id} 的 serial 不匹配")
                serial = str(registered.get("serial", "")).strip() or serial
            else:
                matches = by_serial.get(serial, [])
                if not matches:
                    raise DeviceCompatibilityError(f"设备未注册或不在当前设备池: {serial}")
                if len(matches) > 1:
                    raise DeviceCompatibilityError(f"序列号 {serial} 存在多个节点归属，请在矩阵中指定 device_id")
                registered = matches[0]
                dev_id = registered.get("id") or registered.get("device_id")

        dedup_key = ("id", dev_id) if dev_id is not None else ("serial", serial)
        if dedup_key in seen_keys:
            raise DeviceCompatibilityError(f"设备矩阵包含重复设备: {serial or dev_id}")
        seen_keys.add(dedup_key)

        if registered:
            for field in _MATCH_FIELDS:
                expected = str(item.get(field, "")).strip()
                actual = str(registered.get(field, "")).strip()
                if expected and actual and expected != actual:
                    raise DeviceCompatibilityError(f"设备 {serial} 的 {field} 不匹配: 期望 {expected}，实际 {actual}")
            normalized = {
                "device_id": registered.get("id") or registered.get("device_id"),
                "worker_id": registered.get("worker_id"),
                **{
                    field: registered.get(field)
                    for field in ("model", "brand", "os_version", "sdk_version", "resolution")
                },
            }
        else:
            normalized = {
                "device_id": dev_id,
                "worker_id": item.get("worker_id"),
                **{field: item.get(field) for field in ("model", "brand", "os_version", "sdk_version", "resolution")},
            }
        result.append(
            {"serial": serial, **{key: value for key, value in normalized.items() if value not in (None, "")}}
        )
    return result
