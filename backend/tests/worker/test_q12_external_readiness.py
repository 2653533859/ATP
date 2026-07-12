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
        "docs/templates/slo-history-template.md",
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
        "docs/templates/android-device-rehearsal-template.md",
    ):
        assert marker in content


def test_external_readiness_templates_are_publishable(repo_file):
    slo_template = repo_file("docs/templates/slo-history-template.md")
    for marker in (
        "API Availability",
        "API P95 Latency",
        "Run Success Rate",
        "Scrape Health",
        "Final Calibration Decision",
        "docs/fixtures/<file>",
    ):
        assert marker in slo_template

    android_template = repo_file("docs/templates/android-device-rehearsal-template.md")
    for marker in (
        "Network Doctor",
        "ADB_SERVER_SOCKET",
        "dumpsys meminfo",
        "End-To-End Special Task",
        "CSV report",
        "JSON report",
    ):
        assert marker in android_template

    acceptance_template = repo_file("docs/templates/q12-acceptance-summary-template.md")
    for marker in (
        "docs/slo-history-<start>-<end>.md",
        "docs/android-device-rehearsal-<date>.md",
        "Alert enablement",
        "Release-blocking gate",
        "Acceptance Statement",
    ):
        assert marker in acceptance_template

    spec = repo_file("docs/q12-external-readiness-evidence.md")
    assert "make scaffold-q12-evidence" in spec
    assert "make validate-q12-evidence" in spec
    assert "scripts/scaffold-q12-evidence.py" in repo_file("docs/q14-completion-audit.md")
    assert "scripts/validate-q12-evidence.py" in spec

    makefile = repo_file("Makefile")
    assert "scaffold-q12-evidence:" in makefile
    assert "validate-q12-evidence:" in makefile
    assert "START=YYYY-MM-DD END=YYYY-MM-DD ANDROID_DATE=YYYY-MM-DD [FORCE=1]" in makefile
    assert "$(if $(FORCE),--force,)" in makefile
    assert "SLO=docs/slo-history-YYYY-MM-DD-YYYY-MM-DD.md" in makefile
    assert "--android" in makefile
    assert "--acceptance" in makefile
    assert "scripts/scaffold-q12-evidence.py scripts/validate-q12-evidence.py" in makefile


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


def test_q14_completion_audit_records_verifiable_status(repo_file):
    audit = repo_file("docs/q14-completion-audit.md")

    for marker in (
        "Q14 Completion Audit",
        "local Q14 work is complete",
        "full Q14 completion is pending Q14-00 external evidence",
        "Q14-00",
        "Q14-01",
        "Q14-02",
        "Q14-03",
        "Q14-04",
        "Q14-05",
        "Q14-06",
        "make scaffold-q12-evidence",
        "make validate-q12-evidence",
        "docs/slo-history-<start>-<end>.md",
        "docs/android-device-rehearsal-<date>.md",
        "docs/q12-acceptance-summary.md",
        "1317 passed",
        "82.20%",
        "21.48%",
    ):
        assert marker in audit

    task = repo_file("Task.md")
    roadmap = repo_file("docs/optimization-roadmap-2026-q14.md")
    assert "docs/q14-completion-audit.md" in task
    assert "docs/q14-completion-audit.md" in roadmap
