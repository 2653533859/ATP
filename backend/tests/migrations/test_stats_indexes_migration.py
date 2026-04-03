import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_stats_index_migration_contains_expected_indexes():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260403_0015_add_stats_indexes.py"
    )
    content = migration_path.read_text(encoding="utf-8")

    assert 'op.create_index("ix_test_runs_status_created_at", "test_runs", ["status", "created_at"])' in content
    assert 'op.create_index("ix_test_runs_triggered_by_created_at", "test_runs", ["triggered_by", "created_at"])' in content
    assert 'op.create_index("ix_suite_runs_status_created_at", "suite_runs", ["status", "created_at"])' in content
    assert 'op.create_index("ix_plan_runs_status_created_at", "plan_runs", ["status", "created_at"])' in content


def test_stats_index_migration_drops_expected_indexes():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260403_0015_add_stats_indexes.py"
    )
    content = migration_path.read_text(encoding="utf-8")

    assert 'op.drop_index("ix_plan_runs_status_created_at", table_name="plan_runs")' in content
    assert 'op.drop_index("ix_suite_runs_status_created_at", table_name="suite_runs")' in content
    assert 'op.drop_index("ix_test_runs_triggered_by_created_at", table_name="test_runs")' in content
    assert 'op.drop_index("ix_test_runs_status_created_at", table_name="test_runs")' in content
