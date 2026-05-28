from pathlib import Path


def repo_path(path: str) -> Path:
    return Path(__file__).resolve().parents[2] / path


def test_dashboard_alerts_router_registered():
    content = repo_path("app/api/v1/router.py").read_text(encoding="utf-8")
    assert "dashboard_alerts" in content
    assert "router.include_router(dashboard_alerts.router)" in content
