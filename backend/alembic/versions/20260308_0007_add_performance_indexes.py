"""add performance indexes

Revision ID: 20260308_0007
Revises: 20260308_0006
Create Date: 2026-03-08 18:00:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260308_0007"
down_revision: Union[str, None] = "20260308_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # test_runs: 按用例+状态+时间查询
    op.create_index("ix_test_runs_case_id_status", "test_runs", ["case_id", "status"])
    op.create_index("ix_test_runs_created_at", "test_runs", ["created_at"])

    # step_results: 按 run_id 查步骤
    op.create_index("ix_step_results_run_id", "step_results", ["run_id"])

    # test_cases: 按模块筛选
    op.create_index("ix_test_cases_module_id", "test_cases", ["module_id"])

    # env_variables: 按环境筛选
    op.create_index("ix_env_variables_env_id", "env_variables", ["env_id"])


def downgrade() -> None:
    op.drop_index("ix_env_variables_env_id", table_name="env_variables")
    op.drop_index("ix_test_cases_module_id", table_name="test_cases")
    op.drop_index("ix_step_results_run_id", table_name="step_results")
    op.drop_index("ix_test_runs_created_at", table_name="test_runs")
    op.drop_index("ix_test_runs_case_id_status", table_name="test_runs")
