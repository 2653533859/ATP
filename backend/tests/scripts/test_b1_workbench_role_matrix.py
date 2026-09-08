"""Contract tests for the B1 workbench role-matrix acceptance probe."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "b1-workbench-role-matrix.py"


def _module():
    spec = importlib.util.spec_from_file_location("b1_workbench_role_matrix", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_base_url_is_redacted_and_rejects_embedded_credentials():
    module = _module()

    assert module._safe_url("https://example.test/api/v1?token=secret#x") == "https://example.test/api/v1"
    assert module._safe_url("https://example.test:not-a-port/api/v1") == "<invalid-url>"
    with pytest.raises(ValueError):
        module.ApiClient("https://user:secret@example.test/api/v1")


def test_role_credentials_are_environment_only(monkeypatch):
    module = _module()
    monkeypatch.delenv("ATP_ENGINEER_TOKEN", raising=False)
    monkeypatch.delenv("ATP_ENGINEER_USERNAME", raising=False)
    monkeypatch.delenv("ATP_ENGINEER_PASSWORD", raising=False)

    with pytest.raises(module.AcceptanceError, match="missing engineer credentials"):
        module._client_for_role("https://example.test/api/v1", 1, "engineer")

    source = SCRIPT.read_text(encoding="utf-8")
    assert "--password" not in source
    assert "credentials were not recorded" in source


def test_http_status_probe_accepts_only_the_expected_denial():
    module = _module()

    class _Client:
        def __init__(self, status):
            self.status = status

        def request(self, method, path, payload=None):
            raise module.ApiHttpError(method, path, self.status)

    module._expect_status(_Client(403), "POST", "/workbench/tasks/case/1/retry", 403)
    with pytest.raises(module.AcceptanceError, match="expected HTTP 403"):
        module._expect_status(_Client(409), "POST", "/workbench/tasks/case/1/retry", 403)


def test_role_matrix_rejects_reused_identity(monkeypatch):
    module = _module()

    class _Client:
        def __init__(self, role):
            self.role = role

        def request(self, method, path, payload=None):
            assert path == "/auth/me"
            return {"id": 1, "role": self.role}

    monkeypatch.setattr(module, "_client_for_role", lambda _base, _timeout, role: _Client(role))
    args = types.SimpleNamespace(
        base_url="https://example.test/api/v1",
        project_id=9,
        foreign_project_id=None,
        require_five_domains=False,
        verify_denials=False,
        timeout=1,
    )

    report = module.run_acceptance(args)

    assert report["status"] == "failed"
    assert report["checks"][-1]["details"] == "three distinct role accounts are required"


def test_complete_role_matrix_checks_visibility_domains_diagnosis_and_denials(monkeypatch):
    module = _module()
    tasks = [
        {
            "id": f"{task_type}:{index}",
            "task_type": task_type,
            "run_id": index,
            "project_id": 9,
            "status": "failed" if task_type == "case" else "passed",
            "can_retry": task_type == "case",
            "can_stop": False,
        }
        for index, task_type in enumerate(module.TASK_TYPES, start=1)
    ]

    class _Client:
        def __init__(self, role):
            self.role = role

        def request(self, method, path, payload=None):
            if path == "/auth/me":
                return {"id": {"admin": 1, "engineer": 2, "viewer": 3}[self.role], "role": self.role}
            if path == "/projects/9/members":
                return [{"user_id": 2, "role": "editor"}, {"user_id": 3, "role": "viewer"}]
            if "project_id=10" in path:
                raise module.ApiHttpError(method, path, 403)
            if path.startswith("/workbench/overview"):
                return {"counts": {"returned_tasks": 5}}
            if path.startswith("/workbench/tasks?"):
                selected = tasks
                if "task_type=" in path:
                    task_type = path.rsplit("task_type=", 1)[1]
                    selected = [item for item in tasks if item["task_type"] == task_type]
                if "limit=1" in path:
                    offset = 1 if "offset=1" in path else 0
                    selected = selected[offset : offset + 1]
                if self.role == "viewer":
                    selected = [{**item, "can_retry": False, "can_stop": False} for item in selected]
                total = 1 if "task_type=" in path else len(tasks)
                return {"items": selected, "total": total, "has_more": False}
            if path.endswith("/failure-diagnosis"):
                return {"task_type": "case", "run_id": 1, "summary": "failed"}
            if method == "POST" and path.endswith("/retry") and self.role == "viewer":
                raise module.ApiHttpError(method, path, 403)
            raise AssertionError((method, path, payload))

    clients = {role: _Client(role) for role in module.ROLES}
    monkeypatch.setattr(module, "_client_for_role", lambda _base, _timeout, role: clients[role])
    args = types.SimpleNamespace(
        base_url="https://example.test/api/v1",
        project_id=9,
        foreign_project_id=10,
        require_five_domains=True,
        verify_denials=True,
        timeout=1,
    )

    report = module.run_acceptance(args)

    assert report["status"] == "passed"
    assert {check["name"] for check in report["checks"]} >= {
        "authentication",
        "project-membership",
        "workbench-read",
        "five-domain-pagination",
        "failure-diagnosis",
        "cross-project",
        "viewer-write-denial",
    }
