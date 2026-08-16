from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
MANUAL_ONLY_WORKFLOWS = (
    "test-integration.yml",
    "test-e2e.yml",
    "security.yml",
    "release-readiness.yml",
)


def _workflow_triggers(name: str) -> dict:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    # PyYAML 1.1 parses the GitHub Actions `on` key as True.
    return workflow.get("on", workflow.get(True, {}))


def test_extended_workflows_are_manual_only_without_nightly_schedule():
    for name in MANUAL_ONLY_WORKFLOWS:
        triggers = _workflow_triggers(name)

        assert "workflow_dispatch" in triggers
        assert "schedule" not in triggers


def test_push_and_pull_request_quality_gates_remain_enabled():
    for name in ("ci.yml", "security.yml"):
        triggers = _workflow_triggers(name)

        assert "push" in triggers
        assert "pull_request" in triggers
