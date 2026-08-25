"""Contract tests for the N8 system-governance acceptance command."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "n8-system-governance-acceptance.py"


def _module():
    spec = importlib.util.spec_from_file_location("n8_system_governance_acceptance", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_safe_url_removes_userinfo_query_and_fragment():
    module = _module()

    assert module._safe_url("https://user:secret@example.test/api?token=secret#fragment") == (
        "https://example.test/api"
    )


def test_safe_payload_accepts_masked_values_and_rejects_plaintext():
    module = _module()

    module._safe_payload({"api_key": "******", "endpoint": "******", "has_api_key": True})
    with pytest.raises(module.AcceptanceError):
        module._safe_payload({"password": "plain-secret"})


def test_select_revision_entry_uses_a_visible_resource():
    module = _module()

    assert module._select_revision_entry(
        {
            "sections": [
                {"key": "environment", "entries": [{"resource_id": 0}]},
                {"key": "notification", "entries": [{"resource_id": 8}]},
            ]
        }
    ) == ("notification", 8)
    assert module._select_revision_entry({"sections": [{"key": "environment", "entries": []}]}) is None


def test_main_requires_base_url_and_writes_redacted_report(tmp_path, monkeypatch):
    module = _module()
    report_path = tmp_path / "n8.json"
    monkeypatch.setenv("ATP_USERNAME", "admin")
    monkeypatch.setenv("ATP_PASSWORD", "password-value")

    assert module.main(["--report", str(report_path)]) == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["status"] == "failed"
    assert payload["checks"][0]["name"] == "configuration"
    assert "password-value" not in report_path.read_text(encoding="utf-8")


def test_acceptance_contract_is_wired_to_quality_gates_and_runbook():
    source = SCRIPT.read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "n8-system-governance-acceptance.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    pre_commit = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert "ATP_PASSWORD" in source
    assert "--password" not in source
    assert "--allow-mutations" in source
    assert "--rollback" in source
    assert "n8-system-governance-acceptance.py" in runbook
    assert "n8-system-governance-acceptance" in makefile
    assert "n8-system-governance-acceptance.py" in makefile
    assert "n8-system-governance-acceptance.py" in ci
    assert "n8-system-governance-acceptance.py" in pre_commit
