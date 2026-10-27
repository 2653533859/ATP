"""Unit and contract verification for Windows Desktop Host (Option A)."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DESKTOP_SCRIPT = REPO_ROOT / "scripts" / "windows-desktop.py"
STANDALONE_PS1 = REPO_ROOT / "scripts" / "windows-standalone.ps1"


def test_windows_desktop_script_exists_and_parses():
    assert DESKTOP_SCRIPT.is_file()
    # Check syntax parsing
    res = subprocess.run([sys.executable, "-m", "py_compile", str(DESKTOP_SCRIPT)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_standalone_ps1_supports_desktop_action():
    content = STANDALONE_PS1.read_text(encoding="utf-8")
    assert "'desktop'" in content
    assert "$Action -eq 'desktop'" in content
    assert "windows-desktop.py" in content


def test_tauri_config_exists_and_valid():
    tauri_conf = REPO_ROOT / "frontend" / "src-tauri" / "tauri.conf.json"
    cargo_toml = REPO_ROOT / "frontend" / "src-tauri" / "Cargo.toml"
    assert tauri_conf.is_file()
    assert cargo_toml.is_file()
    assert "com.atp.desktop" in tauri_conf.read_text(encoding="utf-8")
    assert "tauri = " in cargo_toml.read_text(encoding="utf-8")
