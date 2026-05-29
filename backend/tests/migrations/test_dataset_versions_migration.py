from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "20260529_0038_add_dataset_versions.py"


def test_dataset_versions_migration_chain_position():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260529_0038"' in content
    assert 'down_revision: Union[str, None] = "20260529_0037"' in content


def test_dataset_versions_migration_creates_snapshot_table():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'op.create_table(\n        "test_dataset_versions"' in content
    assert '"dataset_id"' in content
    assert '"version"' in content
    assert '"rows"' in content
    assert '"schema_fields"' in content
    assert '"validation_policy"' in content
    assert '"uq_test_dataset_versions_dataset_version"' in content


def test_dataset_versions_migration_downgrade_drops_table():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'op.drop_index("ix_test_dataset_versions_dataset_id"' in content
    assert 'op.drop_table("test_dataset_versions")' in content
