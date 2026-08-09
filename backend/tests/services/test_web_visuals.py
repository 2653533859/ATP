from io import BytesIO

import pytest
from PIL import Image

from app.services.web_visuals import VisualCompareError, compare_png_bytes


def _png(color, *, size=(4, 4)) -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_identical_images_match_with_empty_diff():
    result = compare_png_bytes(_png("white"), _png("white"))
    assert result["match"] is True
    assert result["changed_pixels"] == 0
    assert result["diff_ratio"] == 0


def test_pixel_difference_and_threshold_are_reported():
    result = compare_png_bytes(_png("white"), _png("black"), threshold=0.2, pixel_threshold=1)
    assert result["match"] is False
    assert result["changed_pixels"] == 16
    assert result["diff_ratio"] == 1
    assert result["diff_png"]


def test_ignored_region_can_make_difference_match():
    result = compare_png_bytes(
        _png("white"),
        _png("black"),
        threshold=0,
        pixel_threshold=1,
        ignore_regions=[{"x": 0, "y": 0, "width": 4, "height": 4}],
    )
    assert result["match"] is True
    assert result["changed_pixels"] == 0


def test_size_mismatch_is_explicit_and_invalid_threshold_is_rejected():
    result = compare_png_bytes(_png("white"), _png("white", size=(2, 2)))
    assert result["match"] is False
    assert result["reason"] == "image_size_mismatch"
    with pytest.raises(VisualCompareError):
        compare_png_bytes(_png("white"), _png("white"), threshold=2)
