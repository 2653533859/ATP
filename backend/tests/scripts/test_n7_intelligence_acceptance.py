"""Contract tests for the N7 intelligence acceptance command."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "n7-intelligence-acceptance.py"


def _module():
    spec = importlib.util.spec_from_file_location("n7_intelligence_acceptance", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_safe_url_redacts_userinfo_query_and_fragment():
    module = _module()

    assert module._safe_url("https://user:secret@example.test/api?token=secret#fragment") == (
        "https://example.test/api"
    )
    assert "secret" not in module._safe_url("https://example.test/api?token=secret")


def test_api_client_rejects_secret_bearing_base_url():
    module = _module()

    with pytest.raises(ValueError):
        module.ApiClient("https://user:secret@example.test/api/v1")
    with pytest.raises(ValueError):
        module.ApiClient("https://example.test/api/v1?token=secret")


def test_viewer_client_uses_token_without_password_login(monkeypatch):
    module = _module()
    monkeypatch.setenv("ATP_VIEWER_TOKEN", "viewer-token")
    monkeypatch.delenv("ATP_VIEWER_USERNAME", raising=False)
    monkeypatch.delenv("ATP_VIEWER_PASSWORD", raising=False)

    class FakeClient:
        def __init__(self, base_url, timeout=20.0, token=None):
            self.token = token

        def login(self, username, password):
            raise AssertionError("token-authenticated viewers must not call login")

    monkeypatch.setattr(module, "ApiClient", FakeClient)
    client = module._build_viewer_client("https://example.test/api/v1", 20.0)

    assert client.token == "viewer-token"


def test_http_error_does_not_return_response_body(monkeypatch):
    module = _module()
    client = module.ApiClient("https://example.test/api/v1")

    class _Opener:
        def open(self, *_args, **_kwargs):
            raise module.urllib.error.HTTPError(
                "https://example.test/api/v1/hermes/query",
                403,
                "secret response body",
                {},
                None,
            )

    monkeypatch.setattr(client, "opener", _Opener())
    with pytest.raises(module.AcceptanceError) as exc:
        client.request("POST", "/hermes/query", {"query": "secret"})

    assert "HTTP 403" in str(exc.value)
    assert "secret" not in str(exc.value)


def test_main_requires_explicit_mutation_opt_in_and_writes_safe_report(tmp_path, monkeypatch):
    module = _module()
    report_path = tmp_path / "n7.json"
    monkeypatch.setenv("ATP_USERNAME", "admin")
    monkeypatch.setenv("ATP_PASSWORD", "password-value")

    args = module._parse_args(["--base-url", "https://example.test/api/v1", "--report", str(report_path)])
    report = module.run_acceptance(args)
    module._write_report(report_path, report)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["status"] == "failed"
    assert payload["checks"][0]["name"] == "mutation-safety"
    assert "password-value" not in report_path.read_text(encoding="utf-8")


def test_source_contract_requires_all_three_project_sources():
    module = _module()

    with pytest.raises(module.AcceptanceError):
        module._assert_source_types(
            {"mode": "project_retrieval", "sources": [{"source_type": "knowledge"}]},
            "marker",
            1,
        )


def test_source_contract_requires_marker_paths_and_references():
    module = _module()
    sources = [
        {
            "source_type": "knowledge",
            "title": "marker handbook",
            "excerpt": "",
            "source_ref": "SOP-marker",
            "path": "/knowledge?project_id=1&knowledge_id=2",
        },
        {
            "source_type": "requirement",
            "title": "marker requirement",
            "excerpt": "",
            "source_ref": "REQ-marker",
            "path": "/requirements?project_id=1&requirement_id=3",
        },
        {
            "source_type": "case",
            "title": "marker case",
            "excerpt": "",
            "source_ref": "CASE-marker",
            "path": "/cases?project_id=1&case_id=4",
        },
    ]

    module._assert_source_types({"mode": "project_retrieval", "sources": sources}, "marker", 1)
    sources[2]["path"] = "/cases?project_id=2&case_id=4"
    with pytest.raises(module.AcceptanceError):
        module._assert_source_types({"mode": "project_retrieval", "sources": sources}, "marker", 1)


def test_empty_project_modules_are_filled_with_a_temporary_module():
    module = _module()

    class _Client:
        def __init__(self):
            self.calls = []

        def request(self, method, path, payload=None):
            self.calls.append((method, path, payload))
            return [] if method == "GET" else {"id": 17}

    client = _Client()
    assert module._ensure_module(client, 9) == (17, True)
    assert client.calls == [
        ("GET", "/projects/9/modules", None),
        ("POST", "/modules", {"project_id": 9, "name": "N7 acceptance module", "module_code": "N7_ACCEPTANCE"}),
    ]


def test_ai_preflight_uses_saved_config_without_sending_or_recording_secrets():
    module = _module()
    calls = []

    class _Client:
        def request(self, method, path, payload=None):
            calls.append((method, path, payload))
            if path == "/ai/llm-configs":
                return [
                    {
                        "id": 7,
                        "provider": "openai_compatible",
                        "model_name": "vision-reasoner",
                        "enabled": True,
                        "supports_vision": True,
                        "default_params": {"reasoning_effort": "medium"},
                    }
                ]
            if path == "/ai/llm-configs/models":
                return {
                    "models": [
                        {
                            "id": "vision-reasoner",
                            "supports_vision": True,
                            "supports_reasoning": True,
                        }
                    ]
                }
            if path == "/ai/llm-configs/test-connection":
                return {"response_received": True, "model_name": "vision-reasoner"}
            raise AssertionError(path)

    result = module._load_and_check_ai_config(
        _Client(),
        types.SimpleNamespace(llm_config_id=7, require_vision=True, require_thinking=True),
    )

    assert result == {
        "id": 7,
        "provider": "openai_compatible",
        "model_name": "vision-reasoner",
        "supports_vision": True,
        "thinking_parameter_keys": ["reasoning_effort"],
        "discovered_model_count": 1,
    }
    assert calls == [
        ("GET", "/ai/llm-configs", None),
        ("POST", "/ai/llm-configs/models", {"config_id": 7, "provider": "openai_compatible"}),
        ("POST", "/ai/llm-configs/test-connection", {"config_id": 7}),
    ]


def test_capability_flags_require_ai_generation_gate():
    module = _module()

    with pytest.raises(SystemExit):
        module._parse_args(["--base-url", "https://example.test", "--require-vision"])


def test_acceptance_script_and_runbook_keep_credentials_out_of_cli_and_evidence():
    source = SCRIPT.read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "n7-intelligence-acceptance.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "ATP_PASSWORD" in source
    assert "ATP_VIEWER_TOKEN" in source
    assert "--password" not in source
    assert "--allow-mutations" in source
    assert "--llm-config-id" in source
    assert "ATP_LLM_CONFIG_ID" in source
    assert "finally:" in source
    assert "n7-intelligence-acceptance" in makefile
    assert "n7-intelligence-acceptance.py" in runbook
    assert "credentials were not recorded" in source


def test_viewer_token_is_documented_as_password_free_role_matrix_credential():
    source = SCRIPT.read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "n7-intelligence-acceptance.md").read_text(encoding="utf-8")

    assert "ATP_VIEWER_TOKEN" in source
    assert "ATP_VIEWER_TOKEN" in runbook
    assert "_build_viewer_client" in source
