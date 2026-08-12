from datetime import timezone
from types import SimpleNamespace

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


def test_system_metrics_support_psutil_success_and_failure(monkeypatch):
    class Psutil:
        def cpu_percent(self, interval=None):
            assert interval is None
            return 12.5

        def virtual_memory(self):
            return SimpleNamespace(percent=34.0, used=100, available=200)

    metrics = {}
    errors = []
    monkeypatch.setattr(performance_metrics, "psutil", Psutil())
    performance_metrics._collect_system_metrics(metrics, errors)
    assert metrics == {
        "cpu_percent": 12.5,
        "memory_percent": 34.0,
        "memory_used_bytes": 100.0,
        "memory_available_bytes": 200.0,
    }
    assert errors == []

    class BrokenPsutil:
        def cpu_percent(self, interval=None):
            raise RuntimeError("metrics unavailable")

    metrics = {}
    errors = []
    monkeypatch.setattr(performance_metrics, "psutil", BrokenPsutil())
    performance_metrics._collect_system_metrics(metrics, errors)
    assert errors == ["system:RuntimeError"]


def test_system_metrics_linux_fallback_tracks_cpu_and_memory(monkeypatch):
    class FakePath:
        reads = {
            "/proc/stat": ["cpu 100 0 0 50 10"],
            "/proc/meminfo": ["MemTotal:       1000 kB", "MemAvailable:    250 kB"],
        }

        def __init__(self, name):
            self.name = name

        def read_text(self, encoding):
            assert encoding == "utf-8"
            return "\n".join(self.reads[self.name])

    monkeypatch.setattr(performance_metrics, "psutil", None)
    monkeypatch.setattr(performance_metrics.sys, "platform", "linux")
    monkeypatch.setattr(performance_metrics.pathlib, "Path", FakePath)
    performance_metrics._last_proc_cpu = None
    first_metrics = {}
    performance_metrics._collect_system_metrics(first_metrics, [])
    assert first_metrics["memory_percent"] == 75.0
    assert first_metrics["memory_used_bytes"] == 768000.0

    FakePath.reads["/proc/stat"] = ["cpu 200 0 0 80 10"]
    second_metrics = {}
    performance_metrics._collect_system_metrics(second_metrics, [])
    assert second_metrics["cpu_percent"] > 0


def test_system_metrics_windows_fallback_uses_native_api(monkeypatch):
    calls = {"times": 0}

    class Kernel32:
        def GetSystemTimes(self, idle, kernel, user):
            calls["times"] += 1
            idle._obj.dwLowDateTime = 100 if calls["times"] == 1 else 175
            kernel._obj.dwLowDateTime = 500 if calls["times"] == 1 else 600
            user._obj.dwLowDateTime = 200
            return 1

        def GlobalMemoryStatusEx(self, memory):
            memory._obj.dwMemoryLoad = 40
            memory._obj.ullTotalPhys = 1000
            memory._obj.ullAvailPhys = 600
            return 1

    monkeypatch.setattr(performance_metrics, "psutil", None)
    monkeypatch.setattr(performance_metrics.sys, "platform", "win32")
    monkeypatch.setattr(performance_metrics.ctypes, "windll", type("Windll", (), {"kernel32": Kernel32()})())
    monkeypatch.setattr(performance_metrics.ctypes, "get_last_error", lambda: 1)
    performance_metrics._last_windows_cpu = None

    first = {}
    second = {}
    errors: list[str] = []
    performance_metrics._collect_system_metrics(first, errors)
    performance_metrics._collect_system_metrics(second, errors)

    assert first["memory_percent"] == 40.0
    assert first["memory_used_bytes"] == 400.0
    assert second["cpu_percent"] == 25.0
    assert errors == []


def test_postgres_metrics_collects_numeric_values_and_records_failures(monkeypatch):
    class Result:
        def mappings(self):
            return self

        def one(self):
            return {"connections": 3, "max_connections": 20.0, "cache_hit_percent": None}

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _statement):
            return Result()

    class Engine:
        def connect(self):
            return Connection()

    import app.core.database as database

    monkeypatch.setattr(database, "sync_engine", Engine(), raising=False)
    metrics = {}
    errors = []
    performance_metrics._collect_postgres_metrics(metrics, errors)
    assert metrics == {"postgres_connections": 3.0, "postgres_max_connections": 20.0}
    assert errors == []

    class BrokenEngine:
        def connect(self):
            raise ConnectionError("database unavailable")

    monkeypatch.setattr(database, "sync_engine", BrokenEngine(), raising=False)
    metrics = {}
    errors = []
    performance_metrics._collect_postgres_metrics(metrics, errors)
    assert errors == ["postgres:ConnectionError"]


def test_minio_metrics_collects_inventory_and_handles_unreachable_bucket(monkeypatch):
    class Client:
        def bucket_exists(self, _bucket):
            return True

        def list_objects(self, _bucket, recursive):
            assert recursive is True
            return [SimpleNamespace(size=4), SimpleNamespace(size=6)]

    monkeypatch.setattr(performance_metrics.minio_client, "get_client", lambda: Client(), raising=False)
    monkeypatch.setattr(performance_metrics.settings, "STORAGE_ALERT_MAX_SCAN_OBJECTS", 1)
    metrics = {}
    errors = []
    performance_metrics._collect_minio_metrics(metrics, errors, include_inventory=True)
    assert metrics["minio_reachable"] == 1.0
    assert metrics["minio_object_count"] == 1.0
    assert metrics["minio_total_bytes"] == 4.0
    assert errors == []

    class Unreachable:
        def bucket_exists(self, _bucket):
            return False

    monkeypatch.setattr(performance_metrics.minio_client, "get_client", lambda: Unreachable(), raising=False)
    metrics = {}
    performance_metrics._collect_minio_metrics(metrics, errors, include_inventory=True)
    assert metrics["minio_reachable"] == 0.0
