"""Static contracts for the Windows local development helpers."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_windows_local_script_exposes_doctor_and_windows_safe_repo_resolution():
    script = _read("scripts/windows-local.ps1")

    assert "'doctor'" in script
    assert "Get-DotEnvValues" in script
    assert "Test-TcpEndpoint" in script
    assert "PERFORMANCE_EXECUTORS" in script
    assert "PlaywrightPackage" in script
    assert "F:\\csh\\MyProjectAutoTest" not in script


def test_android_network_doctor_has_a_powershell_entrypoint_and_safe_modes():
    script = _read("scripts/android-network-doctor.ps1")

    assert "[switch]$SkipServerRestart" in script
    assert "[switch]$SkipConnect" in script
    assert "adb.exe" in script
    assert "adb devices" in script
    assert "shell echo" in script


def test_windows_local_smoke_covers_live_and_browser_paths_without_secrets():
    script = _read("scripts/windows-local-smoke.ps1")

    assert "[switch]$StartServices" in script
    assert "[switch]$SkipLiveLogin" in script
    assert "[switch]$SkipFileTransfer" in script
    assert "[switch]$SkipReports" in script
    assert "[switch]$StopServicesAfter" in script
    assert "IsPathRooted" in script
    assert "local-dev.cmd" in script
    assert "/health" in script
    assert "/api/v1/auth/login" in script
    assert "/auth/me" in script
    assert "'/projects'" in script
    assert "/web-files" in script
    assert "/storage/cleanup-execute" in script
    assert "export/html" in script
    assert "/junit" in script
    assert "No historical run is available" in script
    assert "if ([string]::IsNullOrWhiteSpace($objectName))" in script
    assert "'run', 'e2e'" in script
    assert "e2e:browser-matrix" in script
    assert "access token returned; value hidden" in script
    assert "ConvertTo-Json" in script
    assert "F:\\csh\\MyProjectAutoTest" not in script
