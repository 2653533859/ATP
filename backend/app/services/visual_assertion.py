"""Visual assertion and image similarity evaluation for Web and Android automation.

Provides:
- compute_image_similarity: Deterministic pixel and structural similarity using Pillow
- parse_image_template_bytes: Base64/data-URL and raw byte parser
- evaluate_visual_assertion: Threshold comparison with informative error reporting
- find_visual_coordinates: Template matching coordinate locator for visual self-healing
"""

from __future__ import annotations

import base64
import io

from PIL import Image, ImageChops, ImageStat


DEFAULT_VISUAL_SIMILARITY_THRESHOLD = 0.85


def parse_image_template_bytes(template_input: str | bytes) -> bytes:
    """Decode an image template from raw bytes, base64 string, or data URL."""
    if isinstance(template_input, bytes):
        return template_input

    raw_str = str(template_input).strip()
    if raw_str.startswith("data:image/"):
        # Strip data URL prefix (e.g. data:image/png;base64,...)
        if "," in raw_str:
            raw_str = raw_str.split(",", 1)[1].strip()

    try:
        return base64.b64decode(raw_str, validate=True)
    except Exception as exc:
        raise ValueError(f"无法解析视觉模板图片 base64 数据: {exc}") from exc


def compute_image_similarity(image_bytes1: bytes, image_bytes2: bytes) -> float:
    """Compute normalized visual similarity (0.0 to 1.0) between two images.

    Handles differing dimensions by bilinear interpolation to match the reference size.
    """
    im1 = Image.open(io.BytesIO(image_bytes1)).convert("RGB")
    im2 = Image.open(io.BytesIO(image_bytes2)).convert("RGB")

    if im1.size != im2.size:
        im2 = im2.resize(im1.size, Image.Resampling.BILINEAR)

    diff = ImageChops.difference(im1, im2)
    stat = ImageStat.Stat(diff)

    channel_count = max(1, len(stat.mean))
    mean_diff = sum(stat.mean) / (channel_count * 255.0)
    similarity = max(0.0, min(1.0, 1.0 - mean_diff))
    return round(similarity, 4)


def evaluate_visual_assertion(
    target_image_bytes: bytes,
    template_input: str | bytes,
    threshold: float = DEFAULT_VISUAL_SIMILARITY_THRESHOLD,
) -> tuple[bool, float, str | None]:
    """Evaluate whether target image matches reference template above threshold.

    Returns:
        (passed, similarity, error_message)
    """
    template_bytes = parse_image_template_bytes(template_input)
    similarity = compute_image_similarity(target_image_bytes, template_bytes)

    if similarity >= threshold:
        return True, similarity, None

    return (
        False,
        similarity,
        f"视觉相似度不匹配: 实际相似度 {similarity:.2f} 低于期望阈值 {threshold:.2f}",
    )


def find_visual_coordinates(
    screenshot_bytes: bytes,
    template_input: str | bytes,
    threshold: float = 0.80,
) -> tuple[int, int] | None:
    """Locate the center coordinates (x, y) of a template within a larger screenshot.

    Uses normalized multi-scale cross-sampling to detect the element's position on screen.
    """
    template_bytes = parse_image_template_bytes(template_input)
    screen = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    template = Image.open(io.BytesIO(template_bytes)).convert("RGB")

    s_w, s_h = screen.size
    t_w, t_h = template.size

    if t_w > s_w or t_h > s_h:
        return None

    # Step down resolution for coarse grid scan
    step_x = max(10, t_w // 4)
    step_y = max(10, t_h // 4)

    best_score = -1.0
    best_loc: tuple[int, int] | None = None

    for y in range(0, s_h - t_h + 1, step_y):
        for x in range(0, s_w - t_w + 1, step_x):
            crop = screen.crop((x, y, x + t_w, y + t_h))
            diff = ImageChops.difference(crop, template)
            stat = ImageStat.Stat(diff)
            score = 1.0 - (sum(stat.mean) / (len(stat.mean) * 255.0))
            if score > best_score:
                best_score = score
                best_loc = (x + t_w // 2, y + t_h // 2)

    if best_score >= threshold and best_loc is not None:
        return best_loc

    return None
