"""Pure helpers for performance-test schedule calculations."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def next_schedule_time(cron_expression: str, timezone_name: str, base: datetime | None = None) -> datetime:
    """Return the next UTC execution time for a cron expression."""
    from croniter import croniter  # type: ignore[import-untyped]

    tzinfo = ZoneInfo(timezone_name)
    local_base = (base or datetime.now(timezone.utc)).astimezone(tzinfo)
    return croniter(cron_expression, local_base).get_next(datetime).astimezone(timezone.utc)
