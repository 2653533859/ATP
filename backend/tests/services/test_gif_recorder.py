"""Unit tests for the execution GIF recording service."""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import MagicMock

from PIL import Image

from app.services.gif_recorder import (
    compose_gif_from_frames,
    generate_and_upload_run_gif,
    generate_gif_from_run_step_records,
)


def _make_dummy_png_bytes(width: int = 1200, height: int = 800, color: tuple[int, int, int] = (100, 150, 200)) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_compose_gif_empty_returns_empty():
    assert compose_gif_from_frames([]) == b""
    assert compose_gif_from_frames([(b"", "label")]) == b""


def test_compose_gif_from_multiple_frames_success():
    frame1 = _make_dummy_png_bytes(1200, 800, (255, 0, 0))
    frame2 = _make_dummy_png_bytes(1200, 800, (0, 255, 0))

    gif_bytes = compose_gif_from_frames(
        [
            (frame1, "步骤 1: 打开首页 [passed]"),
            (frame2, "步骤 2: 点击搜索 [passed]"),
        ],
        duration_per_frame_ms=800,
        max_width=960,
    )

    assert len(gif_bytes) > 0
    assert gif_bytes.startswith(b"GIF89a")

    # Verify Pillow can open and inspect the generated GIF
    with Image.open(io.BytesIO(gif_bytes)) as gif:
        assert gif.format == "GIF"
        assert gif.is_animated is True
        assert gif.n_frames == 2
        # Downscaled to max_width = 960 (1200 -> 960, 800 -> 640)
        assert gif.size == (960, 640)


def test_generate_and_upload_run_gif(monkeypatch):
    mock_upload = MagicMock()
    mock_presign = MagicMock(return_value="https://minio.example.test/gifs/runs/42/recording.gif?token=xxx")
    monkeypatch.setattr("app.services.gif_recorder.upload_bytes", mock_upload)
    monkeypatch.setattr("app.services.gif_recorder.presigned_url", mock_presign)

    frame = _make_dummy_png_bytes(400, 300)
    url = generate_and_upload_run_gif(42, [(frame, "Step 1")])

    assert url == "https://minio.example.test/gifs/runs/42/recording.gif?token=xxx"
    mock_upload.assert_called_once()
    args, kwargs = mock_upload.call_args
    assert args[0] == "gifs/runs/42/recording.gif"
    assert args[2] == "image/gif"
    mock_presign.assert_called_once_with("gifs/runs/42/recording.gif")


def test_generate_gif_from_run_step_records(monkeypatch):
    frame1 = _make_dummy_png_bytes(600, 400)
    frame2 = _make_dummy_png_bytes(600, 400)

    def fake_read(obj_name: str) -> bytes:
        if "step_1" in obj_name:
            return frame1
        if "step_2" in obj_name:
            return frame2
        return b""

    mock_upload = MagicMock()
    monkeypatch.setattr("app.services.gif_recorder.read_bytes", fake_read)
    monkeypatch.setattr("app.services.gif_recorder.upload_bytes", mock_upload)
    monkeypatch.setattr(
        "app.services.gif_recorder.presigned_url",
        lambda obj: f"http://test/{obj}",
    )

    steps = [
        SimpleNamespace(step_index=2, name="输入关键字", status=SimpleNamespace(value="passed")),
        SimpleNamespace(step_index=1, name="打开搜索页", status=SimpleNamespace(value="passed")),
        SimpleNamespace(step_index=3, name="没有截图的步骤", status=SimpleNamespace(value="passed")),
    ]

    url = generate_gif_from_run_step_records(99, steps)
    assert url == "http://test/gifs/runs/99/recording.gif"
    mock_upload.assert_called_once()
