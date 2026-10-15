"""Scrcpy 实时视频流与零延迟触控模块。"""

from app.device_stream.manager import scrcpy_manager
from app.device_stream.router import rest_router, ws_router

__all__ = ["scrcpy_manager", "rest_router", "ws_router"]
