from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
MANUAL_ONLY_WORKFLOWS = (
    "test-integration.yml",
    "test-e2e.yml",
    "release-readiness.yml",
)
WEEKLY_WORKFLOWS = ("ci.yml", "security.yml")


def _workflow_triggers(name: str) -> dict:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    # PyYAML 1.1 parses the GitHub Actions `on` key as True.
    return workflow.get("on", workflow.get(True, {}))


def test_extended_workflows_are_manual_only_without_nightly_schedule():
    for name in MANUAL_ONLY_WORKFLOWS:
        triggers = _workflow_triggers(name)

        assert "workflow_dispatch" in triggers
        assert "schedule" not in triggers


def test_quality_workflows_run_weekly_and_remain_manually_dispatchable():
    for name in WEEKLY_WORKFLOWS:
        triggers = _workflow_triggers(name)

        assert "push" not in triggers
        assert "pull_request" not in triggers
        assert "workflow_dispatch" in triggers
        assert triggers["schedule"] == [{"cron": "0 2 * * 0"}]
