"""The bundled backend must reject direct starts before loading server settings."""

import os
import runpy
import subprocess
import sys
from pathlib import Path


ENTRY = Path(__file__).resolve().parents[2] / "frozen_entry.py"


def test_frozen_windows_uses_user_playwright_cache(monkeypatch, tmp_path: Path) -> None:
    configure = runpy.run_path(str(ENTRY))["configure_playwright_browser_cache"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    configure()
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path / "ms-playwright")


def test_frozen_windows_respects_explicit_playwright_cache(monkeypatch, tmp_path: Path) -> None:
    configure = runpy.run_path(str(ENTRY))["configure_playwright_browser_cache"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "0")
    configure()
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == "0"


def test_source_runtime_does_not_override_playwright_cache(monkeypatch, tmp_path: Path) -> None:
    configure = runpy.run_path(str(ENTRY))["configure_playwright_browser_cache"]
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    configure()
    assert "PLAYWRIGHT_BROWSERS_PATH" not in os.environ


def test_direct_start_explains_launcher_requirement() -> None:
    env = os.environ.copy()
    env.pop("ATP_LOCAL_MODE", None)
    result = subprocess.run(
        [sys.executable, str(ENTRY)],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 2
    assert "ATP_LOCAL_MODE=true is required" in result.stderr
    assert "Traceback" not in result.stderr
