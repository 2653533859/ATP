from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class AICaseFunnelEvent:
    action: str
    detail: str | None
    created_at: datetime | None = None


def parse_event_detail(detail: str | None) -> dict:
    if not detail:
        return {}
    try:
        payload = json.loads(detail)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_funnel_stats(events: Iterable[AICaseFunnelEvent]) -> dict:
    generated_sessions = 0
    generated_drafts = 0
    saved_drafts = 0
    failed_generations = 0
    warning_count = 0
    latest_event_at = None

    for event in events:
        if event.created_at and (latest_event_at is None or event.created_at > latest_event_at):
            latest_event_at = event.created_at
        payload = parse_event_detail(event.detail)
        if event.action == "ai_case_generate":
            generated_sessions += 1
            generated_drafts += int(payload.get("draft_count") or 0)
            warning_count += int(payload.get("warning_count") or 0)
        elif event.action == "ai_case_generate_failed":
            failed_generations += 1
        elif event.action == "ai_case_draft_saved":
            saved_drafts += int(payload.get("saved_count") or 1)

    return {
        "generated_sessions": generated_sessions,
        "generated_drafts": generated_drafts,
        "saved_drafts": saved_drafts,
        "failed_generations": failed_generations,
        "warning_count": warning_count,
        "save_rate": round((saved_drafts / generated_drafts) * 100, 2) if generated_drafts else 0.0,
        "latest_event_at": latest_event_at.isoformat() if latest_event_at else None,
    }
