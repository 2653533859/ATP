"""Black-box contract tests for the external performance acceptance command."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_smoke_script():
    path = ROOT / "scripts" / "performance-environment-smoke.py"
    spec = importlib.util.spec_from_file_location("performance_environment_smoke", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_operator_target_parser_supports_bare_grpc_and_explicit_tls():
    smoke = _load_smoke_script()

    bare = smoke.parse_target("GRPC.EXAMPLE.TEST:50051")
    secure = smoke.parse_target("grpcs://grpc.example.test:443", require_tls=True, server_name="svc.example.test")

    assert bare == smoke.Target(host="grpc.example.test", port=50051, tls=False, server_name=None)
    assert secure.tls is True
    assert secure.server_name == "svc.example.test"


@pytest.mark.parametrize(
    ("host", "allowlist", "expected"),
    [
        ("grpc.example.test", ["grpc.example.test"], True),
        ("api.grpc.example.test", ["grpc.example.test"], True),
        ("grpc.example.test.evil.test", ["grpc.example.test"], False),
        ("grpc.example.test", [], True),
    ],
)
def test_operator_allowlist_matches_exact_or_subdomain_only(host, allowlist, expected):
    smoke = _load_smoke_script()

    assert smoke.host_allowed(host, allowlist) is expected


def test_target_check_proves_dns_and_tcp_without_printing_credentials(monkeypatch):
    smoke = _load_smoke_script()

    class _Connection:
        def close(self):
            return None

    monkeypatch.setattr(smoke.socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, None)])
    monkeypatch.setattr(smoke.socket, "create_connection", lambda *args, **kwargs: _Connection())

    detail = smoke.check_target(smoke.Target("grpc.example.test", 50051, False), timeout=1)

    assert "DNS 1 个地址" in detail
    assert "TCP 已连接" in detail


def test_api_node_check_requires_online_node_and_declared_executor():
    smoke = _load_smoke_script()

    class _Client:
        def request(self, method, path, payload=None):
            del payload
            responses = {
                ("GET", "/health"): {"status": "ok"},
                ("GET", "/api/v1/performance/executors"): [
                    {"name": "grpc", "ready": True},
                    {"name": "locust", "ready": True},
                ],
                ("GET", "/api/v1/performance/nodes"): [
                    {
                        "id": 9,
                        "node_id": "worker-a",
                        "queue_name": "performance.worker-a",
                        "status": "online",
                        "capabilities": {"executors": ["grpc", "locust"]},
                        "egress_allowlist": ["grpc.example.test"],
                    }
                ],
            }
            return responses[(method, path)]

    report = smoke.CheckReport()
    node = smoke.check_api_and_node(
        report,
        _Client(),
        expected_executors={"grpc", "locust"},
        node_id="worker-a",
        expected_queue="performance.worker-a",
        target=smoke.Target("grpc.example.test", 443, True),
        require_allowlist=True,
    )

    assert node and node["id"] == 9
    assert not report.has_failures
    assert {item.name for item in report.checks} == {
        "api-health",
        "api-executors",
        "performance-node-queue",
        "performance-node",
        "performance-node-allowlist",
    }


def test_api_node_check_rejects_missing_executor_and_does_not_claim_acceptance():
    smoke = _load_smoke_script()

    class _Client:
        def request(self, method, path, payload=None):
            del payload
            responses = {
                ("GET", "/health"): {"status": "ok"},
                ("GET", "/api/v1/performance/executors"): [
                    {"name": "grpc", "ready": True},
                    {"name": "locust", "ready": True},
                ],
                ("GET", "/api/v1/performance/nodes"): [
                    {
                        "id": 9,
                        "node_id": "worker-a",
                        "queue_name": "performance.worker-a",
                        "status": "online",
                        "capabilities": {"executors": ["grpc"]},
                        "egress_allowlist": ["grpc.example.test"],
                    }
                ],
            }
            return responses[(method, path)]

    report = smoke.CheckReport()
    with pytest.raises(smoke.SmokeError, match="未声明执行器"):
        smoke.check_api_and_node(
            report,
            _Client(),
            expected_executors={"grpc", "locust"},
            node_id="worker-a",
            expected_queue="performance.worker-a",
            target=None,
            require_allowlist=False,
        )

    assert report.has_failures is False
    assert all(item.status == "PASS" for item in report.checks)


def test_api_node_check_waits_for_worker_heartbeat(monkeypatch):
    smoke = _load_smoke_script()

    class _Client:
        def __init__(self):
            self.node_reads = 0

        def request(self, method, path, payload=None):
            del payload
            if (method, path) == ("GET", "/health"):
                return {"status": "ok"}
            if (method, path) == ("GET", "/api/v1/performance/executors"):
                return [{"name": "grpc", "ready": True}]
            if (method, path) == ("GET", "/api/v1/performance/nodes"):
                self.node_reads += 1
                return [
                    {
                        "id": 9,
                        "node_id": "worker-a",
                        "queue_name": "performance.worker-a",
                        "status": "offline" if self.node_reads == 1 else "online",
                        "capabilities": {"executors": ["grpc"]},
                        "egress_allowlist": ["grpc.example.test"],
                    }
                ]
            raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(smoke.time, "sleep", lambda _seconds: None)
    report = smoke.CheckReport()
    node = smoke.check_api_and_node(
        report,
        _Client(),
        expected_executors={"grpc"},
        node_id="worker-a",
        expected_queue="performance.worker-a",
        target=smoke.Target("grpc.example.test", 443, True),
        require_allowlist=True,
        node_ready_timeout=5,
        node_poll_interval=0,
    )

    assert node and node["status"] == "online"
    assert not report.has_failures


def test_report_redacts_sensitive_http_error_fields_and_cli_has_no_token_option():
    smoke = _load_smoke_script()

    assert "--token" not in smoke.build_parser().format_help()
    assert smoke._safe_error({"detail": "bad", "access_token": "secret-value", "password": "pw"}) == (
        "{'detail': 'bad', 'access_token': '<redacted>', 'password': '<redacted>'}"
    )


def test_report_inputs_serialize_path_arguments():
    smoke = _load_smoke_script()

    args = smoke.build_parser().parse_args(["--api-base-url", "http://localhost:8000", "--report", "evidence.json"])

    assert smoke._safe_cli_inputs(args)["report"] == "evidence.json"


def test_api_client_adds_csrf_header_to_state_changing_requests():
    smoke = _load_smoke_script()
    captured = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"{}"

    class _Opener:
        def open(self, request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _Response()

    client = smoke.ApiClient("http://localhost:8000", token=None, timeout=3)
    client._opener = _Opener()

    client.request("POST", "/api/v1/performance/runs/1/stop")

    assert captured["request"].headers.get("X-requested-with") == "XMLHttpRequest"


def test_real_smoke_waits_for_success_checks_summary_and_metrics(monkeypatch):
    smoke = _load_smoke_script()

    class _Client:
        def __init__(self):
            self.calls = []
            self.run_reads = 0

        def request(self, method, path, payload=None):
            self.calls.append((method, path, payload))
            if method == "GET" and path == "/api/v1/performance/tests/42":
                return {
                    "id": 42,
                    "executor": "grpc",
                    "default_options": {"target": "grpcs://grpc.example.test:443", "use_tls": True},
                }
            if method == "POST" and path == "/api/v1/performance/tests/42/run":
                assert payload == {"options": {}, "performance_node_id": 9}
                return {"id": 77, "status": "pending"}
            if method == "GET" and path == "/api/v1/performance/runs/77":
                self.run_reads += 1
                if self.run_reads == 1:
                    return {"id": 77, "status": "running"}
                return {
                    "id": 77,
                    "status": "success",
                    "summary": {"executor": "grpc", "iterations": 12, "error_rate": 0},
                }
            if method == "GET" and path == "/api/v1/performance/runs/77/metrics?limit=2000":
                return [{"node_id": "worker-a", "metrics": {"cpu_percent": 10}}]
            raise AssertionError((method, path, payload))

    monkeypatch.setattr(smoke.time, "sleep", lambda _seconds: None)
    report = smoke.CheckReport()
    run_id = smoke.run_real_test(
        report,
        _Client(),
        test_id=42,
        node_db_id=9,
        expected_executor="grpc",
        target=smoke.Target("grpc.example.test", 443, True),
        require_tls=True,
        timeout=10,
        poll_interval=0.1,
        require_metrics=True,
        max_error_rate=0,
        label="performance-smoke",
    )

    assert run_id == 77
    assert report.checks[-1].status == "PASS"


def test_cancel_real_test_requires_cancelled_terminal_state(monkeypatch):
    smoke = _load_smoke_script()

    class _Client:
        def __init__(self):
            self.run_reads = 0

        def request(self, method, path, payload=None):
            if method == "POST" and path == "/api/v1/performance/tests/44/run":
                assert payload == {"options": {}, "performance_node_id": 9}
                return {"id": 88, "status": "pending"}
            if method == "POST" and path == "/api/v1/performance/runs/88/stop":
                assert payload is None
                return {"id": 88, "status": "cancelling"}
            if method == "GET" and path == "/api/v1/performance/runs/88":
                self.run_reads += 1
                return {"id": 88, "status": "cancelling" if self.run_reads == 1 else "cancelled"}
            raise AssertionError((method, path, payload))

    monkeypatch.setattr(smoke.time, "sleep", lambda _seconds: None)
    report = smoke.CheckReport()

    run_id = smoke.cancel_real_test(
        report,
        _Client(),
        test_id=44,
        node_db_id=9,
        wait_before_cancel=0,
        timeout=10,
        poll_interval=0.1,
    )

    assert run_id == 88
    assert report.checks == [
        smoke.Check(name="performance-cancel", status="PASS", detail="run=88 从运行态进入 cancelled")
    ]


def test_main_refuses_real_run_without_target_or_node():
    smoke = _load_smoke_script()

    with pytest.raises(SystemExit):
        smoke.main(["--api-base-url", "https://atp.example.test", "--smoke-test-id", "42"])


def test_docker_worker_check_validates_running_container_and_runtime_dependencies(monkeypatch):
    smoke = _load_smoke_script()
    commands: list[list[str]] = []

    class _Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout):
            self.stdout = stdout

    def fake_run(command, **_kwargs):
        commands.append(command)
        if command[1:3] == ["inspect", "worker-a"]:
            return _Result('[{"State":{"Status":"running"}}]')
        if command[1:3] == ["exec", "worker-a"] and "python" in command:
            if any("sync_playwright" in item for item in command):
                return _Result(
                    "chromium=/ms-playwright/chromium/firefox=/ms-playwright/firefox/webkit=/ms-playwright/webkit"
                )
            return _Result("python-dependencies-ok")
        if command[1:3] == ["exec", "worker-a"] and "k6" in command:
            return _Result("k6 v2.1.0")
        if command[1:3] == ["exec", "worker-a"] and "jmeter" in command:
            return _Result("Apache JMeter 5.6.3")
        raise AssertionError(command)

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)
    report = smoke.CheckReport()

    smoke.check_docker_worker(report, container="worker-a", image=None, timeout=5)

    assert not report.has_failures
    assert any(command[1:3] == ["exec", "worker-a"] for command in commands)


def test_jmeter_smoke_fixture_is_local_and_credential_free():
    fixture = (ROOT / "deploy" / "performance-acceptance" / "jmeter_smoke.jmx").read_text(encoding="utf-8")

    assert '<jmeterTestPlan version="1.2"' in fixture
    assert '<stringProp name="HTTPSampler.domain">127.0.0.1</stringProp>' in fixture
    assert '<stringProp name="HTTPSampler.path">/login</stringProp>' in fixture
    assert "password" not in fixture.lower()
    assert "username" not in fixture.lower()
