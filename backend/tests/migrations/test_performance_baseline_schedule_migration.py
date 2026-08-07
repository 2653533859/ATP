from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "20260529_0041_add_performance_baseline_schedule.py"


def test_performance_baseline_schedule_migration_follows_current_head():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260529_0041"' in content
    assert 'down_revision: Union[str, None] = "20260529_0040"' in content
    assert 'op.add_column("performance_tests"' in content
    assert "baseline_run_id" in content
    assert "schedule_enabled" in content
    assert "schedule_environment_id" in content
    assert "fk_performance_tests_baseline_run_id_performance_runs" in content
    assert "fk_performance_tests_schedule_environment_id_environments" in content


def test_performance_baseline_schedule_migration_is_reversible():
    content = MIGRATION.read_text(encoding="utf-8")

    assert "def downgrade()" in content
    assert 'op.drop_column("performance_tests", "baseline_run_id")' in content
    assert 'op.drop_column("performance_tests", "next_run_at")' in content
