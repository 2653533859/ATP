"""Unit tests for strict-v1 visual template matching, SHA-256 binding, disambiguation, and two-frame stability."""

from __future__ import annotations

import asyncio
import io

from PIL import Image, ImageDraw

from app.services.execution_errors import (
    E2005_IMAGE_NOT_MATCHED,
    E2010_IMAGE_AMBIGUOUS,
    E2011_IMAGE_TEMPLATE_INVALID,
    E2012_IMAGE_UNSTABLE,
    E2013_IMAGE_MATCH_UNSUPPORTED,
    E2201_INVALID_ARGS,
)
from app.services.strict_image_matcher import (
    assert_image_strict,
    compute_template_sha256,
    crop_lossless_png_template,
    locate_image_two_frame_stable,
    match_image_strict_single_frame,
    select_platform_image_options,
)


def _to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _draw_icon(draw: ImageDraw.ImageDraw, x: int, y: int, *, variant: int = 1) -> None:
    """Draw a high-contrast structured icon (40x32) with distinct inner geometry per variant."""
    draw.rectangle([x, y, x + 39, y + 31], fill=(245, 248, 255), outline=(25, 60, 140), width=2)
    draw.rectangle([x + 4, y + 4, x + 15, y + 27], fill=(20, 110, 220))
    if variant == 1:
        # Distinct vertical bar (like "1") on right half
        draw.rectangle([x + 25, y + 6, x + 30, y + 25], fill=(220, 45, 45))
    else:
        # Distinct Z/2-like bars on right half (like "Order 2" vs "Order 1")
        draw.rectangle([x + 20, y + 6, x + 34, y + 10], fill=(220, 45, 45))
        draw.rectangle([x + 20, y + 14, x + 34, y + 18], fill=(220, 45, 45))
        draw.rectangle([x + 20, y + 22, x + 34, y + 26], fill=(220, 45, 45))


def _make_screen_and_template(positions: list[tuple[int, int, int]]) -> tuple[bytes, bytes]:
    screen = Image.new("RGB", (200, 160), (235, 238, 242))
    draw = ImageDraw.Draw(screen)
    for x, y, var in positions:
        _draw_icon(draw, x, y, variant=var)

    tpl = Image.new("RGB", (40, 32), (235, 238, 242))
    _draw_icon(ImageDraw.Draw(tpl), 0, 0, variant=1)
    return _to_png_bytes(screen), _to_png_bytes(tpl)


def test_template_quality_sha_binding_and_aspect_ratio_guards():
    # Solid color template rejected -> E2011
    solid = _to_png_bytes(Image.new("RGB", (40, 40), (128, 128, 128)))
    screen, tpl = _make_screen_and_template([(50, 40, 1)])
    res_solid = match_image_strict_single_frame(screen, solid, scales=(1.0,))
    assert res_solid["status"] == "invalid_template"
    assert res_solid["error_code"] == E2011_IMAGE_TEMPLATE_INVALID

    # Wrong SHA-256 rejected -> E2201
    res_sha = match_image_strict_single_frame(
        screen,
        tpl,
        image_options={"android": {"template_sha256": "0" * 64}},
        platform="android",
        scales=(1.0,),
    )
    assert res_sha["status"] == "invalid_options"
    assert res_sha["error_code"] == E2201_INVALID_ARGS

    # Aspect ratio drift > 3% rejected -> E2013
    res_aspect = match_image_strict_single_frame(
        screen,
        tpl,
        image_options={"android": {"template_sha256": compute_template_sha256(tpl), "source_size": [200, 300]}},
        platform="android",
        scales=(1.0,),
    )
    assert res_aspect["status"] == "invalid_options"
    assert res_aspect["error_code"] == E2013_IMAGE_MATCH_UNSUPPORTED

    # Cross-platform borrow strips source_size and search_region
    borrowed = select_platform_image_options(
        {
            "android": {
                "template_sha256": compute_template_sha256(tpl),
                "tap_anchor": [0.25, 0.75],
                "source_size": [1080, 2400],
                "search_region": [0, 0, 0.5, 0.5],
            }
        },
        platform="ios",
    )
    assert borrowed == {"template_sha256": compute_template_sha256(tpl), "tap_anchor": [0.25, 0.75]}


