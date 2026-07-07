"""convert bug_trackers.tracker_type to native enum

Revision ID: 20260529_0040
Revises: 20260529_0039
Create Date: 2026-05-29 19:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260529_0040"
down_revision: Union[str, None] = "20260529_0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


tracker_type_enum = postgresql.ENUM(
    "jira",
    "zentao",
    "github",
    "gitlab",
    name="trackertype",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        tracker_type_enum.create(bind, checkfirst=True)
        op.alter_column(
            "bug_trackers",
            "tracker_type",
            existing_type=sa.String(length=16),
            type_=tracker_type_enum,
            postgresql_using="tracker_type::trackertype",
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "bug_trackers",
            "tracker_type",
            existing_type=tracker_type_enum,
            type_=sa.String(length=16),
            postgresql_using="tracker_type::text",
            existing_nullable=False,
        )
        tracker_type_enum.drop(bind, checkfirst=True)
