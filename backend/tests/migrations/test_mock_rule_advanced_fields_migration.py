from pathlib import Path


def test_mock_rule_advanced_fields_migration_covers_match_conditions():
    migration_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    content = "\n".join(file.read_text(encoding="utf-8") for file in sorted(migration_dir.glob("*.py")))

    assert "match_conditions" in content
