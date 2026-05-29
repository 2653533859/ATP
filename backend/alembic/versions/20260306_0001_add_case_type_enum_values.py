"""add graphql/websocket/grpc to case type enum

Revision ID: 20260306_0001
Revises:
Create Date: 2026-03-06 23:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260306_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_CASE_TYPE_VALUES = ("graphql", "websocket", "grpc")
CANDIDATE_ENUM_NAMES = ("case_type", "casetype")


def _ts_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _create_base_tables() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=128), nullable=False),
        sa.Column("hashed_password", sa.String(length=256), nullable=False),
        sa.Column("role", sa.Enum("admin", "engineer", "tester", "viewer", name="userrole"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        *_ts_columns(),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        *_ts_columns(),
    )

    op.create_table(
        "modules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("modules.id"), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        *_ts_columns(),
    )

    op.create_table(
        "environments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        *_ts_columns(),
    )

    op.create_table(
        "env_variables",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("env_id", sa.Integer(), sa.ForeignKey("environments.id"), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("is_secret", sa.Boolean(), nullable=True),
        *_ts_columns(),
    )

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("serial", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("brand", sa.String(length=64), nullable=True),
        sa.Column("os_version", sa.String(length=32), nullable=True),
        sa.Column("sdk_version", sa.String(length=16), nullable=True),
        sa.Column("resolution", sa.String(length=32), nullable=True),
        sa.Column("status", sa.Enum("online", "offline", "busy", name="devicestatus"), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_columns(),
        sa.UniqueConstraint("serial"),
    )

    op.create_table(
        "apks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("package_name", sa.String(length=256), nullable=True),
        sa.Column("version_name", sa.String(length=64), nullable=True),
        sa.Column("version_code", sa.Integer(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("object_name", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        *_ts_columns(),
    )

    op.create_table(
        "test_cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("case_type", sa.Enum("api", "web", "android", name="casetype"), nullable=False),
        sa.Column("status", sa.Enum("active", "deprecated", name="casestatus"), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("modules.id"), nullable=False),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        *_ts_columns(),
    )

    op.create_table(
        "test_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("test_cases.id"), nullable=False),
        sa.Column("triggered_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "passed", "failed", "error", "skipped", name="runstatus"), nullable=True),
        sa.Column("environment", sa.String(length=64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        *_ts_columns(),
    )

    op.create_table(
        "step_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("test_runs.id"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("status", sa.Enum("pending", "running", "passed", "failed", "error", "skipped", name="runstatus"), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("request_data", sa.JSON(), nullable=True),
        sa.Column("response_data", sa.JSON(), nullable=True),
        sa.Column("screenshot_url", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        *_ts_columns(),
    )

    op.create_table(
        "test_suites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("status", sa.Enum("active", "archived", name="suitestatus"), nullable=True),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("case_ids", sa.JSON(), nullable=True),
        sa.Column("parameterization", sa.JSON(), nullable=True),
        *_ts_columns(),
    )

    op.create_table(
        "suite_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("suite_id", sa.Integer(), sa.ForeignKey("test_suites.id"), nullable=False),
        sa.Column("triggered_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "passed", "failed", "error", name="suiterunstatus"), nullable=True),
        sa.Column("environment", sa.String(length=64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("case_run_ids", sa.JSON(), nullable=True),
        *_ts_columns(),
    )

    op.create_table(
        "test_plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("status", sa.Enum("draft", "active", "archived", name="planstatus"), nullable=True),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("suite_ids", sa.JSON(), nullable=True),
        sa.Column("schedule_type", sa.Enum("manual", "cron", "webhook", name="scheduletype"), nullable=True),
        sa.Column("cron_expression", sa.String(length=128), nullable=True),
        sa.Column("webhook_secret", sa.String(length=64), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=True),
        sa.Column("env_id", sa.Integer(), sa.ForeignKey("environments.id"), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=False), nullable=True),
        *_ts_columns(),
    )

    op.create_table(
        "plan_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("test_plans.id"), nullable=False),
        sa.Column("triggered_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("trigger_type", sa.Enum("manual", "cron", "webhook", name="triggertype"), nullable=True),
        sa.Column("status", sa.Enum("pending", "running", "passed", "failed", "error", name="planrunstatus"), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("suite_run_ids", sa.JSON(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        *_ts_columns(),
    )


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _resolve_case_type_enum_name() -> str | None:
    bind = op.get_bind()
    column_enum_result = bind.execute(
        sa.text(
            """
            SELECT t.typname
            FROM pg_attribute AS a
            JOIN pg_class AS c ON c.oid = a.attrelid
            JOIN pg_type AS t ON t.oid = a.atttypid
            WHERE c.relname = 'test_cases'
              AND a.attname = 'case_type'
              AND a.attnum > 0
              AND NOT a.attisdropped
            LIMIT 1
            """
        )
    )
    column_enum_row = column_enum_result.first()
    if column_enum_row:
        return column_enum_row[0]

    result = bind.execute(
        sa.text(
            """
            SELECT t.typname
            FROM pg_type AS t
            WHERE t.typname = ANY(:enum_names)
            ORDER BY CASE WHEN t.typname = 'case_type' THEN 0 ELSE 1 END
            LIMIT 1
            """
        ),
        {"enum_names": list(CANDIDATE_ENUM_NAMES)},
    )
    row = result.first()
    return row[0] if row else None


def upgrade() -> None:
    _create_base_tables()

    if not _is_postgresql():
        return

    enum_name = _resolve_case_type_enum_name()
    if not enum_name:
        return

    quoted_enum_name = op.get_bind().dialect.identifier_preparer.quote(enum_name)
    for enum_value in NEW_CASE_TYPE_VALUES:
        with op.get_context().autocommit_block():
            op.execute(f"ALTER TYPE {quoted_enum_name} ADD VALUE IF NOT EXISTS '{enum_value}'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be safely removed in-place without rebuilding
    # dependent columns and data. Keep downgrade as a no-op.
    pass
