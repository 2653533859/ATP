"""Regression coverage for the knowledge hub migration."""

from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260824_0063_add_knowledge_entries.py"


def test_knowledge_migration_is_attached_to_requirements_head():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260824_0063"' in content
    assert 'down_revision: Union[str, None] = "20260824_0062"' in content
    assert 'op.create_table(\n        "knowledge_entries"' in content
    assert 'op.drop_table("knowledge_entries")' in content


def test_knowledge_migration_has_project_scope_and_cascade_indexes():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE")' in content
    for name in (
        "ix_knowledge_entries_project_status",
        "ix_knowledge_entries_project_source",
        "ix_knowledge_entries_project_updated",
    ):
        assert name in content
