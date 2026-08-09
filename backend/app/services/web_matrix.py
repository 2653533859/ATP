"""Validate and normalize Web browser/device execution matrices."""

from __future__ import annotations

from typing import Any


SUPPORTED_BROWSERS = {"chromium", "firefox", "webkit"}
MAX_MATRIX_VARIANTS = 12


class WebMatrixError(ValueError):
    """Raised when a Web execution matrix is invalid or too large."""


def build_web_matrix(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw_matrix = config.get("browser_matrix")
    if raw_matrix is None:
        return [_base_variant(config)]
    if not isinstance(raw_matrix, list) or not raw_matrix:
        raise WebMatrixError("browser_matrix 必须是非空数组")
    if len(raw_matrix) > MAX_MATRIX_VARIANTS:
        raise WebMatrixError(f"浏览器矩阵最多支持 {MAX_MATRIX_VARIANTS} 个组合")

    variants: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for index, item in enumerate(raw_matrix, start=1):
        if not isinstance(item, dict):
            raise WebMatrixError(f"浏览器矩阵第 {index} 项必须是对象")
        variant = _base_variant(config)
        browser = str(item.get("browser", variant["browser"])).strip().lower()
        if browser not in SUPPORTED_BROWSERS:
            raise WebMatrixError(f"不支持的浏览器: {browser}")
        variant["browser"] = browser
        raw_viewport = item.get("viewport")
        viewport: dict[str, Any] = raw_viewport if isinstance(raw_viewport, dict) else {}
        variant["viewport"] = {
            "width": _bounded_int(viewport.get("width", variant["viewport"]["width"]), 320, 3840, "viewport.width"),
            "height": _bounded_int(viewport.get("height", variant["viewport"]["height"]), 240, 2160, "viewport.height"),
        }
        for key in ("device", "locale", "user_agent"):
            if item.get(key) is not None:
                variant[key] = str(item[key]).strip()
        if item.get("device_scale_factor") is not None:
            variant["device_scale_factor"] = float(item["device_scale_factor"])
        identity = (
            variant["browser"],
            variant["viewport"]["width"],
            variant["viewport"]["height"],
            variant.get("device", ""),
            variant.get("locale", ""),
            variant.get("user_agent", ""),
            variant.get("device_scale_factor", 1),
        )
        if identity in seen:
            continue
        seen.add(identity)
        variant["label"] = str(item.get("label") or _variant_label(variant, len(variants) + 1))
        variants.append(variant)
    if not variants:
        raise WebMatrixError("浏览器矩阵没有有效组合")
    return variants


def _base_variant(config: dict[str, Any]) -> dict[str, Any]:
    raw_viewport = config.get("viewport")
    viewport: dict[str, Any] = raw_viewport if isinstance(raw_viewport, dict) else {}
    return {
        "browser": str(config.get("browser", "chromium")).strip().lower(),
        "viewport": {
            "width": _bounded_int(viewport.get("width", 1280), 320, 3840, "viewport.width"),
            "height": _bounded_int(viewport.get("height", 720), 240, 2160, "viewport.height"),
        },
        "device": str(config.get("device", "")).strip(),
        "locale": str(config.get("locale", "")).strip(),
        "user_agent": str(config.get("user_agent", "")).strip(),
        "device_scale_factor": float(config.get("device_scale_factor", 1)),
    }


def _bounded_int(value: Any, minimum: int, maximum: int, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise WebMatrixError(f"{field} 必须是数字") from exc
    if not minimum <= parsed <= maximum:
        raise WebMatrixError(f"{field} 必须在 {minimum} 到 {maximum} 之间")
    return parsed


def _variant_label(variant: dict[str, Any], index: int) -> str:
    viewport = variant["viewport"]
    device = f"/{variant['device']}" if variant.get("device") else ""
    return f"{variant['browser']} {viewport['width']}x{viewport['height']}{device} ({index})"
