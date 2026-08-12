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


def test_dataset_minio_storage_migration_adds_references_and_counts():
    migration = ROOT / "alembic" / "versions" / "20260812_0055_add_dataset_minio_storage.py"
    content = migration.read_text(encoding="utf-8")

    assert 'revision = "20260812_0055"' in content
    assert 'down_revision = "20260811_0054"' in content
    assert 'sa.Column("storage_mode"' in content
    assert 'sa.Column("object_name"' in content
    assert 'sa.Column("row_count"' in content
    assert "json_array_length(rows)" in content
