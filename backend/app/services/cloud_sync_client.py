"""Client service for synchronizing local Outbox records to the Cloud Result Center (D4)."""

from __future__ import annotations

import logging
from typing import Any
import httpx
from sqlalchemy import text

from app.core.config import settings
from app.services.cloud_result_sanitizer import sanitize_queued_summary
from app.services.sync_outbox import list_retryable_outbox_items, mark_outbox_failed, mark_outbox_synced

logger = logging.getLogger(__name__)


def sync_pending_outbox(
    sync_url: str | None = None,
    api_key: str | None = None,
    batch_size: int = 50,
    engine: Any = None,
    http_client: Any = None,
    force_retry: bool = False,
) -> dict[str, Any]:
    """Sweep local pending Outbox records and push them to the configured Cloud server."""
    target_url = (sync_url or settings.CLOUD_SYNC_URL or "").strip().rstrip("/")
    if not target_url:
        return {"status": "disabled", "synced": 0, "failed": 0, "message": "CLOUD_SYNC_URL not configured"}

    endpoint = f"{target_url}/api/v1/cloud-sync/runs"
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }
    key = api_key or settings.CLOUD_SYNC_API_KEY
    if key:
        headers["X-ATP-Api-Key"] = key

    if engine is None:
        from app.core.database import sync_engine

        engine = sync_engine

    with engine.begin() as conn:
        items = list_retryable_outbox_items(conn, limit=batch_size, force_retry=force_retry)

    if not items:
        return {"status": "ok", "synced": 0, "failed": 0, "processed": 0, "message": "No pending items"}

    synced_count = 0
    failed_count = 0

    client_ctx = None
    if http_client is not None:
        client = http_client
    else:
        client_ctx = httpx.Client(timeout=10.0)
        client = client_ctx.__enter__()

    try:
        for item in items:
            ukey = item["unique_key"]
            payload = sanitize_queued_summary(item.get("payload") or {})
            try:
                # Claim only records that are still in the state selected above.
                with engine.begin() as conn:
                    claimed = conn.execute(
                        text(
                            "UPDATE local_sync_outbox SET status = 'syncing', updated_at = CURRENT_TIMESTAMP "
                            "WHERE unique_key = :key AND status = :previous AND updated_at = :updated_at"
                        ),
                        {"key": ukey, "previous": item["status"], "updated_at": item["updated_at"]},
                    )
                if not claimed.rowcount:
                    continue

                response = client.post(endpoint, json=payload, headers=headers)
                if response.status_code == 200 and response.json().get("acknowledged"):
                    with engine.begin() as conn:
                        mark_outbox_synced(conn, ukey)
                    synced_count += 1
                else:
                    err_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    with engine.begin() as conn:
                        mark_outbox_failed(conn, ukey, err_msg)
                    failed_count += 1
            except Exception as exc:
                err_msg = f"Network error: {str(exc)[:200]}"
                with engine.begin() as conn:
                    mark_outbox_failed(conn, ukey, err_msg)
                failed_count += 1
    finally:
        if client_ctx is not None:
            client_ctx.__exit__(None, None, None)

    return {
        "status": "ok",
        "synced": synced_count,
        "failed": failed_count,
        "processed": len(items),
    }
