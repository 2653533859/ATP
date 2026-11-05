"""Exercise standalone data location and restore without touching a real profile."""

import ctypes
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.config import Settings


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "windows-standalone.ps1"
REPO_ROOT = SCRIPT.parents[1]
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe")

pytestmark = pytest.mark.skipif(sys.platform != "win32" or not POWERSHELL, reason="Windows PowerShell required")

# windows-standalone.ps1 的 Assert-RequestedDataDir 要求 -DataDir 位于剩余 20GB
# 以上的本地固定盘；pytest 的 tmp_path 可能落在空间不足的系统盘上。
DATA_DIR_MIN_FREE_BYTES = 20 * 1024**3


def _fixed_drive_free_bytes(drive: str) -> int:
    """返回本地固定盘（DriveType=3）剩余空间字节数；不存在或非固定盘返回 -1。"""
    try:
        if not Path(drive).exists() or ctypes.windll.kernel32.GetDriveTypeW(drive) != 3:
            return -1
        return shutil.disk_usage(drive).free
    except OSError:
        return -1


def _create_spacey_tmp_root() -> Path:
    """在剩余 >=20GB 的本地固定盘上创建临时根目录，供需要 -DataDir 的用例使用。

    优先使用仓库所在盘的 .local-run（已被 .gitignore 覆盖），否则挑选剩余空间
    最大的固定盘根目录；没有任何合格盘时跳过用例。
    """
    if _fixed_drive_free_bytes(SCRIPT.drive + "\\") >= DATA_DIR_MIN_FREE_BYTES:
        parent = REPO_ROOT / ".local-run"
        parent.mkdir(exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="data-dir-tests-", dir=parent))
    candidates: list[tuple[int, str]] = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        free = _fixed_drive_free_bytes(f"{letter}:\\")
        if free >= DATA_DIR_MIN_FREE_BYTES:
            candidates.append((free, f"{letter}:\\"))
    if not candidates:
        pytest.skip("no fixed drive with at least 20 GB free for -DataDir")
    for _free, drive in sorted(candidates, reverse=True):
        try:
            return Path(tempfile.mkdtemp(prefix="atp-data-dir-tests-", dir=drive))
        except OSError:
            continue
    pytest.skip("cannot create temp dir on any qualifying drive")


@pytest.fixture
def spacey_tmp_path() -> Iterator[Path]:
    """替代 tmp_path：位于剩余 >=20GB 固定盘上的临时目录，用例结束自动清理。"""
    root = _create_spacey_tmp_root()
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


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


def test_new_profile_uses_requested_data_dir_and_preserves_it(spacey_tmp_path: Path) -> None:
    script = _isolated_script(spacey_tmp_path / "repo")
    data_dir = spacey_tmp_path / "data root with spaces"
    created = _run(script, "-Action", "init", "-DataDir", str(data_dir))
    assert created.returncode == 0, created.stderr
    profile = spacey_tmp_path / "repo" / "config" / "startup-profiles" / "local-lite.env"
    original = profile.read_text(encoding="utf-8")
    assert f"ATP_LOCAL_DATA_DIR={data_dir}" in original
    assert Settings(_env_file=profile).LOCAL_DATA_PATH == data_dir.resolve()
    assert data_dir.is_dir()

    rejected = _run(script, "-Action", "init", "-DataDir", str(spacey_tmp_path / "other data"))
    assert rejected.returncode != 0
    assert profile.read_text(encoding="utf-8") == original


def test_desktop_state_root_keeps_profile_outside_install_directory(spacey_tmp_path: Path) -> None:
    install = spacey_tmp_path / "installed app"
    script = _isolated_script(install)
    state_root = spacey_tmp_path / "user state"
    data_dir = spacey_tmp_path / "desktop data"
    result = _run(script, "-Action", "init", "-StateRoot", str(state_root), "-DataDir", str(data_dir))
    assert result.returncode == 0, result.stderr
    profile = state_root / "config" / "startup-profiles" / "local-lite.env"
    assert profile.exists()
    assert Settings(_env_file=profile).LOCAL_DATA_PATH == data_dir.resolve()
    assert not (install / "config" / "startup-profiles" / "local-lite.env").exists()


def test_backup_and_restore_follow_profile_data_dir(spacey_tmp_path: Path) -> None:
    source_root = spacey_tmp_path / "source repo"
    source_script = _isolated_script(source_root)
    source_data = spacey_tmp_path / "source data"
    source_data.mkdir()
    (source_data / "result.txt").write_text("saved locally", encoding="utf-8")
    (source_root / "config" / "startup-profiles" / "local-lite.env").write_text(
        f"ATP_LOCAL_MODE=true\nATP_LOCAL_DATA_DIR={source_data}\nAPP_ENV=local\n"
        "APP_SECRET_KEY=test-only\nFIRST_ADMIN_PASSWORD=test-password\n",
        encoding="utf-8",
    )
    archive = spacey_tmp_path / "backup archive"
    backed_up = _run(source_script, "-Action", "backup", "-ArchiveDir", str(archive))
    assert backed_up.returncode == 0, backed_up.stderr
    assert (archive / "data" / "result.txt").read_text(encoding="utf-8") == "saved locally"

    target_root = spacey_tmp_path / "target repo"
    target_script = _isolated_script(target_root)
    target_data = spacey_tmp_path / "restored data"
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


def _has_qualifying_non_c_drive() -> bool:
    """是否存在会被 Select-NewAtpDataDir 优先选中的非 C 固定盘。"""
    return any(
        _fixed_drive_free_bytes(f"{letter}:{chr(92)}") >= DATA_DIR_MIN_FREE_BYTES
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if letter != "C"
    )


@pytest.mark.skipif(
    _has_qualifying_non_c_drive(),
    reason="machine has a spare non-C fixed drive; the state-root fallback is not exercised",
)
def test_desktop_init_without_data_dir_uses_state_root(spacey_tmp_path: Path) -> None:
    """桌面端不传 -DataDir：没有可选的非 C 盘时必须回退到状态根，而不是直接失败。"""
    install = spacey_tmp_path / "installed app"
    script = _isolated_script(install)
    state_root = spacey_tmp_path / "user state"
    result = _run(script, "-Action", "init", "-StateRoot", str(state_root))
    assert result.returncode == 0, result.stderr
    profile = state_root / "config" / "startup-profiles" / "local-lite.env"
    assert Settings(_env_file=profile).LOCAL_DATA_PATH == (state_root / "ATP_resources").resolve()


def test_relative_data_dir_resolves_under_state_root(spacey_tmp_path: Path) -> None:
    """profile 里的相对 ATP_LOCAL_DATA_DIR 必须相对 -StateRoot 解析，而不是安装目录。"""
    install = spacey_tmp_path / "installed app"
    script = _isolated_script(install)
    state_root = spacey_tmp_path / "user state"
    profile = state_root / "config" / "startup-profiles" / "local-lite.env"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        chr(10).join(
            [
                "ATP_LOCAL_MODE=true",
                "ATP_LOCAL_DATA_DIR=relative-data",
                "APP_ENV=local",
                "APP_SECRET_KEY=test-only",
                "FIRST_ADMIN_PASSWORD=test-password",
                "",
            ]
        ),
        encoding="utf-8",
    )
    data_dir = state_root / "relative-data"
    data_dir.mkdir()
    result = _run(script, "-Action", "init", "-StateRoot", str(state_root), "-DataDir", str(data_dir))
    assert result.returncode == 0, result.stderr
    assert "ATP_LOCAL_DATA_DIR=relative-data" in profile.read_text(encoding="utf-8")
