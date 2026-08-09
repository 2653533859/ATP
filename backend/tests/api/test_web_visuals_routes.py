from __future__ import annotations

import asyncio
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.api.v1 import web_visuals


class _FakeUpload:
    filename = "baseline.png"
    content_type = "image/png"

    def __init__(self, content):
        self.content = content
        self.closed = False

    async def read(self, _size=-1):
        return self.content

    async def close(self):
        self.closed = True


class _DB:
    def __init__(self):
        self.commits = 0
        self.item = None

    async def get(self, model, key):
        if model.__name__ == "Project":
            return SimpleNamespace(id=key)
        return self.item

    def add(self, item):
        self.item = item

    async def commit(self):
        self.commits += 1
        if self.item is not None and self.item.id is None:
            self.item.id = 1

    async def refresh(self, _item):
        return None

    async def delete(self, _item):
        return None


def _png_bytes():
    buffer = BytesIO()
    Image.new("RGBA", (1, 1), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_upload_visual_baseline_records_dimensions_and_settings(monkeypatch):
    uploaded = {}
    monkeypatch.setattr(web_visuals, "assert_project_access", lambda *_args: _none())
    monkeypatch.setattr(web_visuals, "ensure_bucket", lambda: None)
    monkeypatch.setattr(
        web_visuals, "upload_bytes", lambda name, data, content_type: uploaded.update(name=name, data=data)
    )
    monkeypatch.setattr(web_visuals, "delete_file", lambda _name: None)
    db = _DB()
    result = asyncio.run(
        web_visuals.upload_web_visual_baseline(
            1,
            "home",
            None,
            0.02,
            5,
            "[]",
            _FakeUpload(_png_bytes()),
            db,
            SimpleNamespace(id=8),
        )
    )
    assert result.project_id == 1
    assert result.width == 1 and result.height == 1
    assert result.threshold == 0.02
    assert uploaded["name"].startswith("visual-baselines/projects/1/")


async def _none():
    return None
