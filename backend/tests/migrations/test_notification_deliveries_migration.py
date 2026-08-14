from pathlib import Path


def test_notification_deliveries_migration_keeps_project_and_config_scope():
    migration = Path(__file__).parents[2] / "alembic" / "versions" / "20260813_0057_add_notification_deliveries.py"
    content = migration.read_text(encoding="utf-8")

    assert 'revision: str = "20260813_0057"' in content
    assert 'down_revision: Union[str, None] = "20260813_0056"' in content
    assert '"notification_deliveries"' in content
    assert 'sa.ForeignKey("projects.id", ondelete="CASCADE")' in content
    assert 'sa.ForeignKey("notification_configs.id", ondelete="SET NULL")' in content
    assert 'sa.Column("attempts", sa.Integer(), nullable=False, server_default="1")' in content
    assert 'sa.Column("error_message", sa.String(length=1000), nullable=True)' in content
