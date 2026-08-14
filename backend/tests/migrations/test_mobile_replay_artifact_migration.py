from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "20260814_0058_add_mobile_replay_artifact.py"


def test_mobile_replay_artifact_migration_is_latest_and_adds_enum_value():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260814_0058"' in content
    assert 'down_revision: Union[str, None] = "20260813_0057"' in content
    assert "ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'replay'" in content


def test_mobile_replay_artifact_downgrade_does_not_drop_shared_enum():
    content = MIGRATION.read_text(encoding="utf-8")

    assert "def downgrade()" in content
    assert "pass" in content
