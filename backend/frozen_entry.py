"""Loopback-only entrypoint for a bundled Windows local backend."""

from __future__ import annotations

import argparse
import multiprocessing
import os
import sys

import uvicorn


def main() -> None:
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description="ATP Windows local backend")
    parser.add_argument("--host", choices=["127.0.0.1", "localhost", "::1"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    if os.environ.get("ATP_LOCAL_MODE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        if getattr(sys, "frozen", False) and sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
                None,
                "这是 ATP 后台程序。请先完整解压 Windows 便携 ZIP，再双击解压目录根部的 start-atp.bat。",
                "ATP 启动方式",
                0x40,
            )
        parser.error("ATP_LOCAL_MODE=true is required for the bundled backend")
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")

    from app.core.config import settings
    from app.main import app

    if not settings.ATP_LOCAL_MODE:
        parser.error("ATP_LOCAL_MODE=true is required for the bundled backend")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
