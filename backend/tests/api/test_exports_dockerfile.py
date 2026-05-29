import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_backend_dockerfile_installs_playwright_chromium():
    content = repo_path("backend/Dockerfile").read_text(encoding="utf-8")

    assert "playwright install chromium --with-deps" in content


def test_worker_dockerfile_uses_solo_pool_for_async_sqlalchemy_tasks():
    content = repo_path("backend/Dockerfile.worker").read_text(encoding="utf-8")

    assert "--pool=solo" in content


def test_worker_dockerfile_uses_multistage_runtime_without_build_deps():
    content = repo_path("backend/Dockerfile.worker").read_text(encoding="utf-8")

    assert "AS python-deps" in content
    assert "pip wheel" in content
    assert "COPY --from=python-deps /wheels /wheels" in content
    assert "postgresql-client" in content
    assert "android-tools-adb" in content
    runtime_section = content.split("FROM python:3.12-slim-bookworm", maxsplit=2)[-1]
    assert "gcc libpq-dev" not in runtime_section


def test_backend_dockerignore_excludes_local_virtualenvs():
    content = repo_path("backend/.dockerignore").read_text(encoding="utf-8")

    assert "venv/" in content
    assert ".venv/" in content
