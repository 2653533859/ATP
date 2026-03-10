"""standardize case management

Revision ID: 20260309_0009
Revises: 20260308_0008
Create Date: 2026-03-09
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260309_0009"
down_revision: Union[str, None] = "20260308_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize_code(name: str | None, fallback_prefix: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9]+", " ", name or "").strip()
    if compact:
        parts = [part[:4].upper() for part in compact.split()[:3]]
        merged = "".join(parts)
        if merged:
            return merged[:12]
    return fallback_prefix


def _ensure_unique_code(base_code: str, used_codes: set[str], fallback_prefix: str, limit: int = 32) -> str:
    candidate = (base_code or fallback_prefix)[:limit]
    if candidate not in used_codes:
        used_codes.add(candidate)
        return candidate

    index = 2
    while True:
        suffix = str(index)
        trimmed = candidate[: max(1, limit - len(suffix) - 1)]
        deduped = f"{trimmed}-{suffix}"
        if deduped not in used_codes:
            used_codes.add(deduped)
            return deduped
        index += 1


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _resolve_case_status_enum_name() -> str | None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT t.typname
            FROM pg_attribute AS a
            JOIN pg_class AS c ON c.oid = a.attrelid
            JOIN pg_type AS t ON t.oid = a.atttypid
            WHERE c.relname = 'test_cases'
              AND a.attname = 'status'
              AND a.attnum > 0
              AND NOT a.attisdropped
            LIMIT 1
            """
        )
    )
    row = result.first()
    return row[0] if row else None


