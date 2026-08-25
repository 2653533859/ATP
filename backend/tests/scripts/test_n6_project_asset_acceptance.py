"""Contract tests for the N6 project asset and role acceptance command."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "n6-project-asset-acceptance.py"


def _module():
    spec = importlib.util.spec_from_file_location("n6_project_asset_acceptance", SCRIPT)
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
    assert "secret" not in module._safe_url("https://example.test/api?token=secret")


def test_target_url_rejects_credentials_query_and_non_http_schemes():
    module = _module()

    with pytest.raises(ValueError):
        module._safe_target_url("https://user:secret@example.test/health")
    with pytest.raises(ValueError):
        module._safe_target_url("https://example.test/health?token=secret")
    with pytest.raises(ValueError):
        module._safe_target_url("file:///tmp/health")


def test_api_client_rejects_secret_bearing_base_url():
    module = _module()

    with pytest.raises(ValueError):
        module.ApiClient("https://user:secret@example.test/api/v1")
    with pytest.raises(ValueError):
        module.ApiClient("https://example.test/api/v1?token=secret")


def test_http_error_does_not_return_response_body(monkeypatch):
    module = _module()
    client = module.ApiClient("https://example.test/api/v1")

    class _Opener:
        def open(self, *_args, **_kwargs):
            raise module.urllib.error.HTTPError(
                "https://example.test/api/v1/auth/me?token=secret",
                403,
                "forbidden",
                {},
                None,
            )

    monkeypatch.setattr(client, "opener", _Opener())
    with pytest.raises(module.AcceptanceError) as exc:
        client.request("GET", "/auth/me")

    assert "HTTP 403" in str(exc.value)
    assert "secret" not in str(exc.value)
    assert "forbidden" not in str(exc.value)


def test_main_requires_explicit_mutation_opt_in_and_writes_safe_report(tmp_path, monkeypatch):
    module = _module()
    report_path = tmp_path / "n6.json"
    monkeypatch.setenv("ATP_USERNAME", "admin")
    monkeypatch.setenv("ATP_PASSWORD", "password-value")

    args = module._parse_args(["--base-url", "https://example.test/api/v1", "--report", str(report_path)])
    report = module.run_acceptance(args)
    module._write_report(report_path, report)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["status"] == "failed"
    assert payload["checks"][0]["name"] == "mutation-safety"
    assert "password-value" not in report_path.read_text(encoding="utf-8")


def test_acceptance_script_and_runbook_keep_credentials_out_of_cli_and_evidence():
    source = SCRIPT.read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "n6-project-asset-acceptance.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "ATP_PASSWORD" in source
    assert "--password" not in source
    assert "--allow-mutations" in source
    assert "finally:" in source
    assert "n6-project-asset-acceptance" in makefile
    assert "n6-project-asset-acceptance.py" in runbook
    assert "credentials were not recorded" in source
