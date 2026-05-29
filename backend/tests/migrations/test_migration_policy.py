from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_bootstrap_db_uses_alembic_not_metadata_create_all():
    content = (ROOT / "backend" / "app" / "bootstrap_db.py").read_text(encoding="utf-8")

    assert "command.upgrade" in content
    assert "create_all" not in content
    assert "command.stamp" not in content


def test_backend_image_runs_alembic_upgrade_before_uvicorn():
    content = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "alembic upgrade head" in content
    assert "app.bootstrap_db" not in content


def test_compose_has_explicit_migration_gate():
    content = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "migrate:" in content
    assert "command: alembic upgrade head" in content
    assert "condition: service_completed_successfully" in content


def test_helm_chart_has_preinstall_migration_job():
    content = (
        ROOT / "deploy" / "helm" / "atp" / "templates" / "migrate-job.yaml"
    ).read_text(encoding="utf-8")

    assert "kind: Job" in content
    assert "helm.sh/hook" in content
    assert "pre-install,pre-upgrade" in content
    assert 'command: ["alembic", "upgrade", "head"]' in content
