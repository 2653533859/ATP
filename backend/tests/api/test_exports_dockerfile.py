from pathlib import Path


def test_backend_dockerfile_installs_playwright_chromium():
    content = Path("backend/Dockerfile").read_text(encoding="utf-8")

    assert "playwright install chromium --with-deps" in content
