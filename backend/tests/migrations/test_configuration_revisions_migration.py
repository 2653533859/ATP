"""Regression coverage for the encrypted configuration revision migration."""

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260824_0064_add_configuration_revisions.py"
)


def test_configuration_revisions_migration_is_attached_to_knowledge_head():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260824_0064"' in content
    assert 'down_revision: Union[str, None] = "20260824_0063"' in content
    assert 'op.create_table(\n        "configuration_revisions"' in content
    assert 'op.drop_table("configuration_revisions")' in content


def test_configuration_revisions_migration_covers_scope_audit_and_lookup_indexes():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE")' in content
    assert 'sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL")' in content
    for name in (
        "ix_configuration_revisions_domain_resource_created",
        "ix_configuration_revisions_project_created",
        "ix_configuration_revisions_fingerprint",
    ):
        assert name in content
