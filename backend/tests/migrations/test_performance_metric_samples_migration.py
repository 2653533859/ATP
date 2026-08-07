from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "20260529_0042_add_performance_metric_samples.py"


def test_performance_metric_samples_migration_follows_baseline_schedule_head():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260529_0042"' in content
    assert 'down_revision: Union[str, None] = "20260529_0041"' in content
    assert '"performance_metric_samples"' in content
    assert '"performance_runs.id"' in content
    assert '"ix_performance_metric_samples_run_captured"' in content


def test_performance_metric_samples_migration_is_reversible():
    content = MIGRATION.read_text(encoding="utf-8")

    assert "def downgrade()" in content
    assert 'op.drop_table("performance_metric_samples")' in content
