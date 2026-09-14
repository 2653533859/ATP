"""Regression coverage for the Hermes session optimistic-lock migration."""

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260914_0073_add_hermes_session_state_version.py"
)


def test_hermes_state_version_migration_extends_current_head_and_is_reversible():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260914_0073"' in content
    assert 'down_revision: Union[str, None] = "20260909_0072"' in content
    assert 'sa.Column("state_version", sa.Integer(), server_default="1", nullable=False)' in content
    assert 'op.drop_column("hermes_sessions", "state_version")' in content
