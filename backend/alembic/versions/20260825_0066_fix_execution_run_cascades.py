"""Make project deletion cascade through modules, cases and execution history."""

from typing import Sequence, Union

from alembic import op


revision: str = "20260825_0066"
down_revision: Union[str, None] = "20260824_0065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FOREIGN_KEYS = (
    ("modules", "modules_parent_id_fkey", "modules", "id", "CASCADE"),
    ("test_cases", "test_cases_module_id_fkey", "modules", "id", "CASCADE"),
    ("test_cases", "test_cases_dataset_id_fkey", "test_datasets", "id", "SET NULL"),
    ("test_runs", "test_runs_case_id_fkey", "test_cases", "id", "CASCADE"),
    ("test_runs", "test_runs_parent_run_id_fkey", "test_runs", "id", "CASCADE"),
    ("step_results", "step_results_run_id_fkey", "test_runs", "id", "CASCADE"),
    ("suite_runs", "suite_runs_suite_id_fkey", "test_suites", "id", "CASCADE"),
    ("plan_runs", "plan_runs_plan_id_fkey", "test_plans", "id", "CASCADE"),
)


def upgrade() -> None:
    for table_name, constraint_name, referred_table, referred_column, ondelete in _FOREIGN_KEYS:
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            table_name,
            referred_table,
            [constraint_name.removeprefix(f"{table_name}_").removesuffix("_fkey")],
            [referred_column],
            ondelete=ondelete,
        )


def downgrade() -> None:
    for table_name, constraint_name, referred_table, referred_column, _ondelete in reversed(_FOREIGN_KEYS):
        column_name = constraint_name.removeprefix(f"{table_name}_").removesuffix("_fkey")
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            table_name,
            referred_table,
            [column_name],
            [referred_column],
        )
