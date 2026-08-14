"""Durable execution event journal for Android special-test runs."""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mobile_special import MobileRunEvent


MAX_PERSISTED_EVENTS_PER_RUN = 5000
EVENT_PAYLOAD_LIMIT = 12000
EVENT_FLUSH_BATCH_SIZE = 25


def _json_object(value: Any) -> dict:
    """Keep event payloads JSON-safe and bounded before storing them."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        value = {"value": value}
    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str)
        if len(encoded) > EVENT_PAYLOAD_LIMIT:
            encoded = json.dumps(
                {
                    "truncated": True,
                    "content": encoded[: EVENT_PAYLOAD_LIMIT - 80],
                },
                ensure_ascii=False,
            )
        result = json.loads(encoded)
        return result if isinstance(result, dict) else {"value": str(result)}
    except (TypeError, ValueError):
        return {"value": str(value)[:EVENT_PAYLOAD_LIMIT]}


class MobileRunEventRecorder:
    """Append-only per-run writer with a sequence and a safety cap."""

    def __init__(
        self,
        db: AsyncSession,
        run_id: int,
        *,
        max_events: int = MAX_PERSISTED_EVENTS_PER_RUN,
    ) -> None:
        self.db = db
        self.run_id = run_id
        self.max_events = max_events
        self.sequence = 0
        self.count = 0
        self.pending = 0
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        # Lightweight executor tests use a minimal DB double.  The real
        # AsyncSession always exposes scalar(); without it, start a fresh
        # journal rather than making the executor depend on test-only methods.
        if not callable(getattr(self.db, "scalar", None)):
            self._initialized = True
            return
        max_sequence = await self.db.scalar(
            select(func.max(MobileRunEvent.sequence)).where(MobileRunEvent.run_id == self.run_id)
        )
        count = await self.db.scalar(
            select(func.count(MobileRunEvent.id)).where(MobileRunEvent.run_id == self.run_id)
        )
        self.sequence = int(max_sequence or 0)
        self.count = int(count or 0)
        self._initialized = True

    async def record(
        self,
        *,
        event_type: str,
        phase: str | None = None,
        action: str | None = None,
        level: str | None = None,
        message: str | None = None,
        parameters: Any = None,
        result: Any = None,
        duration_ms: int | None = None,
        commit: bool = True,
    ) -> MobileRunEvent | None:
        await self.initialize()
        if self.count >= self.max_events:
            return None

        self.sequence += 1
        self.count += 1
        self.pending += 1
        event = MobileRunEvent(
            run_id=self.run_id,
            sequence=self.sequence,
            event_time=datetime.now(timezone.utc),
            event_type=event_type[:64],
            phase=phase[:64] if phase else None,
            action=action[:128] if action else None,
            level=level[:16] if level else None,
            message=message[:4000] if message else None,
            parameters_json=_json_object(parameters),
            result_json=_json_object(result),
            duration_ms=duration_ms,
        )
        self.db.add(event)
        if commit or self.pending >= EVENT_FLUSH_BATCH_SIZE:
            await self.flush()
        return event

    async def flush(self) -> None:
        if self.pending:
            await self.db.commit()
            self.pending = 0
