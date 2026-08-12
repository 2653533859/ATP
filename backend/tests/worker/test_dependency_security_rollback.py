def test_dependency_rollback_doc_covers_manifests_lockfiles_and_clean_installs(repo_file):
    content = repo_file("docs/dependency-security-rollback.md")

    for marker in (
        "backend/requirements.txt",
        "backend/requirements-dev.txt",
        "frontend/package.json",
        "frontend/package-lock.json",
        "npm --prefix frontend ci",
        "pip check",
        "Python 3.12",
        "Python 3.14",
        "clean environment",
    ):
        assert marker in content


def test_dependency_rollback_doc_covers_audits_images_and_schema_safety(repo_file):
    content = repo_file("docs/dependency-security-rollback.md")

    for marker in (
        "make security-pip-audit",
        "npm --prefix frontend audit --audit-level=high",
        "trivy image --severity HIGH,CRITICAL",
        "immutable image digest",
        "Gitleaks",
        "alembic downgrade",
        "make test-integration",
        "helm rollback",
        "Reintroduced Vulnerability Policy",
    ):
        assert marker in content


def test_frontend_image_install_is_lockfile_reproducible(repo_file):
    dockerfile = repo_file("frontend/Dockerfile")

    assert "COPY package*.json ./" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "RUN npm install" not in dockerfile


def test_python314_runtime_pins_use_binary_compatible_versions(repo_file):
    requirements = repo_file("backend/requirements.txt")

    assert "asyncpg==0.31.0" in requirements
    assert "psycopg2-binary==2.9.12" in requirements
    assert "pyyaml==6.0.3" in requirements