def test_single_frame_matches_exact_rejects_variant2_and_rejects_duplicate_ambiguity():
    # Exact match passes with accurate tap point
    screen_ok, tpl = _make_screen_and_template([(60, 50, 1)])
    res_ok = match_image_strict_single_frame(
        screen_ok,
        tpl,
        image_options={"android": {"template_sha256": compute_template_sha256(tpl), "tap_anchor": [0.5, 0.5]}},
        scales=(1.0,),
    )
    assert res_ok["status"] == "matched"
    assert abs(res_ok["point"][0] - 80) <= 2
    assert abs(res_ok["point"][1] - 66) <= 2

    # Variant 2 (similar frame, different foreground shape like Order 2 vs Order 1) MUST NOT match
    screen_v2, _ = _make_screen_and_template([(60, 50, 2)])
    res_v2 = match_image_strict_single_frame(screen_v2, tpl, scales=(1.0,))
    assert res_v2["status"] == "not_found"
    assert res_v2["error_code"] == E2005_IMAGE_NOT_MATCHED

    # Duplicate icons on screen MUST return ambiguous (E2010) and point=None
    screen_dup, _ = _make_screen_and_template([(20, 20, 1), (120, 80, 1)])
    res_dup = match_image_strict_single_frame(screen_dup, tpl, scales=(1.0,))
    assert res_dup["status"] == "ambiguous"
    assert res_dup["error_code"] == E2010_IMAGE_AMBIGUOUS
    assert res_dup["point"] is None


def test_two_frame_stability_and_assert_image_not_exists_semantics():
    screen_a, tpl = _make_screen_and_template([(60, 50, 1)])
    screen_moved, _ = _make_screen_and_template([(110, 50, 1)])
    screen_empty, _ = _make_screen_and_template([])

    # 1. Two stable frames -> matched & stable=True
    frames_stable = iter([screen_a, screen_a])

    async def cap_stable():
        return next(frames_stable, screen_a)

    res_stable = asyncio.run(
        locate_image_two_frame_stable(cap_stable, tpl, timeout_seconds=1.0, frame_interval_seconds=0.01, scales=(1.0,))
    )
    assert res_stable["status"] == "matched" and res_stable["stable"] is True

    # 2. Moving target across frames -> target_not_stable (E2012)
    flip = {"i": 0}

    async def cap_moving():
        flip["i"] += 1
        return screen_a if flip["i"] % 2 == 1 else screen_moved

    res_moving = asyncio.run(
        locate_image_two_frame_stable(cap_moving, tpl, timeout_seconds=0.25, frame_interval_seconds=0.05, scales=(1.0,))
    )
    assert res_moving["status"] == "target_not_stable"
    assert res_moving["error_code"] == E2012_IMAGE_UNSTABLE

    # 3. assert_image(not_exists) passes after two consecutive not_found frames
    async def cap_empty():
        return screen_empty

    passed_ne, diag_ne = asyncio.run(
        assert_image_strict(
            cap_empty, tpl, match_mode="not_exists", timeout_seconds=1.0, frame_interval_seconds=0.01, scales=(1.0,)
        )
    )
    assert passed_ne is True and diag_ne["frames_checked"] == 2

    # 4. assert_image(not_exists) NEVER passes on invalid template
    solid = _to_png_bytes(Image.new("RGB", (30, 30), (10, 10, 10)))
    passed_bad, diag_bad = asyncio.run(
        assert_image_strict(
            cap_empty, solid, match_mode="not_exists", timeout_seconds=1.0, frame_interval_seconds=0.01, scales=(1.0,)
        )
    )
    assert passed_bad is False and diag_bad["error_code"] == E2011_IMAGE_TEMPLATE_INVALID


def test_crop_lossless_png_template_computes_sha_and_anchor():
    screen, _ = _make_screen_and_template([(60, 50, 1)])
    cropped = crop_lossless_png_template(screen, x1=60, y1=50, x2=100, y2=82, click_point=(70, 66))
    assert cropped["quality_ok"] is True
    assert cropped["source_size"] == [200, 160]
    assert len(cropped["template_sha256"]) == 64
    assert cropped["tap_anchor"] == [0.25, 0.5]


def test_validate_visual_template_object_name_blocks_traversal_and_cross_project():
    import pytest
    from app.services.strict_image_matcher import validate_visual_template_object_name

    ok = validate_visual_template_object_name("visual-templates/projects/5/tpl_abc.png", 5)
    assert ok == "visual-templates/projects/5/tpl_abc.png"

    with pytest.raises(PermissionError):
        validate_visual_template_object_name("visual-templates/projects/9/tpl_abc.png", 5)

    for bad in ("../secret.png", "apks/projects/5/app.apk", "visual-templates/projects/5/a/b.png", "/etc/passwd"):
        with pytest.raises(ValueError):
            validate_visual_template_object_name(bad, 5)
