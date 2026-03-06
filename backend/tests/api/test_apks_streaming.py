import asyncio
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.core.minio_client"] = types.SimpleNamespace(
    ensure_bucket=lambda: None,
    upload_bytes=lambda *args, **kwargs: None,
    upload_file=lambda *args, **kwargs: None,
    presigned_url=lambda *args, **kwargs: "",
    delete_file=lambda *args, **kwargs: None,
)
sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_engineer=lambda: None,
)

from app.api.v1 import apks


class FakeUploadFile:
    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)

    async def read(self, _: int = -1) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def test_save_upload_to_tempfile_streams_chunks():
    fake = FakeUploadFile([b"a" * 3, b"b" * 2])

    temp_path, size = asyncio.run(apks._save_upload_to_tempfile(fake, max_size=10, chunk_size=3))
    temp_file = Path(temp_path)
    try:
        assert size == 5
        assert temp_file.exists()
        assert temp_file.read_bytes() == b"aaabb"
    finally:
        if temp_file.exists():
            temp_file.unlink()


def test_save_upload_to_tempfile_rejects_oversize():
    fake = FakeUploadFile([b"a" * 4, b"b" * 4, b"c" * 4])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(apks._save_upload_to_tempfile(fake, max_size=10, chunk_size=4))
    assert exc.value.status_code == 413
