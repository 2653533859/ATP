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


def test_viewer_token_is_documented_as_password_free_role_matrix_credential():
    source = SCRIPT.read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "n8-system-governance-acceptance.md").read_text(encoding="utf-8")

    assert "ATP_VIEWER_TOKEN" in source
    assert "ATP_VIEWER_TOKEN" in runbook
    assert "viewer.login" in source


def test_role_matrix_uses_viewer_token_without_password_login(monkeypatch):
    module = _module()
    monkeypatch.setenv("ATP_TOKEN", "admin-token")
    monkeypatch.setenv("ATP_VIEWER_TOKEN", "viewer-token")
    monkeypatch.delenv("ATP_USERNAME", raising=False)
    monkeypatch.delenv("ATP_PASSWORD", raising=False)
    monkeypatch.delenv("ATP_VIEWER_USERNAME", raising=False)
    monkeypatch.delenv("ATP_VIEWER_PASSWORD", raising=False)

    class FakeClient:
        instances = []

        def __init__(self, base_url, timeout=20.0, token=None):
            self.token = token
            self.calls = []
            self.__class__.instances.append(self)

        def login(self, username, password):
            raise AssertionError("token-authenticated clients must not call login")

        def request(self, method, path, payload=None):
            self.calls.append((method, path, payload))
            if path == "/auth/me":
                return {"id": 1, "role": "admin" if self.token == "admin-token" else "viewer"}
            if self.token == "viewer-token" and path in {
                "/remote-toolbox/overview",
                "/configuration-center/overview",
            }:
                raise module.AcceptanceError(f"{method} {path} returned HTTP 403")
            if self.token == "viewer-token" and path.startswith("/audit-logs/export"):
                raise module.AcceptanceError(f"{method} {path} returned HTTP 403")
            if path == "/remote-toolbox/overview":
                return {"checks": [{"key": "postgres"}, {"key": "redis"}, {"key": "minio"}]}
            if path == "/configuration-center/overview":
                return {"sections": [{"key": key, "entries": []} for key in module.REQUIRED_SECTIONS]}
            raise AssertionError(f"unexpected request: {method} {path}")

        def request_raw(self, method, path):
            self.calls.append((method, path, None))
            return b"id,created_at\n"

    monkeypatch.setattr(module, "ApiClient", FakeClient)
    report = module.run_acceptance(
        module._parse_args(["--base-url", "https://example.test/api/v1", "--require-role-matrix"])
    )

    assert report["status"] == "partial"
    assert any(item["name"] == "role-matrix" and item["status"] == "passed" for item in report["checks"])
    assert [client.token for client in FakeClient.instances] == ["admin-token", "viewer-token"]


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
    assert "ATP_VIEWER_TOKEN" in source
    assert "--password" not in source
    assert "--allow-mutations" in source
    assert "--rollback" in source
    assert "n8-system-governance-acceptance.py" in runbook
    assert "n8-system-governance-acceptance" in makefile
    assert "n8-system-governance-acceptance.py" in makefile
    assert "n8-system-governance-acceptance.py" in ci
    assert "n8-system-governance-acceptance.py" in pre_commit
