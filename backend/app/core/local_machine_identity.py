"""Stable machine identity for Windows local desktop client."""

from __future__ import annotations

import json
import os
import socket
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings


def _identity_file_path(data_dir: Path | None = None) -> Path:
    base = data_dir if data_dir is not None else settings.LOCAL_DATA_PATH
    return base / ".machine_identity.json"


def get_machine_name() -> str:
    """Return a sanitized local hostname."""
    try:
        return socket.gethostname().strip()[:64] or "windows-desktop"
    except Exception:
        return "windows-desktop"


def get_machine_info(data_dir: Path | None = None) -> dict[str, Any]:
    """Retrieve or generate the persistent machine identity."""
    path = _identity_file_path(data_dir)
    if path.is_file():
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(content, dict) and content.get("machine_id"):
                return content
        except Exception:
            pass

    path.parent.mkdir(parents=True, exist_ok=True)
    generated_id = f"win-{uuid.uuid4().hex[:24]}"
    info = {
        "schema_version": 1,
        "machine_id": generated_id,
        "machine_name": get_machine_name(),
        "platform": sys.platform,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def get_machine_id(data_dir: Path | None = None) -> str:
    """Return the stable machine ID string."""
    return str(get_machine_info(data_dir)["machine_id"])
