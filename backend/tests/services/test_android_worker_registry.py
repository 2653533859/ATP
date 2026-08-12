import asyncio
import json


class _FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}
        self.deleted = []

    async def set(self, key, value, *, ex):
        self.values[key] = value
        self.expirations[key] = ex

    async def delete(self, key):
        self.deleted.append(key)
        self.values.pop(key, None)

    async def mget(self, keys):
        return [self.values.get(key) for key in keys]

    async def scan_iter(self, *, match):
        prefix = match.removesuffix("*")
        for key in self.values:
            if key.startswith(prefix):
                yield key

    async def aclose(self):
        return None


def test_android_worker_registry_registers_lists_and_unregisters(monkeypatch):
    from app.core import config
    from app.services import android_worker_registry as registry

    redis = _FakeRedis()
    monkeypatch.setattr(config.settings, "ANDROID_WORKER_REGISTRY_PREFIX", "test:android")
    monkeypatch.setattr(config.settings, "ANDROID_WORKER_TTL_SECONDS", 45)
    monkeypatch.setattr(registry._redis_client, "get_async_redis", lambda: redis)
    monkeypatch.setattr(registry._redis_client, "close_async_redis", lambda client: client.aclose())

    payload = asyncio.run(registry.register_android_worker("win-a", queues=["android", "mobile_special"], client=redis))

    assert payload["worker_id"] == "win-a"
    assert payload["status"] == "online"
    assert payload["capabilities"] == ["adb", "android"]
    assert redis.expirations[registry.worker_key("win-a")] == 45
    assert json.loads(redis.values[registry.worker_key("win-a")])["queues"] == ["android", "mobile_special"]

    workers = asyncio.run(registry.list_android_workers())
    assert [worker["worker_id"] for worker in workers] == ["win-a"]

    asyncio.run(registry.unregister_android_worker("win-a"))
    assert redis.deleted == [registry.worker_key("win-a")]
