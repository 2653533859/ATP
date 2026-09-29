"""Private filesystem object storage used by the single-process Windows profile."""

from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import shutil
import time
from uuid import uuid4
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from app.core.config import settings


@dataclass(frozen=True)
class LocalObject:
    object_name: str
    size: int
    last_modified: datetime


def object_path(object_name: str) -> Path:
    name = PurePosixPath(object_name.replace("\\", "/"))
    if not object_name or name.is_absolute() or any(part in {"", ".", ".."} for part in name.parts):
        raise ValueError("invalid object name")
    root = (settings.LOCAL_DATA_PATH / "objects").resolve()
    path = root.joinpath(*name.parts).resolve()
    if not path.is_relative_to(root):
        raise ValueError("object name escapes local storage")
    return path


def ensure_store() -> None:
    (settings.LOCAL_DATA_PATH / "objects").mkdir(parents=True, exist_ok=True)
    (settings.LOCAL_DATA_PATH / "object-metadata").mkdir(parents=True, exist_ok=True)


def _metadata_path(object_name: str) -> Path:
    object_path(object_name)
    digest = hashlib.sha256(object_name.encode()).hexdigest()
    return settings.LOCAL_DATA_PATH / "object-metadata" / f"{digest}.json"


def _write_metadata(object_name: str, content_type: str) -> None:
    path = _metadata_path(object_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(json.dumps({"content_type": content_type}), encoding="utf-8")
    temporary.replace(path)


def content_type_for(object_name: str) -> str:
    path = _metadata_path(object_name)
    if path.exists():
        try:
            return str(json.loads(path.read_text(encoding="utf-8"))["content_type"])
        except (ValueError, KeyError, TypeError):
            pass
    return mimetypes.guess_type(object_name)[0] or "application/octet-stream"


def upload_bytes(object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    path = object_path(object_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)
    _write_metadata(object_name, content_type)
    return object_name


def upload_file(object_name: str, local_path: str | Path, content_type: str = "application/octet-stream") -> str:
    path = object_path(object_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    shutil.copyfile(local_path, temporary)
    temporary.replace(path)
    _write_metadata(object_name, content_type)
    return object_name


def download_file(object_name: str, local_path: str | Path) -> None:
    target = Path(local_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(object_path(object_name), target)


def read_bytes(object_name: str) -> bytes:
    return object_path(object_name).read_bytes()


def delete_file(object_name: str) -> None:
    object_path(object_name).unlink(missing_ok=True)
    _metadata_path(object_name).unlink(missing_ok=True)


def list_objects(prefix: str = "") -> list[LocalObject]:
    root = (settings.LOCAL_DATA_PATH / "objects").resolve()
    if not root.exists():
        return []
    result = []
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            name = path.relative_to(root).as_posix()
            if name.startswith(prefix):
                stat = path.stat()
                result.append(LocalObject(name, stat.st_size, datetime.fromtimestamp(stat.st_mtime, timezone.utc)))
    return result


def signed_url(object_name: str, expires_seconds: int) -> str:
    expires = int(time.time()) + max(1, expires_seconds)
    message = f"{expires}:{object_name}".encode()
    signature = hmac.new(settings.APP_SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()
    return f"/api/v1/local-files/{quote(object_name, safe='/')}?expires={expires}&signature={signature}"


def verify_signature(object_name: str, expires: int, signature: str) -> bool:
    if expires < time.time():
        return False
    expected = hmac.new(
        settings.APP_SECRET_KEY.encode(), f"{expires}:{object_name}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
