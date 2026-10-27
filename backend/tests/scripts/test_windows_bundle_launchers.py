"""The portable bundle must launch cleanly without copying local credentials."""

import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "package-windows-standalone-bundle.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe")

pytestmark = pytest.mark.skipif(sys.platform != "win32" or not POWERSHELL, reason="Windows PowerShell required")


def test_frozen_bundle_uses_readable_launcher_and_excludes_private_profile(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(SCRIPT, scripts / SCRIPT.name)
    (scripts / "windows-standalone.ps1").write_text("# stub\n", encoding="utf-8")
    frontend = root / "frontend" / "dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("<html></html>", encoding="utf-8")
    frozen = root / ".local-run" / "pyinstaller" / "dist" / "atp-backend"
    frozen.mkdir(parents=True)
    (frozen / "atp-backend.exe").write_bytes(b"test binary")
    profile = root / "config" / "startup-profiles"
    profile.mkdir(parents=True)
    (profile / "local-lite.env").write_text("APP_SECRET_KEY=must-not-package\n", encoding="utf-8")
    output = tmp_path / "bundle.zip"

    result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(scripts / SCRIPT.name),
            "-FrozenBackend",
            "-SkipFrozenBackendBuild",
            "-SkipFrontendBuild",
            "-OutputPath",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    with ZipFile(output) as archive:
        launcher = archive.read("start-atp.bat").decode("ascii")
        assert 'start "" "http://127.0.0.1:8001/"' in launcher
        assert "Startup failed" in launcher
        assert "config/startup-profiles/local-lite.env" not in archive.namelist()
        assert "backend/atp-backend.exe" in archive.namelist()
