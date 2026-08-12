from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services import performance_node


def _node(**overrides):
    values = {
        "name": "worker-a",
        "enabled": True,
        "status": "online",
        "last_heartbeat_at": datetime.now(timezone.utc),
        "max_vus": None,
        "max_concurrency": None,
        "egress_allowlist": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_parse_egress_allowlist_normalizes_and_deduplicates():
    assert performance_node.parse_egress_allowlist(" API.Example.test,api.example.test, ") == ["api.example.test"]
    assert performance_node.parse_egress_allowlist(["A.test", "a.test", ""]) == ["a.test"]


def test_validate_node_options_enforces_peak_vus_across_stages_and_scenarios():
    node = _node(max_vus=10)

    performance_node.validate_node_options(
        {
            "stages": [{"target": 4}],
            "scenarios": {"checkout": {"executor": "constant-vus", "vus": 10}},
        },
        node,
    )

    node.max_vus = 10
    try:
        performance_node.validate_node_options(
            {"stages": [{"target": 4}], "scenarios": {"checkout": {"vus": 11}}},
            node,
        )
    except performance_node.PerformanceNodeConstraintError as exc:
        assert "VUs" in str(exc)
    else:
        raise AssertionError("节点应拒绝超过 max_vus 的场景")


def test_validate_node_options_rejects_non_allowlisted_target_without_suffix_bypass():
    node = _node(egress_allowlist=["example.test"])

    performance_node.validate_node_options({"env": {"TARGET_URL": "https://api.example.test/path"}}, node)

    try:
        performance_node.validate_node_options({"env": {"TARGET_URL": "https://notexample.test"}}, node)
    except performance_node.PerformanceNodeConstraintError as exc:
        assert "allowlist" in str(exc)
    else:
        raise AssertionError("节点应拒绝不在 egress allowlist 中的目标")


def test_validate_node_options_checks_target_hosts_inside_dataset_rows():
    node = _node(egress_allowlist=["example.test"])
    options = {"env": {"ATP_DATASET_JSON": '[{"TARGET_URL":"https://evil.test"}]'}}

    try:
        performance_node.validate_node_options(options, node)
    except performance_node.PerformanceNodeConstraintError as exc:
        assert "evil.test" in str(exc)
    else:
        raise AssertionError("节点出口校验不能被数据集中的目标 URL 绕过")


def test_validate_node_options_checks_target_metrics_url_from_worker_environment(monkeypatch):
    monkeypatch.setenv("ATP_PROM_URL", "http://evil.test:9090")
    node = _node(egress_allowlist=["prometheus.example.test"])

    try:
        performance_node.validate_node_options(
            {
                "target_metrics": {
                    "url_env": "ATP_PROM_URL",
                    "queries": {"cpu": "up"},
                }
            },
            node,
        )
    except performance_node.PerformanceNodeConstraintError as exc:
        assert "evil.test" in str(exc)
    else:
        raise AssertionError("worker 环境中的 Prometheus 地址不能绕过节点 allowlist")


def test_validate_node_options_normalizes_grpc_target_and_concurrency():
    node = _node(max_vus=2, egress_allowlist=["api.example.test"])
    performance_node.validate_node_options(
        {
            "target": "grpcs://api.example.test:50051",
            "service": "demo.v1.Greeter",
            "method": "SayHello",
            "request": {},
            "concurrency": "2",
            "duration_seconds": "10s",
        },
        node,
        executor="grpc",
    )

    try:
        performance_node.validate_node_options(
            {
                "target": "api.example.test:50051",
                "service": "demo.v1.Greeter",
                "method": "SayHello",
                "request": {},
                "concurrency": "3",
            },
            node,
            executor="grpc",
        )
    except performance_node.PerformanceNodeConstraintError as exc:
        assert "VUs" in str(exc)
    else:
        raise AssertionError("gRPC concurrency should respect node max_vus")


def test_effective_node_status_respects_disabled_draining_and_heartbeat_timeout(monkeypatch):
    now = datetime(2026, 8, 7, tzinfo=timezone.utc)
    monkeypatch.setattr(performance_node.settings, "PERFORMANCE_NODE_HEARTBEAT_TIMEOUT_SECONDS", 90)

    assert performance_node.effective_node_status(_node(enabled=False), now) == "disabled"
    assert performance_node.effective_node_status(_node(status="offline"), now) == "offline"
    assert performance_node.effective_node_status(_node(status="draining"), now) == "draining"
    assert performance_node.effective_node_status(_node(last_heartbeat_at=None), now) == "offline"
    assert (
        performance_node.effective_node_status(_node(last_heartbeat_at=now - timedelta(seconds=91)), now) == "offline"
    )
    assert performance_node.effective_node_status(_node(last_heartbeat_at=now), now) == "online"


def test_enqueue_performance_run_uses_node_queue_when_available():
    calls = []

    class _Task:
        def apply_async(self, *, args, queue):
            calls.append((args, queue))

        def delay(self, *_args):
            raise AssertionError("应通过节点队列派发")

    performance_node.enqueue_performance_run(_Task(), 42, "performance.node-a")

    assert calls == [((42,), "performance.node-a")]
