import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _setup(monkeypatch, *, total_bytes: int, threshold_gb: float, interval_seconds: int = 3600):
    class FakeMinioObject:
        def __init__(self, size):
            self.size = size

    fake_minio = types.SimpleNamespace(
        list_objects=lambda prefix="": [FakeMinioObject(total_bytes)],
        delete_file=lambda *args, **kwargs: None,
    )

    cache: dict[str, object] = {}

    async def get_cache(key, db=2):
        return cache.get(key)

    async def set_cache(key, value, ttl_seconds=300, db=2):
        cache[key] = value

    async def delete_cache(key, db=2):
        cache.pop(key, None)

    async def delete_pattern(pattern, db=2):
        return None

    fake_redis = types.SimpleNamespace(
        get_json_cache=get_cache,
        set_json_cache=set_cache,
        delete_json_cache=delete_cache,
        delete_json_cache_pattern=delete_pattern,
    )

    monkeypatch.setitem(sys.modules, "app.core.minio_client", fake_minio)
    monkeypatch.setitem(sys.modules, "app.core.redis_client", fake_redis)

    sys.modules.pop("app.services.storage_alerts", None)
    from app.services import storage_alerts

    monkeypatch.setattr(storage_alerts, "get_json_cache", get_cache)
    monkeypatch.setattr(storage_alerts, "set_json_cache", set_cache)
    monkeypatch.setattr(storage_alerts, "delete_json_cache", delete_cache)
    monkeypatch.setattr(storage_alerts, "minio_client", fake_minio)
    monkeypatch.setattr(storage_alerts.settings, "STORAGE_ALERT_SIZE_GB", threshold_gb, raising=False)
    monkeypatch.setattr(storage_alerts.settings, "STORAGE_ALERT_INTERVAL_SECONDS", interval_seconds, raising=False)
    monkeypatch.setattr(storage_alerts.settings, "STORAGE_ALERT_MAX_SCAN_OBJECTS", 100000, raising=False)
    monkeypatch.setattr(storage_alerts.settings, "MINIO_BUCKET", "atp", raising=False)

    return storage_alerts, cache


def test_check_returns_none_when_threshold_disabled(monkeypatch):
    storage_alerts, cache = _setup(monkeypatch, total_bytes=5 * (1024 ** 3), threshold_gb=0)

    result = asyncio.run(storage_alerts.check_and_record_alert())

    assert result is None
    assert cache == {}


def test_check_clears_stale_alert_when_disabled(monkeypatch):
    storage_alerts, cache = _setup(monkeypatch, total_bytes=0, threshold_gb=0)
    cache[storage_alerts.ALERT_CACHE_KEY] = {"stale": True}

    asyncio.run(storage_alerts.check_and_record_alert())

    assert storage_alerts.ALERT_CACHE_KEY not in cache


def test_check_writes_alert_when_threshold_exceeded(monkeypatch):
    storage_alerts, cache = _setup(monkeypatch, total_bytes=10 * (1024 ** 3), threshold_gb=5.0)

    result = asyncio.run(storage_alerts.check_and_record_alert())

    assert result is not None
    assert result["bucket"] == "atp"
    assert result["threshold_gb"] == 5.0
    assert result["total_gb"] == 10.0
    assert cache[storage_alerts.ALERT_CACHE_KEY] == result


def test_check_keeps_existing_alert_within_interval(monkeypatch):
    storage_alerts, cache = _setup(monkeypatch, total_bytes=10 * (1024 ** 3), threshold_gb=5.0)
    cached_payload = {"existing": True}
    cache[storage_alerts.ALERT_CACHE_KEY] = cached_payload

    result = asyncio.run(storage_alerts.check_and_record_alert())

    assert result is cached_payload


def test_check_clears_alert_when_usage_returns_below_threshold(monkeypatch):
    storage_alerts, cache = _setup(monkeypatch, total_bytes=int(1.5 * 1024 ** 3), threshold_gb=5.0)
    cache[storage_alerts.ALERT_CACHE_KEY] = {"existing": True}

    result = asyncio.run(storage_alerts.check_and_record_alert())

    assert result is None
    assert storage_alerts.ALERT_CACHE_KEY not in cache


def test_get_current_alert_returns_cached_payload(monkeypatch):
    storage_alerts, cache = _setup(monkeypatch, total_bytes=0, threshold_gb=5.0)
    cache[storage_alerts.ALERT_CACHE_KEY] = {"x": 1}

    result = asyncio.run(storage_alerts.get_current_alert())

    assert result == {"x": 1}


def test_check_skips_when_object_count_exceeds_scan_limit(monkeypatch):
    storage_alerts, cache = _setup(monkeypatch, total_bytes=10 * (1024 ** 3), threshold_gb=5.0)
    # 模拟 list_objects 返回比上限更多的对象
    monkeypatch.setattr(storage_alerts.settings, "STORAGE_ALERT_MAX_SCAN_OBJECTS", 2, raising=False)

    class FakeObj:
        size = 1024 ** 3

    monkeypatch.setattr(
        storage_alerts.minio_client,
        "list_objects",
        lambda prefix="": [FakeObj(), FakeObj(), FakeObj(), FakeObj()],
    )

    result = asyncio.run(storage_alerts.check_and_record_alert())

    assert result is None
    # 超限时不应该写入告警
    assert storage_alerts.ALERT_CACHE_KEY not in cache
