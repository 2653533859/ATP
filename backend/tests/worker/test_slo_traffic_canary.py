from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_canary(repo_root: Path):
    script = repo_root / "scripts" / "slo-traffic-canary.py"
    spec = importlib.util.spec_from_file_location("slo_traffic_canary", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeClient:
    def __init__(self, *, target: str = "http://127.0.0.1:8000") -> None:
        self.target = target
        self.requests: list[tuple[str, str, object]] = []
        self.next_run_id = 111

    def request(self, method: str, path: str, payload=None):
        self.requests.append((method, path, payload))
        if path == "/api/v1/projects?limit=100":
            return [{"id": 77}]
        if path.startswith("/api/v1/workbench/overview?"):
            return {"counts": {}}
        if path.startswith("/api/v1/cases?"):
            return [{"id": 42}]
        if path == "/api/v1/cases/42":
            return {
                "id": 42,
                "case_type": "api",
                "status": "active",
                "review_status": "approved",
                "automation_status": "auto",
                "is_ready_for_execution": True,
                "config": {"method": "GET", "url": self.target},
                "steps": [{}],
            }
        if method == "POST" and path == "/api/v1/cases/42/run":
            run_id = self.next_run_id
            self.next_run_id += 1
            return {"id": run_id, "status": "pending"}
        if path.startswith("/api/v1/runs/"):
            return {"id": int(path.rsplit("/", 1)[1]), "status": "passed"}
        raise AssertionError(f"unexpected request: {method} {path}")


def test_default_mode_generates_only_bounded_read_traffic(repo_root, tmp_path, monkeypatch):
    module = _load_canary(repo_root)
    client = FakeClient()
    monkeypatch.setattr(module, "_client_from_environment", lambda *_args, **_kwargs: client)
    report = tmp_path / "report.json"

    result = module.main(
        [
            "--api-base-url",
            "http://atp.test:8000",
            "--iterations",
            "3",
            "--delay-seconds",
            "0",
            "--report",
            str(report),
        ]
    )

    assert result == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["authenticated_read_requests"] == 6
    assert payload["credentials_in_report"] is False
    assert not any(path.endswith("/run") for _method, path, _payload in client.requests)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--case-id", "42"],
        ["--confirm-case-run"],
    ],
)
def test_case_run_requires_id_and_explicit_confirmation(repo_root, arguments):
    module = _load_canary(repo_root)

    with pytest.raises(SystemExit):
        module._parse_args(["--api-base-url", "http://atp.test", *arguments])


def test_explicit_loopback_case_canary_waits_and_passes(repo_root, tmp_path, monkeypatch):
    module = _load_canary(repo_root)
    client = FakeClient()
    sleep_calls = []
    monkeypatch.setattr(module, "_client_from_environment", lambda *_args, **_kwargs: client)
    monkeypatch.setattr(module.time, "sleep", sleep_calls.append)
    report = tmp_path / "report.json"

    result = module.main(
        [
            "--api-base-url",
            "http://atp.test:8000",
            "--project-id",
            "77",
            "--iterations",
            "1",
            "--case-id",
            "42",
            "--confirm-case-run",
            "--run-count",
            "2",
            "--scrape-wait-seconds",
            "20",
            "--report",
            str(report),
        ]
    )

    assert result == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["case_canary"]["target_host"] == "127.0.0.1"
    assert payload["case_canary"]["runs"] == [
        {"run_id": 111, "status": "passed"},
        {"run_id": 112, "status": "passed"},
    ]
    assert [path for method, path, _payload in client.requests if method == "POST"] == [
        "/api/v1/cases/42/run",
        "/api/v1/cases/42/run",
    ]
    assert sleep_calls == [2, 20, 2, 20]


@pytest.mark.parametrize("target", ["https://external.example.test/api", "http://127.0.0.1:not-a-port"])
def test_case_canary_rejects_unsafe_target_before_run(repo_root, tmp_path, monkeypatch, target):
    module = _load_canary(repo_root)
    client = FakeClient(target=target)
    monkeypatch.setattr(module, "_client_from_environment", lambda *_args, **_kwargs: client)
    report = tmp_path / "report.json"

    result = module.main(
        [
            "--api-base-url",
            "http://atp.test:8000",
            "--project-id",
            "77",
            "--iterations",
            "1",
            "--case-id",
            "42",
            "--confirm-case-run",
            "--report",
            str(report),
        ]
    )

    assert result == 1
    assert "target" in json.loads(report.read_text(encoding="utf-8"))["error"]
    assert not any(method == "POST" for method, _path, _payload in client.requests)
