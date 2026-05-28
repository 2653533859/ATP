from pathlib import Path


def repo_path(path: str) -> Path:
    return Path(__file__).resolve().parents[2] / path


def test_ai_healing_stats_router_registered():
    content = repo_path("app/api/v1/router.py").read_text(encoding="utf-8")

    assert "ai_healing_stats" in content
    assert "router.include_router(ai_healing_stats.router)" in content


def test_ai_healing_stats_endpoint_is_cached_and_admin_only():
    content = repo_path("app/api/v1/ai_healing_stats.py").read_text(encoding="utf-8")

    assert 'APIRouter(prefix="/ai-healing"' in content
    assert '@router.get("/stats"' in content
    assert "@cached_json(" in content
    assert "ttl_seconds=300" in content
    assert "require_admin" in content
