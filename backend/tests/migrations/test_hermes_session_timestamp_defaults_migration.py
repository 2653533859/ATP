"""Regression coverage for Hermes session timestamp defaults."""

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260914_0074_fix_hermes_session_timestamp_defaults.py"
)


def test_hermes_timestamp_default_migration_extends_current_head_and_is_reversible():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260914_0074"' in content
    assert 'down_revision: Union[str, None] = "20260914_0073"' in content
    assert 'for column_name in ("created_at", "updated_at")' in content
    assert "server_default=sa.func.now()" in content
    assert "server_default=None" in content
