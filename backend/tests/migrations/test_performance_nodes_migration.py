from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "20260529_0043_add_performance_nodes.py"


def test_performance_nodes_migration_follows_metric_samples_head():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260529_0043"' in content
    assert 'down_revision: Union[str, None] = "20260529_0042"' in content
    assert '"performance_nodes"' in content
    assert '"performance_tests"' in content
    assert '"performance_runs"' in content
    assert '"uq_performance_nodes_node_id"' in content


def test_performance_nodes_migration_is_reversible():
    content = MIGRATION.read_text(encoding="utf-8")

    assert "def downgrade()" in content
    assert 'op.drop_table("performance_nodes")' in content
    assert 'op.drop_column("performance_tests", "schedule_node_id")' in content
    assert 'op.drop_column("performance_runs", "performance_node_id")' in content