def upgrade() -> None:
    if _is_postgresql():
        enum_name = _resolve_case_status_enum_name()
        if enum_name:
            quoted_enum_name = op.get_bind().dialect.identifier_preparer.quote(enum_name)
            with op.get_context().autocommit_block():
                op.execute(f"ALTER TYPE {quoted_enum_name} ADD VALUE IF NOT EXISTS 'draft'")

    op.add_column("projects", sa.Column("project_code", sa.String(length=32), nullable=True))
    op.create_unique_constraint("uq_projects_project_code", "projects", ["project_code"])

    op.add_column("modules", sa.Column("module_code", sa.String(length=32), nullable=True))

    op.add_column("test_cases", sa.Column("case_code", sa.String(length=64), nullable=True))
    op.add_column("test_cases", sa.Column("summary", sa.String(length=512), nullable=True))
    op.add_column("test_cases", sa.Column("preconditions", sa.JSON(), nullable=True, server_default=sa.text("'[]'")))
    op.add_column("test_cases", sa.Column("postconditions", sa.JSON(), nullable=True, server_default=sa.text("'[]'")))
    op.add_column("test_cases", sa.Column("priority", sa.String(length=8), nullable=True, server_default="P2"))
    op.add_column("test_cases", sa.Column("case_level", sa.String(length=32), nullable=True, server_default="regression"))
    op.add_column("test_cases", sa.Column("review_status", sa.String(length=32), nullable=True, server_default="approved"))
    op.add_column("test_cases", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.add_column("test_cases", sa.Column("automation_status", sa.String(length=32), nullable=True, server_default="auto"))
    op.add_column("test_cases", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("test_cases", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("test_cases", sa.Column("reviewed_by", sa.Integer(), nullable=True))
    op.add_column("test_cases", sa.Column("review_comment", sa.Text(), nullable=True))
    op.create_foreign_key("fk_test_cases_owner_id", "test_cases", "users", ["owner_id"], ["id"])
    op.create_foreign_key("fk_test_cases_reviewed_by", "test_cases", "users", ["reviewed_by"], ["id"])

    op.create_table(
        "case_steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("test_data", sa.Text(), nullable=True),
        sa.Column("expected_result", sa.Text(), nullable=True),
        sa.Column("is_key_step", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("case_id", "step_no", name="uq_case_steps_case_id_step_no"),
    )
    op.create_index("ix_case_steps_case_id_step_no", "case_steps", ["case_id", "step_no"])

    op.add_column(
        "case_snapshots",
        sa.Column("snapshot_data", sa.JSON(), nullable=True, server_default=sa.text("'{}'")),
    )

    bind = op.get_bind()

    project_rows = bind.execute(sa.text("SELECT id, name FROM projects ORDER BY id")).mappings().all()
    used_project_codes: set[str] = set()
    for row in project_rows:
        project_code = _ensure_unique_code(
            _normalize_code(row["name"], f"P{row['id']}"),
            used_project_codes,
            f"P{row['id']}",
        )
        bind.execute(
            sa.text("UPDATE projects SET project_code = :code WHERE id = :project_id"),
            {"code": project_code, "project_id": row["id"]},
        )

    module_rows = bind.execute(sa.text("SELECT id, name, project_id FROM modules ORDER BY project_id, id")).mappings().all()
    used_module_codes_by_project: dict[int, set[str]] = defaultdict(set)
    for row in module_rows:
        module_code = _ensure_unique_code(
            _normalize_code(row["name"], f"M{row['id']}"),
            used_module_codes_by_project[row["project_id"]],
            f"M{row['id']}",
        )
        bind.execute(
            sa.text("UPDATE modules SET module_code = :code WHERE id = :module_id"),
            {"code": module_code, "module_id": row["id"]},
        )

    case_rows = bind.execute(
        sa.text(
            """
            SELECT tc.id, tc.name, tc.description, tc.case_type, tc.status, tc.creator_id, tc.module_id,
                   p.project_code, m.module_code
            FROM test_cases tc
            JOIN modules m ON m.id = tc.module_id
            JOIN projects p ON p.id = m.project_id
            ORDER BY tc.module_id, tc.case_type, tc.id
            """
        )
    ).mappings().all()

    sequences: dict[tuple[int, str], int] = defaultdict(int)
    type_codes = {
        "api": "API",
        "web": "WEB",
        "android": "AND",
        "graphql": "GQL",
        "websocket": "WS",
        "grpc": "GRPC",
    }
    for row in case_rows:
        key = (row["module_id"], row["case_type"])
        sequences[key] += 1
        case_code = f"{row['project_code']}-{row['module_code']}-{type_codes.get(row['case_type'], 'CASE')}-{sequences[key]:04d}"
        summary = row["description"] or row["name"]
        bind.execute(
            sa.text(
                """
                UPDATE test_cases
                SET case_code = :case_code,
                    summary = :summary,
                    preconditions = :preconditions,
                    postconditions = :postconditions,
                    priority = :priority,
                    case_level = :case_level,
                    review_status = :review_status,
                    owner_id = :owner_id,
                    automation_status = :automation_status,
                    reviewed_at = created_at,
                    reviewed_by = creator_id,
                    review_comment = :review_comment
                WHERE id = :case_id
                """
            ),
            {
                "case_code": case_code,
                "summary": summary,
                "preconditions": [],
                "postconditions": [],
                "priority": "P2",
                "case_level": "regression",
                "review_status": "approved",
                "owner_id": row["creator_id"],
                "automation_status": "auto",
                "review_comment": "Migrated legacy case",
                "case_id": row["id"],
            },
        )

    bind.execute(sa.text("UPDATE case_snapshots SET snapshot_data = '{}'::jsonb"))

    op.alter_column("projects", "project_code", nullable=False)
    op.alter_column("modules", "module_code", nullable=False)
    op.alter_column("test_cases", "case_code", nullable=False)
    op.alter_column("test_cases", "summary", nullable=False)
    op.alter_column("test_cases", "preconditions", nullable=False)
    op.alter_column("test_cases", "postconditions", nullable=False)
    op.alter_column("test_cases", "priority", nullable=False)
    op.alter_column("test_cases", "case_level", nullable=False)
    op.alter_column("test_cases", "review_status", nullable=False)
    op.alter_column("test_cases", "automation_status", nullable=False)
    op.alter_column("case_snapshots", "snapshot_data", nullable=False)

    op.create_unique_constraint("uq_test_cases_case_code", "test_cases", ["case_code"])
    op.create_index("ix_test_cases_case_code", "test_cases", ["case_code"])
    op.create_index("ix_test_cases_review_status", "test_cases", ["review_status"])


def downgrade() -> None:
    op.drop_index("ix_test_cases_review_status", table_name="test_cases")
    op.drop_index("ix_test_cases_case_code", table_name="test_cases")
    op.drop_constraint("uq_test_cases_case_code", "test_cases", type_="unique")
    op.drop_column("case_snapshots", "snapshot_data")

    op.drop_index("ix_case_steps_case_id_step_no", table_name="case_steps")
    op.drop_table("case_steps")

    op.drop_constraint("fk_test_cases_reviewed_by", "test_cases", type_="foreignkey")
    op.drop_constraint("fk_test_cases_owner_id", "test_cases", type_="foreignkey")
    op.drop_column("test_cases", "review_comment")
    op.drop_column("test_cases", "reviewed_by")
    op.drop_column("test_cases", "reviewed_at")
    op.drop_column("test_cases", "submitted_at")
    op.drop_column("test_cases", "automation_status")
    op.drop_column("test_cases", "owner_id")
    op.drop_column("test_cases", "review_status")
    op.drop_column("test_cases", "case_level")
    op.drop_column("test_cases", "priority")
    op.drop_column("test_cases", "postconditions")
    op.drop_column("test_cases", "preconditions")
    op.drop_column("test_cases", "summary")
    op.drop_column("test_cases", "case_code")

    op.drop_column("modules", "module_code")
    op.drop_constraint("uq_projects_project_code", "projects", type_="unique")
    op.drop_column("projects", "project_code")
