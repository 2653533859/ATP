"""API multipart 请求文件上传路由测试。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.v1 import api_request_files as module


class _FakeDB:
    pass


class _FakeUpload:
    def __init__(self, content: bytes, filename: str = "hello.txt", content_type: str = "text/plain"):
        self.content = content
        self.filename = filename
        self.content_type = content_type
        self.closed = False
        self.offset = 0

    async def read(self, size: int = -1):
        if self.offset >= len(self.content):
            return b""
        end = len(self.content) if size < 0 else min(self.offset + size, len(self.content))
        chunk = self.content[self.offset : end]
        self.offset = end
        return chunk

    async def close(self):
        self.closed = True


def _run(coro):
    return asyncio.run(coro)


def test_object_name_sanitizes_filename_and_keeps_project_scope():
    value = module._object_name(7, "../private report?.csv")
    assert value.startswith("api-files/projects/7/")
    assert ".." not in Path(value).name
    assert "?" not in value


def test_upload_stores_file_and_returns_reference(monkeypatch):
    uploaded = {}
    monkeypatch.setattr(module, "assert_project_access", lambda *_args: _async_none())
    monkeypatch.setattr(module, "ensure_bucket", lambda: None)

    def fake_upload(object_name, local_path, content_type):
        uploaded["object_name"] = object_name
        uploaded["content"] = Path(local_path).read_bytes()
        uploaded["content_type"] = content_type

    monkeypatch.setattr(module, "upload_file", fake_upload)
    file = _FakeUpload(b"hello", filename="hello.txt", content_type="text/plain")

    result = _run(module.upload_api_request_file(7, file, _FakeDB(), object()))

    assert result["object_name"].startswith("api-files/projects/7/")
    assert result["filename"] == "hello.txt"
    assert result["size"] == 5
    assert uploaded["content"] == b"hello"
    assert uploaded["content_type"] == "text/plain"
    assert file.closed is True


def test_upload_rejects_files_over_20mb(monkeypatch):
    monkeypatch.setattr(module, "assert_project_access", lambda *_args: _async_none())
    file = _FakeUpload(b"x" * (module._MAX_REQUEST_FILE_SIZE + 1))

    with pytest.raises(HTTPException) as excinfo:
        _run(module.upload_api_request_file(7, file, _FakeDB(), object()))

    assert excinfo.value.status_code == 413
    assert file.closed is True


async def _async_none():
    return None
