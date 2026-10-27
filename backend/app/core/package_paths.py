"""Locate resources in source checkouts and PyInstaller one-folder builds."""

from pathlib import Path
import sys


def installation_root() -> Path:
    if getattr(sys, "frozen", False):
        # The packaged backend lives at <install>/backend/atp-backend.exe.
        return Path(sys.executable).resolve().parent.parent
    return Path(__file__).resolve().parents[3]


def bundled_resource(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / relative_path  # type: ignore[attr-defined]
    return installation_root() / relative_path
