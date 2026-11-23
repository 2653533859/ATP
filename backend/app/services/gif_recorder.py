"""Execution GIF recorder.

Composes ordered step screenshots from test executions into a lightweight,
animated GIF summary with step watermark overlays.  The resulting GIF can be
previewed in the test run workbench, embedded in reports, or copied into bug
trackers without requiring video codecs.
"""

from __future__ import annotations

import io
import logging
from typing import Any, Sequence

from PIL import Image, ImageDraw, ImageFont

from app.core.minio_client import presigned_url, read_bytes, upload_bytes

logger = logging.getLogger(__name__)

# Fallback fonts searched in order across Windows, Linux and macOS
_SYSTEM_FONT_CANDIDATES = (
    # Windows
    "msyh.ttc",
    "simhei.ttf",
    "simsun.ttc",
    "arial.ttf",
    # Debian/Ubuntu container paths
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
)


def _resolve_font(size: int = 14) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for candidate in _SYSTEM_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _render_step_watermark(
    base_img: Image.Image,
    label: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
) -> Image.Image:
    """Draw a semi-transparent dark banner at the bottom with step information."""
    if not label:
        return base_img

    img = base_img.copy()
    banner_height = max(28, int(img.height * 0.055))
    banner_y = max(0, img.height - banner_height)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.rectangle([(0, banner_y), (img.width, img.height)], fill=(15, 23, 42, 215))

    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    text_x = 12
    text_y = banner_y + max(4, (banner_height - 16) // 2)
    try:
        draw.text((text_x, text_y), label, fill=(248, 250, 252), font=font)
    except Exception:
        # Fallback to plain ASCII if specific characters fail rendering
        ascii_label = label.encode("ascii", "replace").decode("ascii")
        draw.text((text_x, text_y), ascii_label, fill=(248, 250, 252))

    return img


def compose_gif_from_frames(
    frames: Sequence[tuple[bytes, str | None]],
    *,
    duration_per_frame_ms: int = 1200,
    max_width: int = 960,
) -> bytes:
    """Compose raw screenshot byte frames into an optimized animated GIF buffer.

    Args:
        frames: Sequence of (image_bytes, optional_step_label) tuples in chronological order.
        duration_per_frame_ms: Display duration for each frame in milliseconds.
        max_width: Maximum image width; frames are downscaled proportionally to save bandwidth.

    Returns:
        Encoded animated GIF bytes.
    """
    if not frames:
        return b""

    font = _resolve_font(size=14)
    processed_images: list[Image.Image] = []

    for raw_bytes, label in frames:
        if not raw_bytes:
            continue
        try:
            with Image.open(io.BytesIO(raw_bytes)) as source:
                # Normalize color space to RGB
                if source.mode in ("RGBA", "LA") or (source.mode == "P" and "transparency" in source.info):
                    alpha = source.convert("RGBA")
                    bg = Image.new("RGBA", alpha.size, (255, 255, 255, 255))
                    bg.paste(alpha, mask=alpha.split()[3])
                    img = bg.convert("RGB")
                else:
                    img = source.convert("RGB")

                # Scale down if width exceeds max_width
                if img.width > max_width and max_width > 0:
                    scaled_height = max(1, int(img.height * (max_width / img.width)))
                    img = img.resize((max_width, scaled_height), Image.Resampling.LANCZOS)

                if label:
                    img = _render_step_watermark(img, label, font)

                # Quantize with adaptive palette for crisp rendering and low file size
                paletted = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
                processed_images.append(paletted)
        except Exception as exc:
            logger.warning("Failed to decode screenshot frame for GIF: %s", exc)
            continue

    if not processed_images:
        return b""

    out = io.BytesIO()
    first_frame = processed_images[0]
    additional_frames = processed_images[1:]

    first_frame.save(
        out,
        format="GIF",
        save_all=True,
        append_images=additional_frames,
        duration=max(200, int(duration_per_frame_ms)),
        loop=0,
        optimize=True,
    )
    return out.getvalue()


def generate_and_upload_run_gif(
    run_id: int,
    frames: Sequence[tuple[bytes, str | None]],
    *,
    duration_per_frame_ms: int = 1200,
    max_width: int = 960,
) -> str | None:
    """Compose frames and upload the resulting animated GIF to MinIO / local storage."""
    gif_bytes = compose_gif_from_frames(
        frames,
        duration_per_frame_ms=duration_per_frame_ms,
        max_width=max_width,
    )
    if not gif_bytes:
        return None

    obj_name = f"gifs/runs/{run_id}/recording.gif"
    try:
        upload_bytes(obj_name, gif_bytes, "image/gif")
        return presigned_url(obj_name)
    except Exception as exc:
        logger.warning("Failed to upload GIF recording for run %s: %s", run_id, exc)
        return None


def generate_gif_from_run_step_records(
    run_id: int,
    steps: Sequence[Any],
    *,
    duration_per_frame_ms: int = 1200,
) -> str | None:
    """Extract screenshots from persisted StepResult items and compose a GIF."""
    frames: list[tuple[bytes, str | None]] = []

    # Sort by step_index
    sorted_steps = sorted(steps, key=lambda s: getattr(s, "step_index", 0))

    for step in sorted_steps:
        idx = getattr(step, "step_index", 0)
        name = getattr(step, "name", "") or f"Step {idx}"
        status_val = getattr(getattr(step, "status", None), "value", None) or getattr(step, "status", "")
        status_tag = f" [{status_val}]" if status_val else ""
        label = f"步骤 {idx}: {name}{status_tag}"

        obj_name = f"screenshots/runs/{run_id}/step_{idx}.png"
        try:
            raw_bytes = read_bytes(obj_name)
            if raw_bytes:
                frames.append((raw_bytes, label))
        except Exception:
            continue

    if not frames:
        return None

    return generate_and_upload_run_gif(
        run_id,
        frames,
        duration_per_frame_ms=duration_per_frame_ms,
    )
