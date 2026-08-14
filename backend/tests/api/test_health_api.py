import asyncio
import sys

from app.api.v1 import health


def test_dependency_health_reports_all_dependencies_ready(monkeypatch):
    async def postgres():
        return health.DependencyCheck(status="ok", latency_ms=1.2, code="ok")

    async def redis():
        return health.DependencyCheck(status="ok", latency_ms=2.3, code="ok")

    async def minio():
        return health.DependencyCheck(status="ok", latency_ms=3.4, code="ok")

    monkeypatch.setattr(health, "_probe_postgres", postgres)
    monkeypatch.setattr(health, "_probe_redis", redis)
    monkeypatch.setattr(health, "_probe_minio", minio)

    result = asyncio.run(health.get_dependency_health())

    assert result.status == "ok"
    assert set(result.dependencies) == {"postgres", "redis", "minio"}
    assert all(item.status == "ok" for item in result.dependencies.values())


def test_dependency_health_route_requires_admin():
    route = next(item for item in health.router.routes if item.path == "/health/dependencies")

    assert any(dependency.call is health.require_admin for dependency in route.dependant.dependencies)


def test_dependency_health_reports_degraded_without_exposing_connection_details(monkeypatch):
    async def postgres():
        return health.DependencyCheck(status="ok", latency_ms=1.2, code="ok")

    async def redis():
        return health.DependencyCheck(status="error", latency_ms=5.0, code="timeout")

    async def minio():
        return health.DependencyCheck(status="error", latency_ms=4.0, code="bucket_missing")

    monkeypatch.setattr(health, "_probe_postgres", postgres)
    monkeypatch.setattr(health, "_probe_redis", redis)
    monkeypatch.setattr(health, "_probe_minio", minio)

    result = asyncio.run(health.get_dependency_health())
    payload = result.model_dump()

    assert result.status == "degraded"
    assert payload["dependencies"]["redis"]["code"] == "timeout"
    assert payload["dependencies"]["minio"]["code"] == "bucket_missing"
    assert "172.31.27.133" not in str(payload)
    assert "password" not in str(payload).lower()


def test_individual_dependency_probes_normalize_failures_and_release_redis(monkeypatch):
    class FakeSession:
        async def execute(self, _statement):
            return None

    class FakeSessionContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, _exc_type, _exc_value, _traceback):
            return None

    database = sys.modules["app.core.database"]
    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: FakeSessionContext(), raising=False)

    class FakeRedis:
        def __init__(self):
            self.closed = False

        async def ping(self):
            raise asyncio.TimeoutError

    redis = FakeRedis()
    redis_module = sys.modules["app.core.redis_client"]
    monkeypatch.setattr(redis_module, "get_async_redis", lambda db=2: redis, raising=False)

    async def close_async_redis(client):
        client.closed = True

    monkeypatch.setattr(redis_module, "close_async_redis", close_async_redis, raising=False)

    class FakeMinio:
        def bucket_exists(self, _bucket):
            return False

    minio_module = sys.modules["app.core.minio_client"]
    monkeypatch.setattr(minio_module, "get_client", lambda: FakeMinio(), raising=False)

    postgres = asyncio.run(health._probe_postgres())
    redis_result = asyncio.run(health._probe_redis())
    minio = asyncio.run(health._probe_minio())

    assert postgres.status == "ok"
    assert redis_result.model_dump(include={"status", "code"}) == {"status": "error", "code": "timeout"}
    assert redis.closed is True
    assert minio.model_dump(include={"status", "code"}) == {"status": "error", "code": "bucket_missing"}
