from pathlib import Path


def test_notification_config_table_is_covered_by_migrations():
    migration_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    migration_files = sorted(migration_dir.glob("*.py"))
    content = "\n".join(file.read_text(encoding="utf-8") for file in migration_files)

    assert "notification_configs" in content


def test_notification_config_fk_cascades_on_project_delete():
    migration_file = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260307_0003_add_notification_configs_table.py"
    )
    content = migration_file.read_text(encoding="utf-8")

    assert 'ondelete="CASCADE"' in content
