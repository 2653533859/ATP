"""Black-box contract tests for the external performance acceptance command."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

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


def test_prometheus_check_proves_readiness_and_query(monkeypatch):
    smoke = _load_smoke_script()

    class _Response:
        status = 200

        def __init__(self, body: bytes):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def getcode(self):
            return self.status

        def read(self):
            return self._body

    calls: list[str] = []

    def fake_urlopen(request, timeout):
        del timeout
        calls.append(request.full_url)
        if request.full_url.endswith("/-/ready"):
            return _Response(b"Prometheus Server is Healthy.")
        return _Response(b'{"status":"success","data":{"result":[{"metric":{"job":"atp"}}]}}')

    monkeypatch.setattr(smoke, "urlopen", fake_urlopen)
    report = smoke.CheckReport()

    smoke.check_prometheus(
        report,
        base_url="https://prometheus.example.test:9090",
        query="up{job='atp'}",
        timeout=2,
    )

    assert not report.has_failures
    assert report.checks[-1].name == "prometheus"
    assert "api/v1/query?query=up%7Bjob%3D%27atp%27%7D" in calls[-1]


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@prometheus.example.test:9090",
        "https://prometheus.example.test:9090/?token=secret",
    ],
)
def test_prometheus_check_rejects_credentials_or_query_in_url(url):
    smoke = _load_smoke_script()

    with pytest.raises(smoke.SmokeError, match="不能包含"):
        smoke.check_prometheus(smoke.CheckReport(), base_url=url, query="up", timeout=2)


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


def test_kubernetes_check_can_prove_nodes_replicas_and_worker_resources(monkeypatch):
    smoke = _load_smoke_script()
    deployment = {
        "spec": {
            "replicas": 2,
            "selector": {"matchLabels": {"app": "performance-worker"}},
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "performance-worker",
                            "resources": {
                                "requests": {"cpu": "1000m", "memory": "1Gi"},
                                "limits": {"cpu": "2000m", "memory": "2Gi"},
                            },
                        }
                    ]
                }
            },
        },
        "status": {"availableReplicas": 2},
    }
    nodes = {
        "items": [
            {
                "metadata": {"name": "node-a"},
                "spec": {},
                "status": {"conditions": [{"type": "Ready", "status": "True"}]},
            },
            {
                "metadata": {"name": "node-b"},
                "spec": {},
                "status": {"conditions": [{"type": "Ready", "status": "True"}]},
            },
        ]
    }
    pods = {
        "items": [
            {
                "metadata": {"name": "performance-worker-0"},
                "status": {
                    "phase": "Running",
                    "containerStatuses": [{"name": "performance-worker", "ready": True}],
                },
            }
        ]
    }

    def fake_run(command, **_kwargs):
        if command[-5:] == ["get", "deployment", "atp-performance-worker", "-o", "json"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps(deployment), stderr="")
        if command[-4:-1] == ["rollout", "status", "deployment/atp-performance-worker"]:
            return SimpleNamespace(returncode=0, stdout="deployment successfully rolled out", stderr="")
        if command[-4:] == ["get", "nodes", "-o", "json"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps(nodes), stderr="")
        if command[-6:] == ["get", "pods", "-l", "app=performance-worker", "-o", "json"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps(pods), stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)
    report = smoke.CheckReport()

    smoke.check_kubernetes(
        report,
        context=None,
        namespace="qa",
        deployment="atp-performance-worker",
        pod_selector="app=performance-worker",
        container="performance-worker",
        verify_worker_image=False,
        min_ready_nodes=2,
        min_worker_replicas=2,
        require_worker_resources=True,
        timeout=2,
    )

    assert not report.has_failures
    assert {item.name for item in report.checks} == {
        "kubernetes-rollout",
        "kubernetes-replicas",
        "kubernetes-nodes",
        "kubernetes-worker-resources",
        "kubernetes-pod",
    }


def test_kubernetes_check_rejects_insufficient_ready_nodes(monkeypatch):
    smoke = _load_smoke_script()
    responses = {
        "deployment": {
            "spec": {"replicas": 2, "selector": {"matchLabels": {"app": "performance-worker"}}},
            "status": {"availableReplicas": 2},
        },
        "nodes": {
            "items": [
                {
                    "metadata": {"name": "node-a"},
                    "spec": {},
                    "status": {"conditions": [{"type": "Ready", "status": "True"}]},
                }
            ]
        },
    }

    def fake_run(command, **_kwargs):
        if "get" in command and "deployment" in command:
            return SimpleNamespace(returncode=0, stdout=json.dumps(responses["deployment"]), stderr="")
        if "rollout" in command:
            return SimpleNamespace(returncode=0, stdout="rolled out", stderr="")
        if "get" in command and "nodes" in command:
            return SimpleNamespace(returncode=0, stdout=json.dumps(responses["nodes"]), stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)

    with pytest.raises(smoke.SmokeError, match="Ready 节点不足"):
        smoke.check_kubernetes(
            smoke.CheckReport(),
            context=None,
            namespace="qa",
            deployment="atp-performance-worker",
            pod_selector="app=performance-worker",
            container=None,
            verify_worker_image=False,
            min_ready_nodes=2,
            timeout=2,
        )


def test_report_redacts_sensitive_http_error_fields_and_cli_has_no_token_option():
    smoke = _load_smoke_script()

    assert "--token" not in smoke.build_parser().format_help()
    assert smoke._safe_error({"detail": "bad", "access_token": "secret-value", "password": "pw"}) == (
        "{'detail': 'bad', 'access_token': '<redacted>', 'password': '<redacted>'}"
    )


def test_report_inputs_redact_url_credentials_and_query(tmp_path, monkeypatch):
    smoke = _load_smoke_script()

    args = smoke.build_parser().parse_args(
        [
            "--prometheus-url",
            "https://user:password@prometheus.example.test:9090/?token=secret",
            "--report",
            str(tmp_path / "evidence.json"),
        ]
    )
    monkeypatch.setattr(
        smoke.sys,
        "argv",
        [
            "performance-environment-smoke.py",
            "--prometheus-url",
            "https://user:password@prometheus.example.test:9090/?token=secret",
        ],
    )
    report = smoke.CheckReport()
    report.write(tmp_path / "evidence.json", args=args)
    content = (tmp_path / "evidence.json").read_text(encoding="utf-8")

    assert "password" not in content
    assert "secret" not in content
    assert "<redacted>" in content


def test_report_inputs_serialize_path_arguments():
    smoke = _load_smoke_script()

    args = smoke.build_parser().parse_args(["--api-base-url", "http://localhost:8000", "--report", "evidence.json"])

    assert smoke._safe_cli_inputs(args)["report"] == "evidence.json"


def test_default_idempotency_key_reuses_ci_identity_and_scopes_requests(monkeypatch):
    smoke = _load_smoke_script()

    monkeypatch.setenv("GITHUB_RUN_ID", "9876")
    monkeypatch.delenv("CI_PIPELINE_ID", raising=False)

    first = smoke.default_idempotency_key("smoke", 42)
    replay = smoke.default_idempotency_key("smoke", 42)
    cancel = smoke.default_idempotency_key("cancel", 42)

    assert first == replay == "ci-9876-acceptance-smoke-42"
    assert cancel == "ci-9876-acceptance-cancel-42"
    assert first != cancel


def test_default_idempotency_key_is_unique_for_local_acceptance(monkeypatch):
    smoke = _load_smoke_script()

    for name in ("CI_PIPELINE_ID", "GITHUB_RUN_ID", "BUILD_BUILDID", "BUILD_ID"):
        monkeypatch.delenv(name, raising=False)

    first = smoke.default_idempotency_key("smoke", 42)
    second = smoke.default_idempotency_key("smoke", 42)

    assert first.startswith("cli-acceptance-smoke-42-")
    assert second.startswith("cli-acceptance-smoke-42-")
    assert first != second


def test_default_idempotency_key_rejects_invalid_explicit_value():
    smoke = _load_smoke_script()

    with pytest.raises(smoke.SmokeError, match="幂等键"):
        smoke.default_idempotency_key("smoke", 42, explicit="invalid key")


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


def test_validate_metric_samples_requires_requested_sources_and_nonempty_metrics():
    smoke = _load_smoke_script()

    sources = smoke.validate_metric_samples(
        [
            {"source": "performance-worker", "metrics": {"cpu_percent": 12}, "errors": []},
            {"source": "target-service-prometheus", "metrics": {"request_count": 8}, "errors": []},
        ],
        required_sources={"performance-worker", "target-service-prometheus"},
    )

    assert sources == "performance-worker, target-service-prometheus"

    with pytest.raises(smoke.SmokeError, match="缺少有效指标来源"):
        smoke.validate_metric_samples(
            [{"source": "performance-worker", "metrics": {}, "errors": ["Prometheus unavailable"]}],
            required_sources={"target-service-prometheus"},
        )


def test_validate_baseline_comparison_can_reject_regressions():
    smoke = _load_smoke_script()
    payload = {
        "baseline_run_id": 10,
        "run_id": 11,
        "metrics": [
            {"metric": "rps", "direction": "improvement"},
            {"metric": "p95_ms", "direction": "regression"},
        ],
    }

    assert smoke.validate_baseline_comparison(payload) == "baseline_run=10 metrics=2 regressions=1"
    assert smoke.validate_baseline_comparison(payload, expected_run_id=11).startswith("baseline_run=10")
    with pytest.raises(smoke.SmokeError, match="基线出现回归"):
        smoke.validate_baseline_comparison(payload, fail_on_regression=True)
    with pytest.raises(smoke.SmokeError, match="run_id"):
        smoke.validate_baseline_comparison(payload, expected_run_id=12)


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
                assert payload == {
                    "options": {},
                    "performance_node_id": 9,
                    "idempotency_key": "ci-123-smoke",
                }
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
                return [{"node_id": "worker-a", "source": "performance-worker", "metrics": {"cpu_percent": 10}}]
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
        idempotency_key="ci-123-smoke",
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
                assert payload == {
                    "options": {},
                    "performance_node_id": 9,
                    "idempotency_key": "ci-123-cancel",
                }
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
        idempotency_key="ci-123-cancel",
    )

    assert run_id == 88
    assert report.checks == [
        smoke.Check(name="performance-cancel", status="PASS", detail="run=88 从运行态进入 cancelled")
    ]


def test_main_refuses_real_run_without_target_or_node():
    smoke = _load_smoke_script()

    with pytest.raises(SystemExit):
        smoke.main(["--api-base-url", "https://atp.example.test", "--smoke-test-id", "42"])


def test_main_rejects_baseline_gate_for_cancel_only_acceptance():
    smoke = _load_smoke_script()

    with pytest.raises(SystemExit):
        smoke.main(
            [
                "--api-base-url",
                "https://atp.example.test",
                "--node-id",
                "worker-a",
                "--target",
                "grpc.example.test:443",
                "--cancel-test-id",
                "42",
                "--require-baseline",
            ]
        )


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
