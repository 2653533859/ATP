from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "20260529_0044_add_performance_dataset_binding.py"


def test_performance_dataset_binding_migration_follows_performance_nodes_head():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260529_0044"' in content
    assert 'down_revision: Union[str, None] = "20260529_0043"' in content
    assert '"performance_tests"' in content
    assert '"performance_runs"' in content
    assert '"test_datasets"' in content
    assert '"dataset_version"' in content


def test_performance_dataset_binding_migration_is_reversible():
    content = MIGRATION.read_text(encoding="utf-8")

    assert "def downgrade()" in content
    assert 'op.drop_column("performance_runs", "dataset_version")' in content
    assert 'op.drop_column("performance_runs", "dataset_id")' in content
    assert 'op.drop_column("performance_tests", "dataset_id")' in content
