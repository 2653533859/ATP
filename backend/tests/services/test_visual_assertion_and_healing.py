"""Unit tests for P1.2 Multi-modal Visual Assertion and Element Visual Self-Healing.

Tests:
1. compute_image_similarity for identical, resized, and differing images
2. parse_image_template_bytes with raw bytes, base64, and data URLs
3. evaluate_visual_assertion pass and threshold failure
4. find_visual_coordinates template matching within screenshot
5. runtime_locator_healer visual coordinate and OCR healing fallback
6. web_lowcode_executor assert_visual_element step execution
7. android_lowcode_executor assert_visual_element step execution
"""

from __future__ import annotations

import asyncio
import base64
import io
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PIL import Image
from app.services.runtime_locator_healer import RuntimeLocatorHealer
from app.services.visual_assertion import (
    compute_image_similarity,
    evaluate_visual_assertion,
    find_visual_coordinates,
    parse_image_template_bytes,
)
from app.worker.executors.web_lowcode_executor import _execute_step
from app.worker.executors.android_lowcode_executor import _execute_step_sync


def _make_png_bytes(width: int = 100, height: int = 100, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    im = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_compute_image_similarity_identical_and_different():
    b1 = _make_png_bytes(100, 100, (255, 128, 0))
    b2 = _make_png_bytes(100, 100, (255, 128, 0))
    b3 = _make_png_bytes(50, 50, (255, 128, 0))  # different dimension
    b4 = _make_png_bytes(100, 100, (0, 0, 255))  # different color

    assert compute_image_similarity(b1, b2) == 1.0
    assert compute_image_similarity(b1, b3) == 1.0
    diff_sim = compute_image_similarity(b1, b4)
    assert diff_sim < 0.6


def test_parse_image_template_bytes():
    raw = _make_png_bytes(20, 20, (10, 20, 30))
    b64 = base64.b64encode(raw).decode("ascii")
    data_url = f"data:image/png;base64,{b64}"

    assert parse_image_template_bytes(raw) == raw
    assert parse_image_template_bytes(b64) == raw
    assert parse_image_template_bytes(data_url) == raw

    with pytest.raises(ValueError, match="无法解析视觉模板图片"):
        parse_image_template_bytes("invalid-base64-content!@#$%")


def test_evaluate_visual_assertion():
    target = _make_png_bytes(80, 80, (200, 200, 200))
    matching_template = _make_png_bytes(80, 80, (200, 200, 200))
    failing_template = _make_png_bytes(80, 80, (0, 0, 0))

    passed, score, err = evaluate_visual_assertion(target, matching_template, threshold=0.90)
    assert passed is True
    assert score == 1.0
    assert err is None

    passed, score, err = evaluate_visual_assertion(target, failing_template, threshold=0.90)
    assert passed is False
    assert score < 0.5
    assert "低于期望阈值" in (err or "")


def test_find_visual_coordinates():
    # Create large screen image (300x300) white background
    screen = Image.new("RGB", (300, 300), (255, 255, 255))
    # Place a 40x40 red square at (100, 100) -> center is (120, 120)
    square = Image.new("RGB", (40, 40), (255, 0, 0))
    screen.paste(square, (100, 100))

    screen_buf = io.BytesIO()
    screen.save(screen_buf, format="PNG")
    screen_bytes = screen_buf.getvalue()

    square_buf = io.BytesIO()
    square.save(square_buf, format="PNG")
    template_bytes = square_buf.getvalue()

    coords = find_visual_coordinates(screen_bytes, template_bytes, threshold=0.85)
    assert coords is not None
    cx, cy = coords
    # Check that center is around (120, 120) with grid tolerance
    assert abs(cx - 120) <= 15
    assert abs(cy - 120) <= 15


def test_runtime_locator_healer_visual_ocr_fallback():
    healer = RuntimeLocatorHealer(max_heals_per_run=2)

    class _FakeLocator:
        first = None

        def __init__(self):
            self.first = self

        async def bounding_box(self):
            return {"x": 200, "y": 150, "width": 80, "height": 30}

    class _FakePage:
        def __init__(self):
            self.clicked = None
            self.mouse = SimpleNamespace(click=self._click)

        async def _click(self, x, y):
            self.clicked = (x, y)

        def get_by_text(self, text):
            return _FakeLocator()

    page = _FakePage()
    params = {"selector": "button#dynamic_login_123", "ocr_text": "立即登录"}

    res = asyncio.run(
        healer.attempt_visual_healing(
            page,
            action="click",
            params=params,
            timeout_ms=1000,
            run_id=88,
            step_index=2,
            original_selector="button#dynamic_login_123",
        )
    )

    assert res is not None
    assert res["success"] is True
    healed = res["data"]["healed_info"]
    assert healed["healed"] is True
    assert healed["method"] == "ocr_text"
    assert healed["coordinates"]["x"] == 240.0
    assert healed["coordinates"]["y"] == 165.0
    assert page.clicked == (240.0, 165.0)


def test_web_lowcode_executor_assert_visual_element():
    img_bytes = _make_png_bytes(60, 60, (100, 150, 200))

    class _FakePage:
        def __init__(self):
            self.url = "http://example.test"

        async def screenshot(self, timeout=None):
            return img_bytes

        def locator(self, sel):
            class _Loc:
                async def wait_for(self, state, timeout):
                    pass

                async def screenshot(self, timeout):
                    return img_bytes

                async def inner_text(self):
                    return "欢迎登录系统"

            return _Loc()

    page = _FakePage()

    # 1. Matching visual template
    step_params = {
        "image_template": img_bytes,
        "threshold": 0.90,
    }
    res = asyncio.run(_execute_step(cast(Any, page), "assert_visual_element", step_params, 1000))
    assert res["success"] is True
    assert res["data"]["similarity"] == 1.0

    # 2. Matching expected text
    step_params_text = {
        "selector": ".header",
        "expected_text": "欢迎登录",
    }
    res_text = asyncio.run(_execute_step(cast(Any, page), "assert_visual_element", step_params_text, 1000))
    assert res_text["success"] is True

    # 3. Mismatched template
    diff_bytes = _make_png_bytes(60, 60, (0, 0, 0))
    step_params_fail = {
        "image_template": diff_bytes,
        "threshold": 0.90,
    }
    res_fail = asyncio.run(_execute_step(cast(Any, page), "assert_visual_element", step_params_fail, 1000))
    assert res_fail["success"] is False
    assert "低于期望阈值" in res_fail["error"]


def test_android_lowcode_executor_assert_visual_element(monkeypatch):
    img_bytes = _make_png_bytes(80, 80, (50, 100, 150))
    monkeypatch.setattr(
        "app.worker.executors.android_lowcode_executor._adb_screenshot",
        lambda _serial: img_bytes,
    )
    monkeypatch.setattr(
        "app.worker.executors.android_lowcode_executor._uiautomator_dump",
        lambda _serial, timeout: (True, "<node text='确定' />"),
    )

    # 1. Pass visual and text
    res = _execute_step_sync(
        "emulator-5554",
        "assert_visual_element",
        {"expected_text": "确定", "image_template": img_bytes, "threshold": 0.85},
    )
    assert res["success"] is True
    assert res["data"]["similarity"] == 1.0

    # 2. Text missing failure
    res_fail = _execute_step_sync(
        "emulator-5554",
        "assert_visual_element",
        {"expected_text": "不存在的文字"},
    )
    assert res_fail["success"] is False
    assert "未找到预期文本" in res_fail["error"]
