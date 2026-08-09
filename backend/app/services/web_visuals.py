"""Bounded PNG comparison for Web visual regression assertions."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable

from PIL import Image, ImageChops

MAX_VISUAL_PIXELS = 20_000_000


class VisualCompareError(ValueError):
    """Raised when a visual baseline or screenshot is not a supported image."""


def _load_png(data: bytes) -> Image.Image:
    try:
        image = Image.open(BytesIO(data)).convert("RGBA")
        image.load()
    except Exception as exc:
        raise VisualCompareError("视觉基线必须是有效 PNG 图片") from exc
    if image.width * image.height > MAX_VISUAL_PIXELS:
        raise VisualCompareError("视觉图片尺寸超过限制")
    return image


def _ignore_mask(size: tuple[int, int], regions: Iterable[dict[str, Any]]) -> Image.Image:
    mask = Image.new("1", size, 0)
    pixels = mask.load()
    if pixels is None:
        raise VisualCompareError("无法创建视觉忽略区域掩码")
    width, height = size
    for region in regions:
        if not isinstance(region, dict):
            continue
        try:
            left = max(0, int(region.get("x", 0)))
            top = max(0, int(region.get("y", 0)))
            right = min(width, left + max(0, int(region.get("width", 0))))
            bottom = min(height, top + max(0, int(region.get("height", 0))))
        except (TypeError, ValueError):
            continue
        for y in range(top, bottom):
            for x in range(left, right):
                pixels[x, y] = 1
    return mask


def compare_png_bytes(
    baseline_bytes: bytes,
    current_bytes: bytes,
    *,
    threshold: float = 0.01,
    pixel_threshold: int = 10,
    ignore_regions: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Return a deterministic diff summary and a PNG diff artifact."""
    if not 0 <= threshold <= 1:
        raise VisualCompareError("视觉差异阈值必须在 0 到 1 之间")
    if not 0 <= pixel_threshold <= 255:
        raise VisualCompareError("像素差异阈值必须在 0 到 255 之间")
    baseline = _load_png(baseline_bytes)
    current = _load_png(current_bytes)
    if baseline.size != current.size:
        return {
            "match": False,
            "reason": "image_size_mismatch",
            "baseline_size": list(baseline.size),
            "current_size": list(current.size),
            "diff_ratio": 1.0,
            "changed_pixels": baseline.width * baseline.height,
            "total_pixels": baseline.width * baseline.height,
            "diff_png": None,
        }

    diff = ImageChops.difference(baseline, current)
    diff_pixels = diff.load()
    if diff_pixels is None:
        raise VisualCompareError("无法创建视觉差异图")
    ignored = _ignore_mask(baseline.size, ignore_regions)
    ignored_pixels = ignored.load()
    if ignored_pixels is None:
        raise VisualCompareError("无法读取视觉忽略区域掩码")
    changed = 0
    total = baseline.width * baseline.height
    for y in range(baseline.height):
        for x in range(baseline.width):
            if ignored_pixels[x, y]:
                diff_pixels[x, y] = (0, 0, 0, 0)
                continue
            pixel = diff_pixels[x, y]
            difference = max(int(channel) for channel in pixel) if isinstance(pixel, tuple) else int(pixel)
            if difference > pixel_threshold:
                changed += 1
            else:
                diff_pixels[x, y] = (0, 0, 0, 0)

    diff_buffer = BytesIO()
    diff.save(diff_buffer, format="PNG")
    ratio = changed / total if total else 0.0
    return {
        "match": ratio <= threshold,
        "reason": "within_threshold" if ratio <= threshold else "pixel_difference_exceeded",
        "diff_ratio": ratio,
        "changed_pixels": changed,
        "total_pixels": total,
        "width": baseline.width,
        "height": baseline.height,
        "diff_png": diff_buffer.getvalue(),
    }
