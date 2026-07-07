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
    content = (ROOT / "deploy" / "helm" / "atp" / "templates" / "migrate-job.yaml").read_text(encoding="utf-8")

    assert "kind: Job" in content
    assert "helm.sh/hook" in content
    assert "pre-install,pre-upgrade" in content
    assert 'command: ["alembic", "upgrade", "head"]' in content


def test_migration_guidelines_document_enum_index_constraint_rules():
    content = (ROOT / "docs" / "alembic-migration-guidelines.md").read_text(encoding="utf-8")

    assert "Enum Changes" in content
    assert "Index Changes" in content
    assert "Constraint Changes" in content
    assert "checkfirst=True" in content
    assert "op.drop_index" in content
    assert "op.drop_constraint" in content
    assert "backend/tests/migrations/" in content


def test_migration_template_covers_reversible_enum_index_and_constraints():
    content = (ROOT / "backend" / "alembic" / "templates" / "migration_template.py").read_text(encoding="utf-8")

    assert "sa.Enum(" in content
    assert ".create(op.get_bind(), checkfirst=True)" in content
    assert ".drop(op.get_bind(), checkfirst=True)" in content
    assert "op.create_index(" in content
    assert "op.drop_index(" in content
    assert "sa.ForeignKeyConstraint" in content
    assert "sa.UniqueConstraint" in content


def test_migration_runbook_links_authoring_guidelines():
    content = (ROOT / "docs" / "migrations.md").read_text(encoding="utf-8")

    assert "alembic-migration-guidelines.md" in content
    assert "migration_template.py" in content
