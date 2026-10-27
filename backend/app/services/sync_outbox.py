"""Persistent outbox queue for local desktop result synchronization (D2)."""

from __future__ import annotations

import json
import logging
from typing import Any
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.schemas.cloud_sync import CloudRunSummary
from app.services.cloud_result_sanitizer import build_cloud_run_summary

logger = logging.getLogger(__name__)


def record_run_in_outbox(connection: Connection, task_name: str, run_id: int) -> str | None:
    """Build a sanitized summary and persist it in local_sync_outbox atomically.

    Deduplication: Uses unique_key (client_id:run_type:run_id).
    If a record already exists and is not synced, update the payload.
    If already synced, keep it synced without duplicate insertion.
    """
    try:
        summary: CloudRunSummary = build_cloud_run_summary(connection, task_name, run_id)
        payload_json = summary.model_dump_json()

        connection.execute(
            text(
                """
                INSERT INTO local_sync_outbox (client_id, run_type, run_id, unique_key, payload_json, status, created_at, updated_at)
                VALUES (:client_id, :run_type, :run_id, :unique_key, :payload_json, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(unique_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status != 'synced'
                """
            ),
            {
                "client_id": summary.client_id,
                "run_type": summary.run_type,
                "run_id": summary.run_id,
                "unique_key": summary.unique_key,
                "payload_json": payload_json,
            },
        )
        return summary.unique_key
    except Exception as exc:
        logger.warning("Failed to record run %s (%s) in local outbox: %s", run_id, task_name, exc, exc_info=True)
        return None


def list_outbox_items(connection: Connection, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Query queued outbox records."""
    where_clause = "WHERE status = :status" if status else ""
    params: dict[str, Any] = {"limit": limit}
    if status:
        params["status"] = status

    res = connection.execute(
        text(
            f"""
            SELECT id, client_id, run_type, run_id, unique_key, payload_json, status,
                   attempts, last_error, created_at, updated_at, synced_at
            FROM local_sync_outbox
            {where_clause}
            ORDER BY id ASC
            LIMIT :limit
            """
        ),
        params,
    )
    rows = list(res.mappings().all()) if res is not None else []

    results: list[dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        try:
            item["payload"] = json.loads(item.get("payload_json") or "{}")
        except Exception:
            item["payload"] = {}
        results.append(item)
    return results


def list_retryable_outbox_items(
    connection: Connection, limit: int = 50, *, force_retry: bool = False
) -> list[dict[str, Any]]:
    """Return pending, due failed, and abandoned in-flight records."""
    failed_condition = (
        "status = 'failed'"
        if force_retry
        else (
            "status = 'failed' AND datetime(updated_at) <= datetime('now', "
            "'-' || CASE WHEN attempts < 2 THEN 5 WHEN attempts < 3 THEN 15 "
            "WHEN attempts < 4 THEN 45 ELSE 300 END || ' seconds')"
        )
    )
    res = connection.execute(
        text(
            "SELECT id, unique_key, payload_json, status, updated_at FROM local_sync_outbox "
            f"WHERE status = 'pending' OR ({failed_condition}) "
            "OR (status = 'syncing' AND datetime(updated_at) <= datetime('now', '-60 seconds')) "
            "ORDER BY id ASC LIMIT :limit"
        ),
        {"limit": limit},
    )
    rows = list(res.mappings().all()) if res is not None else []
    return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]


def mark_outbox_synced(connection: Connection, unique_key: str) -> bool:
    """Mark an outbox record as successfully confirmed by the cloud result center."""
    res = connection.execute(
        text(
            """
            UPDATE local_sync_outbox
            SET status = 'synced', synced_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE unique_key = :unique_key
            """
        ),
        {"unique_key": unique_key},
    )
    rowcount = getattr(res, "rowcount", 0) if res is not None else 0
    return bool(rowcount and rowcount > 0)


def mark_outbox_failed(connection: Connection, unique_key: str, error_message: str) -> bool:
    """Mark an outbox record attempt as failed with backoff error recording."""
    res = connection.execute(
        text(
            """
            UPDATE local_sync_outbox
            SET status = 'failed',
                attempts = attempts + 1,
                last_error = :error,
                updated_at = CURRENT_TIMESTAMP
            WHERE unique_key = :unique_key
            """
        ),
        {"unique_key": unique_key, "error": error_message[:2048]},
    )
    rowcount = getattr(res, "rowcount", 0) if res is not None else 0
    return bool(rowcount and rowcount > 0)


def reset_failed_outbox(connection: Connection) -> int:
    """Reset failed items back to pending state for automatic or manual retry."""
    res = connection.execute(
        text(
            """
            UPDATE local_sync_outbox
            SET status = 'pending', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'failed'
            """
        )
    )
    return int(getattr(res, "rowcount", 0) or 0) if res is not None else 0


def get_outbox_stats(connection: Connection) -> dict[str, int]:
    """Return counts of outbox items by status."""
    res = connection.execute(
        text(
            """
            SELECT status, count(*) as count
            FROM local_sync_outbox
            GROUP BY status
            """
        )
    )
    rows = list(res.mappings().all()) if res is not None else []
    stats = {"pending": 0, "syncing": 0, "synced": 0, "failed": 0, "total": 0}
    for r in rows:
        st = str(r["status"])
        cnt = int(r["count"])
        if st in stats:
            stats[st] = cnt
        stats["total"] += cnt
    return stats
