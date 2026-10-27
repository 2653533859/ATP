"""Exercise standalone data location and restore without touching a real profile."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.config import Settings


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "windows-standalone.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe")

pytestmark = pytest.mark.skipif(sys.platform != "win32" or not POWERSHELL, reason="Windows PowerShell required")


def _isolated_script(root: Path) -> Path:
    script = root / "scripts" / "windows-standalone.ps1"
    script.parent.mkdir(parents=True)
    (root / "config" / "startup-profiles").mkdir(parents=True)
    shutil.copy2(SCRIPT, script)
    return script


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


@pytest.fixture(autouse=True)
def _isolate_test_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("APP_ENV", "APP_SECRET_KEY", "FIRST_ADMIN_PASSWORD", "ATP_LOCAL_MODE", "ATP_LOCAL_DATA_DIR"):
        monkeypatch.delenv(key, raising=False)


def test_new_profile_uses_requested_data_dir_and_preserves_it(tmp_path: Path) -> None:
    script = _isolated_script(tmp_path / "repo")
    data_dir = tmp_path / "data root with spaces"
    created = _run(script, "-Action", "init", "-DataDir", str(data_dir))
    assert created.returncode == 0, created.stderr
    profile = tmp_path / "repo" / "config" / "startup-profiles" / "local-lite.env"
    original = profile.read_text(encoding="utf-8")
    assert f"ATP_LOCAL_DATA_DIR={data_dir}" in original
    assert Settings(_env_file=profile).LOCAL_DATA_PATH == data_dir.resolve()
    assert data_dir.is_dir()

    rejected = _run(script, "-Action", "init", "-DataDir", str(tmp_path / "other data"))
    assert rejected.returncode != 0
    assert profile.read_text(encoding="utf-8") == original


def test_backup_and_restore_follow_profile_data_dir(tmp_path: Path) -> None:
    source_root = tmp_path / "source repo"
    source_script = _isolated_script(source_root)
    source_data = tmp_path / "source data"
    source_data.mkdir()
    (source_data / "result.txt").write_text("saved locally", encoding="utf-8")
    (source_root / "config" / "startup-profiles" / "local-lite.env").write_text(
        f"ATP_LOCAL_MODE=true\nATP_LOCAL_DATA_DIR={source_data}\nAPP_ENV=local\n"
        "APP_SECRET_KEY=test-only\nFIRST_ADMIN_PASSWORD=test-password\n",
        encoding="utf-8",
    )
    archive = tmp_path / "backup archive"
    backed_up = _run(source_script, "-Action", "backup", "-ArchiveDir", str(archive))
    assert backed_up.returncode == 0, backed_up.stderr
    assert (archive / "data" / "result.txt").read_text(encoding="utf-8") == "saved locally"

    target_root = tmp_path / "target repo"
    target_script = _isolated_script(target_root)
    target_data = tmp_path / "restored data"
    restored = _run(target_script, "-Action", "restore", "-ArchiveDir", str(archive), "-DataDir", str(target_data))
    assert restored.returncode == 0, restored.stderr
    assert (target_data / "result.txt").read_text(encoding="utf-8") == "saved locally"
    profile = (target_root / "config" / "startup-profiles" / "local-lite.env").read_text(encoding="utf-8")
    assert f"ATP_LOCAL_DATA_DIR={target_data}" in profile
    assert Settings(_env_file=target_root / "config" / "startup-profiles" / "local-lite.env").LOCAL_DATA_PATH == (
        target_data.resolve()
    )


def test_backup_rejects_destination_inside_configured_data_dir(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    script = _isolated_script(root)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (root / "config" / "startup-profiles" / "local-lite.env").write_text(
        f"ATP_LOCAL_DATA_DIR={data_dir}\n", encoding="utf-8"
    )
    archive = data_dir / "backup"
    result = _run(script, "-Action", "backup", "-ArchiveDir", str(archive))
    assert result.returncode != 0
    assert not archive.exists()
