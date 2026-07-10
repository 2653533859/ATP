def test_external_readiness_spec_defines_slo_history_contract(repo_file):
    content = repo_file("docs/q12-external-readiness-evidence.md")

    for marker in (
        "docs/slo-guide.md",
        "7 consecutive days",
        "day-14",
        "API availability",
        "API P95 latency",
        "Run success rate",
        "Absolute start/end dates",
        "alert/release-gate decision",
        "docs/slo-history-<start>-<end>.md",
    ):
        assert marker in content


def test_external_readiness_spec_defines_device_rehearsal_contract(repo_file):
    content = repo_file("docs/q12-external-readiness-evidence.md")

    for marker in (
        "docs/android-worker-connectivity-rehearsal.md",
        "adb tcpip 5555",
        "scripts/android-network-doctor.sh",
        "ADB_SKIP_SERVER_RESTART=true",
        "dumpsys meminfo",
        "metric sample count > 0",
        "CSV and JSON report exports",
        "docs/android-device-rehearsal-<date>.md",
    ):
        assert marker in content


def test_external_readiness_spec_matches_platform_surfaces(repo_file):
    """口径引用的平台能力必须真实存在，防止演练单先于实现漂移。"""
    doctor = repo_file("scripts/android-network-doctor.sh")
    assert "ADB_SKIP_SERVER_RESTART" in doctor
    assert "ADB_SKIP_CONNECT" in doctor

    slo_guide = repo_file("docs/slo-guide.md")
    for marker in ("API availability", "API P95", "Run success rate", "14 consecutive days"):
        assert marker in slo_guide

    compose = repo_file("docker-compose.yml")
    assert "host.docker.internal:host-gateway" in compose
