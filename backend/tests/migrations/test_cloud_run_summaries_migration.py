"""Verify Alembic migration 20261026_0082 structure and down_revision chain."""

from pathlib import Path


def test_cloud_run_summaries_migration_contract() -> None:
    migration = Path(__file__).parents[2] / "alembic" / "versions" / "20261026_0082_add_cloud_run_summaries.py"
    content = migration.read_text(encoding="utf-8")

    assert 'revision: str = "20261026_0082"' in content
    assert 'down_revision: Union[str, None] = "20261015_0081"' in content
    assert '"cloud_run_summaries"' in content
    assert 'sa.UniqueConstraint("unique_key"' in content
    assert '"ix_cloud_run_summaries_unique_key"' in content
    assert '"ix_cloud_run_summaries_client_id"' in content
    assert '"ix_cloud_run_summaries_status"' in content
    assert 'op.drop_table("cloud_run_summaries")' in content
