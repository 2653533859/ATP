from tests._paths import repo_path


def test_backend_dockerfile_installs_playwright_chromium():
    content = repo_path("backend/Dockerfile").read_text(encoding="utf-8")

    assert "playwright install chromium --with-deps" in content


def test_worker_dockerfile_uses_solo_pool_for_async_sqlalchemy_tasks():
    content = repo_path("backend/Dockerfile.worker").read_text(encoding="utf-8")

    assert "--pool=solo" in content
