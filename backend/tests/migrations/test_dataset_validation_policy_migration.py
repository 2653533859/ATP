from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "20260529_0037_add_dataset_validation_policy.py"


def test_dataset_validation_policy_migration_chain_position():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260529_0037"' in content
    assert 'down_revision: Union[str, None] = "20260529_0036"' in content


def test_dataset_validation_policy_migration_adds_soft_default():
    content = MIGRATION.read_text(encoding="utf-8")

    assert '"validation_policy"' in content
    assert 'sa.String(length=16)' in content
    assert 'server_default="soft"' in content
    assert 'nullable=False' in content
