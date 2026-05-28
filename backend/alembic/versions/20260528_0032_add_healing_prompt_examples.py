"""Q6 P2.2: add healing prompt examples

Revision ID: 20260528_0032
Revises: 20260528_0031
Create Date: 2026-05-28 22:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260528_0032"
down_revision: Union[str, None] = "20260528_0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "healing_prompt_examples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("error_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("case_type", sa.String(length=32), nullable=False),
        sa.Column("step_context_json", sa.JSON(), nullable=False),
        sa.Column("suggestion_text", sa.Text(), nullable=False),
        sa.Column("source_step_result_id", sa.Integer(), nullable=True),
        sa.Column("marked_high_quality", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("marked_by", sa.Integer(), nullable=True),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["marked_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_step_result_id"], ["step_results.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_healing_prompt_examples_error_fingerprint", "healing_prompt_examples", ["error_fingerprint"])
    op.create_index("ix_healing_prompt_examples_case_type", "healing_prompt_examples", ["case_type"])
    op.create_index("ix_healing_prompt_examples_source_step_result_id", "healing_prompt_examples", ["source_step_result_id"])
    op.create_index(
        "ix_healing_prompt_examples_quality_lookup",
        "healing_prompt_examples",
        ["error_fingerprint", "case_type", "marked_high_quality", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_healing_prompt_examples_quality_lookup", table_name="healing_prompt_examples")
    op.drop_index("ix_healing_prompt_examples_source_step_result_id", table_name="healing_prompt_examples")
    op.drop_index("ix_healing_prompt_examples_case_type", table_name="healing_prompt_examples")
    op.drop_index("ix_healing_prompt_examples_error_fingerprint", table_name="healing_prompt_examples")
    op.drop_table("healing_prompt_examples")
