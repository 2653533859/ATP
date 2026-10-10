"""Cooperative group stop checks shared by local and server workers.

The active child finishes before a group stops. Queued groups stop immediately.
"""

from sqlalchemy import text


def is_group_cancelled(kind: str, run_id: int, identity: str | None = None) -> bool:
    if kind not in {"suite", "plan"}:
        raise ValueError("unsupported execution group")
    from app.core.database import sync_engine

    with sync_engine.connect() as connection:
        table = "suite_runs" if kind == "suite" else "plan_runs"
        row = connection.execute(
            text(f"SELECT identity_token, cancel_requested_at, status FROM {table} WHERE id=:id"), {"id": run_id}
        ).first()
        if row is None or (identity is not None and row[0] != identity):
            return True
        if row[1] is not None or row[2] not in {"pending", "running"}:
            return True
        return False
