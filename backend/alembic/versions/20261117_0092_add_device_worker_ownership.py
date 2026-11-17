"""add worker_id and worker_hostname ownership to devices

Revision ID: 20261117_0092
Revises: 20261113_0091
Create Date: 2026-11-17 17:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261117_0092"
down_revision: Union[str, None] = "20261113_0091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_single_serial_unique_constraints(bind: sa.Connection) -> None:
    inspector = sa.inspect(bind)
    for uc in inspector.get_unique_constraints("devices"):
        if list(uc.get("column_names") or []) == ["serial"] and uc.get("name"):
            with op.batch_alter_table("devices") as batch_op:
                batch_op.drop_constraint(uc["name"], type_="unique")
    for idx in inspector.get_indexes("devices"):
        if idx.get("unique") and list(idx.get("column_names") or []) == ["serial"] and idx.get("name"):
            op.drop_index(idx["name"], table_name="devices")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("devices")}

    if "worker_id" not in existing_columns:
        op.add_column("devices", sa.Column("worker_id", sa.String(length=128), nullable=True))
    if "worker_hostname" not in existing_columns:
        op.add_column("devices", sa.Column("worker_hostname", sa.String(length=128), nullable=True))

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("devices") if idx.get("name")}
    if "ix_devices_worker_id" not in existing_indexes:
        op.create_index("ix_devices_worker_id", "devices", ["worker_id"], unique=False)

    _drop_single_serial_unique_constraints(bind)

    refreshed_indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("devices") if idx.get("name")}
    if "ix_devices_serial" not in refreshed_indexes:
        op.create_index("ix_devices_serial", "devices", ["serial"], unique=False)

    existing_uqs = {uc["name"] for uc in sa.inspect(bind).get_unique_constraints("devices") if uc.get("name")}
    if "uq_devices_worker_id_serial" not in existing_uqs:
        with op.batch_alter_table("devices") as batch_op:
            batch_op.create_unique_constraint("uq_devices_worker_id_serial", ["worker_id", "serial"])

    if "uq_devices_unclaimed_serial" not in refreshed_indexes:
        op.create_index(
            "uq_devices_unclaimed_serial",
            "devices",
            ["serial"],
            unique=True,
            postgresql_where=sa.text("worker_id IS NULL"),
            sqlite_where=sa.text("worker_id IS NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text("SELECT serial FROM devices GROUP BY serial HAVING COUNT(*) > 1")
    ).fetchall()
    if duplicates:
        sample = ", ".join(str(row[0]) for row in duplicates[:5])
        raise RuntimeError(
            f"无法降级 20261117_0092：存在跨节点同 serial 设备 ({sample})，请先备份并按运行手册人工处理冲突"
        )

    inspector = sa.inspect(bind)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("devices") if idx.get("name")}
    if "uq_devices_unclaimed_serial" in existing_indexes:
        op.drop_index("uq_devices_unclaimed_serial", table_name="devices")

    existing_uqs = {uc["name"] for uc in inspector.get_unique_constraints("devices") if uc.get("name")}
    if "uq_devices_worker_id_serial" in existing_uqs:
        with op.batch_alter_table("devices") as batch_op:
            batch_op.drop_constraint("uq_devices_worker_id_serial", type_="unique")

    if "ix_devices_serial" in existing_indexes:
        op.drop_index("ix_devices_serial", table_name="devices")

    with op.batch_alter_table("devices") as batch_op:
        batch_op.create_unique_constraint("uq_devices_serial", ["serial"])

    if "ix_devices_worker_id" in existing_indexes:
        op.drop_index("ix_devices_worker_id", table_name="devices")

    existing_columns = {col["name"] for col in sa.inspect(bind).get_columns("devices")}
    if "worker_hostname" in existing_columns:
        op.drop_column("devices", "worker_hostname")
    if "worker_id" in existing_columns:
        op.drop_column("devices", "worker_id")
