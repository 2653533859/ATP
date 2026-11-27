"""High-precision ``strict-v1`` visual template matching with SHA-256 binding and two-frame stability.

Implements the frozen ``strict-v1`` verification contract:
1. Template quality validation (minimum size, non-uniform content, valid edge energy) -> E2011.
2. Platform-scoped ``image_options`` with strict SHA-256 binding -> E2201 on mismatch.
3. Aspect-ratio distortion rejection (>3% drift) -> E2013.
4. Multi-scale normalized zero-mean cross-correlation (NCC) candidate discovery + NMS merge.
5. Full-resolution verification:
   - Bidirectional Sobel contour coverage >= 0.88 (threshold = max(8.0, p90(grad >= 8) / 4.0))
   - 4x4 block foreground error AND 16x16 stride-8 overlapping window foreground error <= 0.22
   - Spatial RGB color error <= 0.18
6. Multi-candidate ambiguity rejection -> E2010 (refuses to click when ambiguous).
7. Two-frame stability confirmation (~150ms interval, IoU >= 0.90, tap drift <= max(2px, 2% min side)) -> E2012.
8. ``assert_image(not_exists)`` requires two consecutive ``not_found`` frames (errors/invalid templates never pass).
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import math
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from PIL import Image

from app.services.execution_errors import (
    E2004_ASSERT_IMAGE_FAILED,
    E2005_IMAGE_NOT_MATCHED,
    E2010_IMAGE_AMBIGUOUS,
    E2011_IMAGE_TEMPLATE_INVALID,
    E2012_IMAGE_UNSTABLE,
    E2013_IMAGE_MATCH_UNSUPPORTED,
    E2201_INVALID_ARGS,
)

MATCHER_VERSION = "strict-v1"

# Frozen strict-v1 thresholds (never relaxed across retries)
MIN_TEMPLATE_SIDE = 12
MIN_GRADIENT_STRENGTH = 8.0
MIN_EDGE_PIXELS = 12
MIN_NCC_SCORE = 0.82
MIN_BIDIRECTIONAL_CONTOUR_COVERAGE = 0.88
MAX_FOREGROUND_BLOCK_ERROR = 0.22
MAX_COLOR_ERROR = 0.18
MIN_AMBIGUITY_MARGIN = 0.04
MIN_STABILITY_IOU = 0.90
STABILITY_FRAME_INTERVAL_SECONDS = 0.15
MAX_ASPECT_DRIFT = 0.03
DEFAULT_SCALES: tuple[float, ...] = (1.0, 0.9, 1.1, 0.8, 1.2)


_VISUAL_TEMPLATE_PATH_RE = re.compile(r"^visual-templates/projects/(\d+)/[A-Za-z0-9._-]+$")


def validate_visual_template_object_name(object_name: str, project_id: int | None) -> str:
    """Enforce project-scoped visual-templates/ MinIO prefix and block path traversal (P0 IDOR guard)."""
    cleaned = str(object_name or "").strip()
    if not cleaned or ".." in cleaned or "\\" in cleaned or cleaned.startswith("/"):
        raise ValueError("视觉模板对象路径非法，禁止路径穿越或绝对路径")
    matched = _VISUAL_TEMPLATE_PATH_RE.fullmatch(cleaned)
    if not matched:
        raise ValueError("视觉模板路径必须位于 visual-templates/projects/{project_id}/ 下")
    path_project_id = int(matched.group(1))
    if project_id is not None and path_project_id != int(project_id):
        raise PermissionError("视觉模板不属于当前项目，拒绝跨项目读取")
    return cleaned


def compute_template_sha256(template_bytes: bytes) -> str:
    return hashlib.sha256(template_bytes).hexdigest()


def select_platform_image_options(
    raw_options: dict[str, Any] | None,
    platform: str,
) -> dict[str, Any]:
    """Select platform-specific image_options.

    Priority: current platform -> default -> borrow only (template_sha256, tap_anchor)
    from the other platform when sharing the same template (stripping source_size & search_region).
    """
    if not isinstance(raw_options, dict):
        return {}
    plat = str(platform or "android").strip().lower()
    other = "ios" if plat == "android" else "android"

    if isinstance(raw_options.get(plat), dict) and raw_options[plat]:
        return dict(raw_options[plat])
    if isinstance(raw_options.get("default"), dict) and raw_options["default"]:
        return dict(raw_options["default"])
    if isinstance(raw_options.get(other), dict) and raw_options[other]:
        borrowed: dict[str, Any] = {}
        src = raw_options[other]
        if src.get("template_sha256"):
            borrowed["template_sha256"] = src["template_sha256"]
        if src.get("tap_anchor"):
            borrowed["tap_anchor"] = src["tap_anchor"]
        return borrowed
    # Flat options dict (already resolved)
    if any(k in raw_options for k in ("template_sha256", "tap_anchor", "source_size", "search_region")):
        return dict(raw_options)
    return {}


def validate_image_options(
    options: dict[str, Any],
    template_bytes: bytes,
    screen_size: tuple[int, int] | None = None,
) -> tuple[bool, str | None, str | None]:
    """Validate SHA-256 binding, anchor/region bounds, and aspect ratio compatibility.

    Returns ``(ok, error_code, error_message)``.
    """
    if not options:
        return True, None, None

    expected_sha = options.get("template_sha256")
    if expected_sha is not None:
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            return False, E2201_INVALID_ARGS, "template_sha256 必须为 64 位十六进制 SHA-256"
        actual_sha = compute_template_sha256(template_bytes)
        if actual_sha.lower() != expected_sha.lower():
            return False, E2201_INVALID_ARGS, "模板文件 SHA-256 与绑定配置不一致，请重新确认或截取模板"

    anchor = options.get("tap_anchor")
    if anchor is not None:
        if (
            not isinstance(anchor, (list, tuple))
            or len(anchor) != 2
            or not all(isinstance(v, (int, float)) and 0.0 <= float(v) <= 1.0 for v in anchor)
        ):
            return False, E2201_INVALID_ARGS, "tap_anchor 必须为 [u, v] 且在 0..1 范围内"

    region = options.get("search_region")
    if region is not None:
        if (
            not isinstance(region, (list, tuple))
            or len(region) != 4
            or not all(isinstance(v, (int, float)) and 0.0 <= float(v) <= 1.0 for v in region)
            or float(region[0]) >= float(region[2])
            or float(region[1]) >= float(region[3])
        ):
            return False, E2201_INVALID_ARGS, "search_region 必须为合法 [x1, y1, x2, y2] (0..1)"

    source_size = options.get("source_size")
    if source_size is not None and screen_size is not None:
        if (
            not isinstance(source_size, (list, tuple))
            or len(source_size) != 2
            or float(source_size[0]) <= 0
            or float(source_size[1]) <= 0
        ):
            return False, E2201_INVALID_ARGS, "source_size 必须为正整数 [width, height]"
        sx = screen_size[0] / float(source_size[0])
        sy = screen_size[1] / float(source_size[1])
        drift = abs(sx - sy) / max(sx, sy, 1e-6)
        if drift > MAX_ASPECT_DRIFT:
            return (
                False,
                E2013_IMAGE_MATCH_UNSUPPORTED,
                f"目标截图与录制源尺寸宽高比偏差 {drift:.1%} 超过 3%，拒绝形变推测",
            )

    return True, None, None


def _rgb_and_gray(img: Image.Image) -> tuple[list[tuple[int, int, int]], list[float], int, int]:
    rgb_img = img.convert("RGB")
    w, h = rgb_img.size
    rgb_pixels = list(rgb_img.getdata())
    gray = [0.299 * r + 0.587 * g + 0.114 * b for (r, g, b) in rgb_pixels]
    return rgb_pixels, gray, w, h


def _sobel_magnitude(gray: list[float], w: int, h: int) -> list[float]:
    """Compute Sobel gradient magnitude per pixel."""
    mag = [0.0] * (w * h)
    if w < 3 or h < 3:
        return mag
    for y in range(1, h - 1):
        row_up = (y - 1) * w
        row_mid = y * w
        row_dn = (y + 1) * w
        for x in range(1, w - 1):
            gx = (
                -gray[row_up + x - 1]
                + gray[row_up + x + 1]
                - 2.0 * gray[row_mid + x - 1]
                + 2.0 * gray[row_mid + x + 1]
                - gray[row_dn + x - 1]
                + gray[row_dn + x + 1]
            )
            gy = (
                -gray[row_up + x - 1]
                - 2.0 * gray[row_up + x]
                - gray[row_up + x + 1]
                + gray[row_dn + x - 1]
                + 2.0 * gray[row_dn + x]
                + gray[row_dn + x + 1]
            )
            # Normalize by 4 to match standard 0..255 edge scale
            mag[row_mid + x] = math.hypot(gx, gy) / 4.0
    return mag


def _edge_mask(mag: list[float]) -> tuple[list[bool], float, int]:
    """Strict-v1 contour threshold: max(8, p90(grad >= 8) / 4) to prevent JPEG noise on flat backgrounds."""
    valid = [g for g in mag if g >= MIN_GRADIENT_STRENGTH]
    if not valid:
        return [False] * len(mag), MIN_GRADIENT_STRENGTH, 0
    valid.sort()
    p90 = valid[min(len(valid) - 1, int(0.90 * (len(valid) - 1)))]
    threshold = max(MIN_GRADIENT_STRENGTH, p90 * 0.25)
    mask = [g >= threshold for g in mag]
    return mask, threshold, sum(1 for m in mask if m)


def _dilate_mask_1px(mask: list[bool], w: int, h: int) -> list[bool]:
    out = [False] * (w * h)
    for y in range(h):
        y0 = max(0, y - 1)
        y1 = min(h - 1, y + 1)
        for x in range(w):
            if not mask[y * w + x]:
                continue
            x0 = max(0, x - 1)
            x1 = min(w - 1, x + 1)
            for ny in range(y0, y1 + 1):
                base = ny * w
                for nx in range(x0, x1 + 1):
                    out[base + nx] = True
    return out


def validate_template_quality(template_bytes: bytes) -> tuple[bool, dict[str, Any], str | None]:
    """Reject tiny, flat, or contour-deficient templates (E2011)."""
    try:
        tpl_img = Image.open(io.BytesIO(template_bytes)).convert("RGB")
    except Exception as exc:
        return False, {"valid": False}, f"无法解码模板图片: {exc}"

    tw, th = tpl_img.size
    if tw < MIN_TEMPLATE_SIDE or th < MIN_TEMPLATE_SIDE:
        return (
            False,
            {"valid": False, "width": tw, "height": th},
            f"模板尺寸过小 ({tw}x{th})，最小要求 {MIN_TEMPLATE_SIDE}x{MIN_TEMPLATE_SIDE}",
        )

    _, gray, _, _ = _rgb_and_gray(tpl_img)
    mean_g = sum(gray) / len(gray)
    var_g = sum((v - mean_g) ** 2 for v in gray) / len(gray)
    std_g = math.sqrt(var_g)
    mag = _sobel_magnitude(gray, tw, th)
    _, edge_thr, edge_count = _edge_mask(mag)

    quality = {
        "valid": std_g >= 5.0 and edge_count >= MIN_EDGE_PIXELS,
        "width": tw,
        "height": th,
        "std": round(std_g, 2),
        "edge_pixels": edge_count,
        "edge_threshold": round(edge_thr, 2),
    }
    if not quality["valid"]:
        return False, quality, "模板内容接近纯色或缺少有效轮廓特征，请重新截取更清晰的目标"
    return True, quality, None


def _ncc_patch(
    screen_gray: list[float],
    sw: int,
    sx: int,
    sy: int,
    tpl_centered: list[float],
    tpl_norm: float,
    tw: int,
    th: int,
) -> float:
    n = tw * th
    patch_sum = 0.0
    patch_sq = 0.0
    dot = 0.0
    idx = 0
    for dy in range(th):
        row_off = (sy + dy) * sw + sx
        for dx in range(tw):
            pv = screen_gray[row_off + dx]
            patch_sum += pv
            patch_sq += pv * pv
            dot += pv * tpl_centered[idx]
            idx += 1
    patch_var = patch_sq - (patch_sum * patch_sum) / n
    if patch_var <= 1e-6:
        return -1.0
    return dot / (math.sqrt(patch_var) * tpl_norm)


def _verify_candidate_full_res(
    screen_rgb: list[tuple[int, int, int]],
    screen_gray: list[float],
    sw: int,
    sx: int,
    sy: int,
    tpl_rgb: list[tuple[int, int, int]],
    tpl_gray: list[float],
    tpl_edges: list[bool],
    tpl_edges_dilated: list[bool],
    tw: int,
    th: int,
) -> dict[str, Any]:
    """Full-resolution strict-v1 verification: bidirectional contour, 4x4 & 16x16 fg error, color error."""
    n = tw * th
    patch_rgb: list[tuple[int, int, int]] = []
    patch_gray: list[float] = []
    color_diff_sum = 0.0

    for dy in range(th):
        row_off = (sy + dy) * sw + sx
        t_row = dy * tw
        for dx in range(tw):
            sp = screen_rgb[row_off + dx]
            tp = tpl_rgb[t_row + dx]
            patch_rgb.append(sp)
            patch_gray.append(screen_gray[row_off + dx])
            color_diff_sum += (abs(sp[0] - tp[0]) + abs(sp[1] - tp[1]) + abs(sp[2] - tp[2])) / (3.0 * 255.0)

    color_error = color_diff_sum / max(1, n)

    # 1. Bidirectional Sobel contour coverage
    patch_mag = _sobel_magnitude(patch_gray, tw, th)
    patch_edges, _, patch_edge_count = _edge_mask(patch_mag)
    patch_edges_dilated = _dilate_mask_1px(patch_edges, tw, th)

    tpl_edge_total = sum(1 for e in tpl_edges if e)
    fwd_hits = sum(1 for i in range(n) if tpl_edges[i] and patch_edges_dilated[i])
    rev_hits = sum(1 for i in range(n) if patch_edges[i] and tpl_edges_dilated[i])
    fwd_cov = fwd_hits / max(1, tpl_edge_total)
    rev_cov = rev_hits / max(1, patch_edge_count) if patch_edge_count > 0 else 0.0
    bi_contour = min(fwd_cov, rev_cov)

    # 2. Foreground pixel error: 4x4 grid blocks + 16x16 stride-8 overlapping windows (min 8 fg pixels)
    fg_mask = tpl_edges_dilated
    max_block_err = 0.0

    # 4x4 blocks
    bw = max(1, tw // 4)
    bh = max(1, th // 4)
    for by in range(4):
        y0 = by * bh
        y1 = th if by == 3 else min(th, (by + 1) * bh)
        for bx in range(4):
            x0 = bx * bw
            x1 = tw if bx == 3 else min(tw, (bx + 1) * bw)
            err_sum = 0.0
            fg_cnt = 0
            for yy in range(y0, y1):
                ro = yy * tw
                for xx in range(x0, x1):
                    idx = ro + xx
                    if fg_mask[idx]:
                        err_sum += abs(patch_gray[idx] - tpl_gray[idx]) / 255.0
                        fg_cnt += 1
            if fg_cnt >= 8:
                max_block_err = max(max_block_err, err_sum / fg_cnt)

    # 16x16 stride-8 overlapping windows (catches single-digit differences like "Order 1" vs "Order 2")
    if tw >= 16 and th >= 16:
        for wy in range(0, th - 15, 8):
            for wx in range(0, tw - 15, 8):
                err_sum = 0.0
                fg_cnt = 0
                for yy in range(wy, wy + 16):
                    ro = yy * tw
                    for xx in range(wx, wx + 16):
                        idx = ro + xx
                        if fg_mask[idx]:
                            err_sum += abs(patch_gray[idx] - tpl_gray[idx]) / 255.0
                            fg_cnt += 1
                if fg_cnt >= 8:
                    max_block_err = max(max_block_err, err_sum / fg_cnt)

    passed = (
        bi_contour >= MIN_BIDIRECTIONAL_CONTOUR_COVERAGE
        and max_block_err <= MAX_FOREGROUND_BLOCK_ERROR
        and color_error <= MAX_COLOR_ERROR
    )
    return {
        "passed": passed,
        "bidirectional_contour": round(bi_contour, 4),
        "forward_contour": round(fwd_cov, 4),
        "reverse_contour": round(rev_cov, 4),
        "max_fg_window_error": round(max_block_err, 4),
        "color_error": round(color_error, 4),
    }


def compute_box_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / max(1, union)


def match_image_strict_single_frame(
    screenshot_bytes: bytes,
    template_bytes: bytes,
    *,
    image_options: dict[str, Any] | None = None,
    platform: str = "android",
    scales: tuple[float, ...] | None = None,
) -> dict[str, Any]:
    """Execute one full ``strict-v1`` frame match and return structured diagnostics."""
    t0 = time.monotonic()
    resolved_opts = select_platform_image_options(image_options, platform)

    quality_ok, quality, quality_err = validate_template_quality(template_bytes)
    if not quality_ok:
        return {
            "status": "invalid_template",
            "error_code": E2011_IMAGE_TEMPLATE_INVALID,
            "reason": quality_err,
            "matcher_version": MATCHER_VERSION,
            "candidates": [],
            "point": None,
            "quality": quality,
            "timings": {"total_ms": round((time.monotonic() - t0) * 1000, 2)},
        }

    try:
        screen_img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
        tpl_img_orig = Image.open(io.BytesIO(template_bytes)).convert("RGB")
    except Exception as exc:
        return {
            "status": "invalid_template",
            "error_code": E2011_IMAGE_TEMPLATE_INVALID,
            "reason": f"截图或模板解码失败: {exc}",
            "matcher_version": MATCHER_VERSION,
            "candidates": [],
            "point": None,
            "quality": quality,
            "timings": {"total_ms": round((time.monotonic() - t0) * 1000, 2)},
        }

    sw_full, sh_full = screen_img.size
    opts_ok, opts_code, opts_err = validate_image_options(resolved_opts, template_bytes, (sw_full, sh_full))
    if not opts_ok:
        return {
            "status": "invalid_options",
            "error_code": opts_code,
            "reason": opts_err,
            "matcher_version": MATCHER_VERSION,
            "candidates": [],
            "point": None,
            "quality": quality,
            "timings": {"total_ms": round((time.monotonic() - t0) * 1000, 2)},
        }

    # Crop search_region if configured
    reg = resolved_opts.get("search_region")
    if isinstance(reg, (list, tuple)) and len(reg) == 4:
        off_x = int(round(float(reg[0]) * sw_full))
        off_y = int(round(float(reg[1]) * sh_full))
        end_x = int(round(float(reg[2]) * sw_full))
        end_y = int(round(float(reg[3]) * sh_full))
        roi_img = screen_img.crop((off_x, off_y, end_x, end_y))
    else:
        off_x, off_y = 0, 0
        roi_img = screen_img

    screen_rgb, screen_gray, sw, sh = _rgb_and_gray(roi_img)

    # Determine scales (use source_size scale hint when available)
    if scales is not None:
        search_scales = scales
    elif isinstance(resolved_opts.get("source_size"), (list, tuple)) and len(resolved_opts["source_size"]) == 2:
        hint = sw_full / max(1.0, float(resolved_opts["source_size"][0]))
        search_scales = tuple(sorted({round(hint, 3), round(hint * 0.95, 3), round(hint * 1.05, 3)}))
    else:
        search_scales = DEFAULT_SCALES

    raw_qualified: list[dict[str, Any]] = []

    for scale in search_scales:
        tw = int(round(tpl_img_orig.size[0] * scale))
        th = int(round(tpl_img_orig.size[1] * scale))
        if tw < MIN_TEMPLATE_SIDE or th < MIN_TEMPLATE_SIDE or tw > sw or th > sh:
            continue
        tpl_scaled = (
            tpl_img_orig if abs(scale - 1.0) < 1e-3 else tpl_img_orig.resize((tw, th), Image.Resampling.BILINEAR)
        )
        tpl_rgb, tpl_gray, _, _ = _rgb_and_gray(tpl_scaled)
        t_mean = sum(tpl_gray) / len(tpl_gray)
        tpl_centered = [v - t_mean for v in tpl_gray]
        tpl_norm = math.sqrt(sum(v * v for v in tpl_centered))
        if tpl_norm <= 1e-6:
            continue

        # Coarse-to-fine NCC scan on 2x bilinear-downsampled images so sharp edges remain smooth across grid shifts
        coarse_factor = 2 if (tw >= 20 and th >= 20) else 1
        if coarse_factor == 2:
            cw, ch = max(8, tw // 2), max(8, th // 2)
            sw_c, sh_c = max(cw, sw // 2), max(ch, sh // 2)
            _, screen_gray_c, _, _ = _rgb_and_gray(roi_img.resize((sw_c, sh_c), Image.Resampling.BILINEAR))
            _, tpl_gray_c, _, _ = _rgb_and_gray(tpl_scaled.resize((cw, ch), Image.Resampling.BILINEAR))
            tc_mean = sum(tpl_gray_c) / len(tpl_gray_c)
            tc_centered = [v - tc_mean for v in tpl_gray_c]
            tc_norm = math.sqrt(sum(v * v for v in tc_centered))
            coarse_stride = 2
            coarse_hits: list[tuple[float, int, int]] = []
            if tc_norm > 1e-6:
                for cy in range(0, sh_c - ch + 1, coarse_stride):
                    for cx in range(0, sw_c - cw + 1, coarse_stride):
                        score = _ncc_patch(screen_gray_c, sw_c, cx, cy, tc_centered, tc_norm, cw, ch)
                        if score >= 0.55:
                            coarse_hits.append((score, cx * 2, cy * 2))
            refine_radius_x = 4
            refine_radius_y = 4
        else:
            stride_x = max(1, min(3, tw // 6))
            stride_y = max(1, min(3, th // 6))
            coarse_hits = []
            for y in range(0, sh - th + 1, stride_y):
                for x in range(0, sw - tw + 1, stride_x):
                    score = _ncc_patch(screen_gray, sw, x, y, tpl_centered, tpl_norm, tw, th)
                    if score >= 0.55:
                        coarse_hits.append((score, x, y))
            refine_radius_x = stride_x
            refine_radius_y = stride_y

        if not coarse_hits:
            continue

        # Sort coarse peaks & suppress immediate neighbors before pixel refinement
        coarse_hits.sort(key=lambda item: item[0], reverse=True)
        refined_peaks: list[tuple[float, int, int]] = []
        for c_score, cx, cy in coarse_hits[:80]:
            if any(abs(cx - px) < tw // 2 and abs(cy - py) < th // 2 for _, px, py in refined_peaks):
                continue
            best_s, best_x, best_y = -1.0, cx, cy
            rx0, rx1 = max(0, cx - refine_radius_x), min(sw - tw, cx + refine_radius_x)
            ry0, ry1 = max(0, cy - refine_radius_y), min(sh - th, cy + refine_radius_y)
            for ry in range(ry0, ry1 + 1):
                for rx in range(rx0, rx1 + 1):
                    s = _ncc_patch(screen_gray, sw, rx, ry, tpl_centered, tpl_norm, tw, th)
                    if s > best_s:
                        best_s, best_x, best_y = s, rx, ry
            if best_s >= MIN_NCC_SCORE:
                refined_peaks.append((best_s, best_x, best_y))
            if len(refined_peaks) >= 8:
                break

        if not refined_peaks:
            continue

        tpl_mag = _sobel_magnitude(tpl_gray, tw, th)
        tpl_edges, _, _ = _edge_mask(tpl_mag)
        tpl_edges_dilated = _dilate_mask_1px(tpl_edges, tw, th)

        for ncc_score, px, py in refined_peaks:
            ver = _verify_candidate_full_res(
                screen_rgb,
                screen_gray,
                sw,
                px,
                py,
                tpl_rgb,
                tpl_gray,
                tpl_edges,
                tpl_edges_dilated,
                tw,
                th,
            )
            if ver["passed"]:
                box = (off_x + px, off_y + py, off_x + px + tw, off_y + py + th)
                raw_qualified.append(
                    {
                        "box": list(box),
                        "scale": scale,
                        "ncc": round(ncc_score, 4),
                        **ver,
                    }
                )

    # Merge multi-scale detections of the same physical object (NMS IoU >= 0.4)
    raw_qualified.sort(key=lambda c: (c["ncc"], c["bidirectional_contour"]), reverse=True)
    merged: list[dict[str, Any]] = []
    for cand in raw_qualified:
        c_box = tuple(cand["box"])
        if any(compute_box_iou(c_box, tuple(m["box"])) >= 0.4 for m in merged):
            continue
        merged.append(cand)

    elapsed_ms = round((time.monotonic() - t0) * 1000, 2)
    anchor = resolved_opts.get("tap_anchor") or [0.5, 0.5]
    u, v = float(anchor[0]), float(anchor[1])

    if not merged:
        return {
            "status": "not_found",
            "error_code": E2005_IMAGE_NOT_MATCHED,
            "reason": "未找到通过 strict-v1 全量结构校验的候选目标",
            "matcher_version": MATCHER_VERSION,
            "candidates": [],
            "point": None,
            "quality": quality,
            "timings": {"total_ms": elapsed_ms},
        }

    if len(merged) > 1:
        # Strict-v1: multiple independent qualified targets are always ambiguous for clicking
        return {
            "status": "ambiguous",
            "error_code": E2010_IMAGE_AMBIGUOUS,
            "reason": f"检测到 {len(merged)} 个相似合格候选目标，拒绝盲点",
            "matcher_version": MATCHER_VERSION,
            "candidates": merged[:5],
            "point": None,
            "quality": quality,
            "timings": {"total_ms": elapsed_ms},
        }

    best = merged[0]
    bx1, by1, bx2, by2 = best["box"]
    point = [int(round(bx1 + (bx2 - bx1) * u)), int(round(by1 + (by2 - by1) * v))]
    return {
        "status": "matched",
        "error_code": None,
        "reason": "ok",
        "matcher_version": MATCHER_VERSION,
        "candidates": merged,
        "point": point,
        "quality": quality,
        "timings": {"total_ms": elapsed_ms},
    }


async def locate_image_two_frame_stable(
    capture_frame: Callable[[], Awaitable[bytes | None]],
    template_bytes: bytes,
    *,
    image_options: dict[str, Any] | None = None,
    platform: str = "android",
    timeout_seconds: float = 10.0,
    frame_interval_seconds: float = STABILITY_FRAME_INTERVAL_SECONDS,
    scales: tuple[float, ...] | None = None,
    check_cancel: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Two-frame stability state machine for ``click_image``.

    Requires two consecutive frames (~150ms apart) both matching a unique qualified target with
    box IoU >= 0.90 and tap-point drift <= max(2px, 2% of template short side).
    """
    deadline = time.monotonic() + max(0.2, float(timeout_seconds))
    frames_checked = 0
    ever_matched = False
    prev_match: dict[str, Any] | None = None
    last_diag: dict[str, Any] | None = None

    while True:
        if check_cancel is not None:
            check_cancel()
        frame = await capture_frame()
        if not frame:
            return {
                "status": "not_found",
                "error_code": E2005_IMAGE_NOT_MATCHED,
                "reason": "无法获取设备截图",
                "matcher_version": MATCHER_VERSION,
                "frames_checked": frames_checked,
                "candidates": [],
                "point": None,
            }

        frames_checked += 1
        diag = await asyncio.to_thread(
            match_image_strict_single_frame,
            frame,
            template_bytes,
            image_options=image_options,
            platform=platform,
            scales=scales,
        )
        diag["frames_checked"] = frames_checked
        last_diag = diag

        # Immediate terminal errors (invalid template / bad SHA / aspect mismatch)
        if diag["status"] in {"invalid_template", "invalid_options"}:
            return diag

        if diag["status"] == "matched":
            ever_matched = True
            if prev_match is not None:
                box_a = tuple(prev_match["candidates"][0]["box"])
                box_b = tuple(diag["candidates"][0]["box"])
                iou = compute_box_iou(box_a, box_b)
                pt_a = prev_match["point"]
                pt_b = diag["point"]
                drift = math.hypot(pt_a[0] - pt_b[0], pt_a[1] - pt_b[1])
                short_side = min(box_b[2] - box_b[0], box_b[3] - box_b[1])
                max_drift = max(2.0, short_side * 0.02)
                if iou >= MIN_STABILITY_IOU and drift <= max_drift:
                    diag["stable"] = True
                    diag["stability_iou"] = round(iou, 4)
                    diag["stability_drift_px"] = round(drift, 2)
                    return diag
            prev_match = diag
        else:
            prev_match = None
            if diag["status"] == "ambiguous":
                return diag

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        await asyncio.sleep(min(frame_interval_seconds, remaining))

    # Timeout reached
    if ever_matched:
        return {
            **(last_diag or {}),
            "status": "target_not_stable",
            "error_code": E2012_IMAGE_UNSTABLE,
            "reason": "目标曾被识别但在超时预算内未能连续两帧稳定",
            "timed_out": True,
            "timeout_reason": "target_not_stable",
            "frames_checked": frames_checked,
            "point": None,
        }
    return {
        **(last_diag or {}),
        "status": "not_found",
        "error_code": E2005_IMAGE_NOT_MATCHED,
        "reason": "超时预算内未找到通过严格校验的模板目标",
        "timed_out": True,
        "timeout_reason": "not_found",
        "frames_checked": frames_checked,
        "point": None,
    }


