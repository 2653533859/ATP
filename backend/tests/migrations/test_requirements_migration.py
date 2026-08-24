"""Regression coverage for the requirements traceability migration."""

from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260824_0062_add_requirements.py"


def test_requirements_migration_is_attached_to_current_head():
    content = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260824_0062"' in content
    assert 'down_revision: Union[str, None] = "20260824_0061"' in content
    assert 'op.create_table(\n        "test_requirements"' in content
    assert 'op.create_table(\n        "requirement_case_links"' in content
    assert 'op.drop_table("requirement_case_links")' in content
    assert 'op.drop_table("test_requirements")' in content


def test_requirements_migration_names_traceability_constraints_and_indexes():
    content = MIGRATION.read_text(encoding="utf-8")

    for name in (
        "uq_test_requirements_project_code",
        "ix_test_requirements_project_status",
        "ix_test_requirements_project_updated",
        "uq_requirement_case_links_relation",
        "ix_requirement_case_links_requirement",
        "ix_requirement_case_links_case",
    ):
        assert name in content
