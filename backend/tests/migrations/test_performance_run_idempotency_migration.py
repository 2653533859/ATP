from pathlib import Path


def test_performance_run_idempotency_migration_adds_scoped_unique_key():
    migration = Path(__file__).parents[2] / "alembic" / "versions" / "20260813_0056_add_performance_run_idempotency.py"
    content = migration.read_text(encoding="utf-8")

    assert 'revision = "20260813_0056"' in content
    assert 'down_revision = "20260812_0055"' in content
    assert 'sa.Column("idempotency_key", sa.String(length=128), nullable=True)' in content
    assert 'sa.Column("idempotency_fingerprint", sa.String(length=64), nullable=True)' in content
    assert '"uq_performance_runs_idempotency_key"' in content
    assert '"project_id", "performance_test_id", "idempotency_key"' in content