async def assert_image_strict(
    capture_frame: Callable[[], Awaitable[bytes | None]],
    template_bytes: bytes,
    *,
    match_mode: Literal["exists", "not_exists"] = "exists",
    image_options: dict[str, Any] | None = None,
    platform: str = "android",
    timeout_seconds: float = 10.0,
    frame_interval_seconds: float = STABILITY_FRAME_INTERVAL_SECONDS,
    scales: tuple[float, ...] | None = None,
    check_cancel: Callable[[], None] | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Strict image existence / non-existence assertion.

    - ``exists``: passes as soon as >=1 qualified candidate appears (including multiple duplicates).
    - ``not_exists``: passes ONLY after two consecutive frames return explicit ``not_found``.
      Invalid templates, bad SHA, or unsupported ratios NEVER pass ``not_exists``.
    """
    deadline = time.monotonic() + max(0.2, float(timeout_seconds))
    frames_checked = 0
    consecutive_not_found = 0
    last_diag: dict[str, Any] | None = None

    while True:
        if check_cancel is not None:
            check_cancel()
        frame = await capture_frame()
        if not frame:
            return False, {
                "status": "capture_failed",
                "error_code": E2004_ASSERT_IMAGE_FAILED,
                "reason": "无法获取设备截图，图像断言失败",
                "matcher_version": MATCHER_VERSION,
                "frames_checked": frames_checked,
            }

        frames_checked += 1
        diag = await asyncio.to_thread(
            match_image_strict_single_frame,
            frame,
            template_bytes,
            image_options=image_options,
            platform=platform,
            scales=scales,
        )
        diag["frames_checked"] = frames_checked
        last_diag = diag

        if diag["status"] in {"invalid_template", "invalid_options"}:
            return False, diag

        has_qualified = diag["status"] in {"matched", "ambiguous"} and len(diag.get("candidates") or []) > 0
        if match_mode == "exists":
            if has_qualified:
                diag["assertion_passed"] = True
                return True, diag
        else:
            if has_qualified:
                diag["assertion_passed"] = False
                diag["error_code"] = E2004_ASSERT_IMAGE_FAILED
                diag["reason"] = "期望图像不存在，但当前帧检测到合格目标"
                return False, diag
            if diag["status"] == "not_found":
                consecutive_not_found += 1
                if consecutive_not_found >= 2:
                    diag["assertion_passed"] = True
                    return True, diag

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        await asyncio.sleep(min(frame_interval_seconds, remaining))

    return False, {
        **(last_diag or {}),
        "assertion_passed": False,
        "error_code": E2004_ASSERT_IMAGE_FAILED,
        "reason": "图像存在断言超时未命中" if match_mode == "exists" else "图像不存在断言未取得连续两帧确认",
        "timed_out": True,
        "frames_checked": frames_checked,
    }


def crop_lossless_png_template(
    screenshot_bytes: bytes,
    *,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    click_point: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Crop lossless PNG template from full-res screenshot and return SHA-256 + anchor metadata."""
    img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    sw, sh = img.size
    cx1, cy1 = max(0, min(sw, int(x1))), max(0, min(sh, int(y1)))
    cx2, cy2 = max(0, min(sw, int(x2))), max(0, min(sh, int(y2)))
    if cx2 <= cx1 or cy2 <= cy1:
        raise ValueError("裁切区域无效，必须满足 x2 > x1 且 y2 > y1")

    cropped = img.crop((cx1, cy1, cx2, cy2))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    sha = compute_template_sha256(png_bytes)
    ok, quality, err = validate_template_quality(png_bytes)

    if click_point is not None and cx1 <= click_point[0] <= cx2 and cy1 <= click_point[1] <= cy2:
        u = round((click_point[0] - cx1) / max(1, cx2 - cx1), 4)
        v = round((click_point[1] - cy1) / max(1, cy2 - cy1), 4)
    else:
        u, v = 0.5, 0.5

    return {
        "png_bytes": png_bytes,
        "template_sha256": sha,
        "source_size": [sw, sh],
        "tap_anchor": [u, v],
        "quality_ok": ok,
        "quality": quality,
        "quality_error": err,
    }
