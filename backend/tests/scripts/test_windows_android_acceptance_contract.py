from pathlib import Path


def script_text() -> str:
    return (
        (Path(__file__).resolve().parents[2] / "../scripts/windows-android-acceptance.ps1")
        .resolve()
        .read_text(encoding="utf-8")
    )


def test_windows_android_acceptance_has_safe_device_checks_and_report_contract():
    source = script_text()

    assert "Get-Command adb.exe" in source
    assert "adb devices" in source
    assert "unauthorized" in source
    assert "offline" in source
    assert "device_status" in source
    assert "get-state" in source
    assert "shell', 'echo', 'atp-android-acceptance" in source
    assert "pm', 'list', 'packages" in source
    assert "logcat', '-d', '-t', '20" in source
    assert "ConvertTo-Json -Depth 8" in source
    assert "required_failures" in source
    assert "password" not in source.lower()
    assert "access_token" not in source.lower()


def test_windows_android_acceptance_supports_target_package_and_report_overrides():
    source = script_text()

    assert "[string]$Target = ''" in source
    assert "[string]$AppPackage = ''" in source
    assert "[string]$ReportPath = ''" in source
    assert "pm', 'path', $AppPackage" in source
