import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.v1 import ai_healing_stats
from app.schemas.ai_healing_stats import AIHealingProductionFeedback, AIHealingStatsOut


def _stats(total: int = 3) -> AIHealingStatsOut:
    return AIHealingStatsOut(
        total_feedback_count=total,
        adopted_count=2,
        rejected_count=1,
        adopted_rate=0.667,
        high_quality_example_count=1,
        by_case_type=[],
        top_error_fingerprints=[],
        recent_trend=[],
        production_feedback=AIHealingProductionFeedback(
            regression_triggered_count=1,
            regression_success_count=1,
            regression_success_rate=1.0,
        ),
    )


def test_ai_healing_stats_cache_key_uses_days():
    assert ai_healing_stats._cache_key(days=14) == "atp:ai-healing:stats:days=14"


def test_ai_healing_stats_returns_cached_payload(monkeypatch):
    calls = {"build": 0, "write": 0}
    cached_payload = _stats(total=9).model_dump()

    async def fake_get_cache(key):
        assert key == "atp:ai-healing:stats:days=7"
        return cached_payload

    async def fake_set_cache(_key, _value, ttl_seconds):
        calls["write"] += 1
        assert ttl_seconds == 300

    async def fake_build(_db, *, days):
        calls["build"] += 1
        return _stats(total=days)

    monkeypatch.setattr(ai_healing_stats, "get_json_cache", fake_get_cache)
    monkeypatch.setattr(ai_healing_stats, "set_json_cache", fake_set_cache)
    monkeypatch.setattr(ai_healing_stats, "build_ai_healing_stats", fake_build)

    result = asyncio.run(ai_healing_stats.get_ai_healing_stats(days=7, db=object(), _=None))

    assert result.total_feedback_count == 9
    assert calls == {"build": 0, "write": 0}


def test_ai_healing_stats_builds_and_writes_cache_on_miss(monkeypatch):
    written = {}

    async def fake_get_cache(_key):
        return None

    async def fake_set_cache(key, value, ttl_seconds):
        written["key"] = key
        written["value"] = value
        written["ttl"] = ttl_seconds

    async def fake_build(db, *, days):
        assert db == "db"
        return _stats(total=days)

    monkeypatch.setattr(ai_healing_stats, "get_json_cache", fake_get_cache)
    monkeypatch.setattr(ai_healing_stats, "set_json_cache", fake_set_cache)
    monkeypatch.setattr(ai_healing_stats, "build_ai_healing_stats", fake_build)

    result = asyncio.run(ai_healing_stats.get_ai_healing_stats(days=30, db="db", _=None))

    assert result.total_feedback_count == 30
    assert written["key"] == "atp:ai-healing:stats:days=30"
    assert written["value"]["total_feedback_count"] == 30
    assert written["ttl"] == 300


def test_ai_healing_stats_cache_failures_do_not_break_request(monkeypatch):
    async def failing_get(_key):
        raise RuntimeError("redis down")

    async def failing_set(_key, _value, ttl_seconds):
        raise RuntimeError("redis still down")

    async def fake_build(_db, *, days):
        return _stats(total=days)

    monkeypatch.setattr(ai_healing_stats, "get_json_cache", failing_get)
    monkeypatch.setattr(ai_healing_stats, "set_json_cache", failing_set)
    monkeypatch.setattr(ai_healing_stats, "build_ai_healing_stats", fake_build)

    result = asyncio.run(ai_healing_stats.get_ai_healing_stats(days=5, db=object(), _=None))

    assert result.total_feedback_count == 5
