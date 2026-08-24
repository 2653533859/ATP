"""Make project-owned resources safe to delete with their project."""

from typing import Sequence, Union

from alembic import op


revision: str = "20260824_0065"
down_revision: Union[str, None] = "20260824_0064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PROJECT_FOREIGN_KEYS = (
    ("apks", "apks_project_id_fkey", "CASCADE"),
    ("environments", "environments_project_id_fkey", "CASCADE"),
    ("modules", "modules_project_id_fkey", "CASCADE"),
    ("test_plans", "test_plans_project_id_fkey", "CASCADE"),
    ("test_suites", "test_suites_project_id_fkey", "CASCADE"),
)


def upgrade() -> None:
    for table_name, constraint_name, ondelete in _PROJECT_FOREIGN_KEYS:
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            table_name,
            "projects",
            ["project_id"],
            ["id"],
            ondelete=ondelete,
        )

    op.drop_constraint("env_variables_env_id_fkey", "env_variables", type_="foreignkey")
    op.create_foreign_key(
        "env_variables_env_id_fkey",
        "env_variables",
        "environments",
        ["env_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("test_plans_env_id_fkey", "test_plans", type_="foreignkey")
    op.create_foreign_key(
        "test_plans_env_id_fkey",
        "test_plans",
        "environments",
        ["env_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("test_plans_env_id_fkey", "test_plans", type_="foreignkey")
    op.create_foreign_key(
        "test_plans_env_id_fkey",
        "test_plans",
        "environments",
        ["env_id"],
        ["id"],
    )
    op.drop_constraint("env_variables_env_id_fkey", "env_variables", type_="foreignkey")
    op.create_foreign_key(
        "env_variables_env_id_fkey",
        "env_variables",
        "environments",
        ["env_id"],
        ["id"],
    )

    for table_name, constraint_name, _ondelete in reversed(_PROJECT_FOREIGN_KEYS):
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            table_name,
            "projects",
            ["project_id"],
            ["id"],
        )
