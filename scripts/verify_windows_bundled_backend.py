"""Smoke-test the frozen backend with fresh, isolated Windows-local data."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
EXE = Path(
    os.environ.get(
        "ATP_BUNDLED_BACKEND_EXE",
        str(ROOT / ".local-run" / "pyinstaller" / "dist" / "atp-backend" / "atp-backend.exe"),
    )
).resolve()
STATIC = EXE.parent.parent / "frontend" / "dist"


def _get(url: str) -> tuple[int, bytes]:
    with urlopen(url, timeout=3) as response:
        return response.status, response.read()


def main() -> None:
    if os.name != "nt" or not EXE.is_file():
        raise RuntimeError("Windows PyInstaller backend is not built")
    if not (STATIC / "index.html").is_file():
        shutil.copytree(ROOT / "frontend" / "dist", STATIC, dirs_exist_ok=True)
    private_root = Path(os.environ.get("ATP_BUNDLE_SMOKE_DIR", "D:/ATP_resources/private"))
    if not private_root.is_dir():
        raise RuntimeError("Private smoke data root is missing")
    data_dir = private_root / f"atp-bundled-smoke-{secrets.token_hex(8)}"
    data_dir.mkdir()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    password = secrets.token_urlsafe(32)
    env = os.environ.copy()
    env.update(
        ATP_LOCAL_MODE="true",
        APP_ENV="local",
        ATP_LOCAL_DATA_DIR=str(data_dir),
        APP_SECRET_KEY=secrets.token_urlsafe(48),
        FIRST_ADMIN_USERNAME="admin",
        FIRST_ADMIN_PASSWORD=password,
        APP_AUTO_CREATE_TABLES="false",
        APP_AUTH_COOKIE_SECURE="false",
        APP_AUTH_COOKIE_SAMESITE="lax",
        ENCRYPTION_KEY="",
        CLOUD_SYNC_ENABLED="false",
    )
    log_dir = ROOT / ".local-run" / "pyinstaller"
    with (log_dir / "verify.out.log").open("wb") as stdout, (log_dir / "verify.err.log").open("wb") as stderr:
        process = subprocess.Popen(
            [str(EXE), "--host", "127.0.0.1", "--port", str(port)],
            cwd=EXE.parent,
            env=env,
            stdout=stdout,
            stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 35
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"Bundled backend exited during startup: {process.returncode}")
                try:
                    status, _ = _get(base + "/health")
                    if status == 200:
                        break
                except (OSError, URLError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("Bundled backend health check timed out")
                time.sleep(0.5)

            status, payload = _get(base + "/api/v1/runtime")
            if status != 200 or json.loads(payload)["mode"] != "local":
                raise RuntimeError("Bundled backend did not start in local mode")
            status, page = _get(base + "/login")
            if status != 200 or b"<html" not in page.lower():
                raise RuntimeError("Bundled frontend is unavailable")
            request = Request(
                base + "/api/v1/auth/login",
                data=json.dumps({"username": "admin", "password": password}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=5) as response:
                if response.status != 200:
                    raise RuntimeError("Bundled administrator login failed")
            print("Bundled backend: health=200 runtime=local frontend=200 admin_login=200")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
