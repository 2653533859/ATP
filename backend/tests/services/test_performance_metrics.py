from datetime import timezone

from app.services import performance_metrics


def test_resource_sampler_returns_timestamped_metrics_and_inventory_cadence(monkeypatch):
    monkeypatch.setattr(
        performance_metrics,
        "_collect_system_metrics",
        lambda metrics, _errors: metrics.update(cpu_percent=42.0, memory_percent=68.0),
    )
    monkeypatch.setattr(
        performance_metrics,
        "_collect_postgres_metrics",
        lambda metrics, _errors: metrics.update(postgres_connections=4.0),
    )
    monkeypatch.setattr(
        performance_metrics,
        "_collect_redis_metrics",
        lambda metrics, _errors: metrics.update(redis_connected_clients=2.0),
    )
    inventory_flags: list[bool] = []
    monkeypatch.setattr(
        performance_metrics,
        "_collect_minio_metrics",
        lambda metrics, _errors, include_inventory: (
            inventory_flags.append(include_inventory),
            metrics.update(minio_reachable=1.0),
        ),
    )
    monkeypatch.setattr(performance_metrics.socket, "gethostname", lambda: "perf-node")

    sampler = performance_metrics.PerformanceResourceSampler()
    first = sampler.sample()
    second = sampler.sample()

    assert first["node_id"] == "perf-node"
    assert first["source"] == "performance-worker"
    assert first["metrics"] == {
        "cpu_percent": 42.0,
        "memory_percent": 68.0,
        "postgres_connections": 4.0,
        "redis_connected_clients": 2.0,
        "minio_reachable": 1.0,
    }
    assert first["errors"] == []
    assert first["captured_at"].tzinfo == timezone.utc
    assert second["captured_at"].tzinfo == timezone.utc
    assert inventory_flags == [True, False]


def test_minio_metrics_report_probe_failure_without_raising(monkeypatch):
    class BrokenClient:
        def bucket_exists(self, _bucket):
            raise TimeoutError("not available")

    monkeypatch.setattr(performance_metrics.minio_client, "get_client", lambda: BrokenClient(), raising=False)
    metrics: dict[str, float] = {}
    errors: list[str] = []

    performance_metrics._collect_minio_metrics(metrics, errors, include_inventory=True)

    assert metrics["minio_probe_ms"] >= 0
    assert errors == ["minio:TimeoutError"]


def test_redis_metrics_close_client_after_sampling(monkeypatch):
    class FakeClient:
        closed = False

        def info(self):
            return {
                "connected_clients": 3,
                "used_memory": 100,
                "used_memory_peak": 120,
                "instantaneous_ops_per_sec": 5,
                "blocked_clients": 0,
            }

        def close(self):
            self.closed = True

    client = FakeClient()
    monkeypatch.setattr(
        performance_metrics.redis.Redis,
        "from_url",
        staticmethod(lambda *_args, **_kwargs: client),
    )
    metrics: dict[str, float] = {}
    errors: list[str] = []

    performance_metrics._collect_redis_metrics(metrics, errors)

    assert metrics["redis_connected_clients"] == 3.0
    assert metrics["redis_used_memory_bytes"] == 100.0
    assert client.closed is True
    assert errors == []
