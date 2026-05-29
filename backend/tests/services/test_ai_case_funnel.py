from __future__ import annotations

from datetime import datetime, timezone

from app.services.ai_case.funnel import AICaseFunnelEvent, build_funnel_stats, parse_event_detail


def test_parse_event_detail_tolerates_invalid_json():
    assert parse_event_detail(None) == {}
    assert parse_event_detail("not json") == {}
    assert parse_event_detail("[1, 2]") == {}


def test_build_funnel_stats_aggregates_generation_and_saved_drafts():
    now = datetime(2026, 5, 29, tzinfo=timezone.utc)
    stats = build_funnel_stats(
        [
            AICaseFunnelEvent(
                action="ai_case_generate",
                detail='{"draft_count": 4, "warning_count": 1}',
                created_at=now,
            ),
            AICaseFunnelEvent(
                action="ai_case_draft_saved",
                detail='{"saved_count": 3}',
                created_at=now,
            ),
            AICaseFunnelEvent(
                action="ai_case_generate_failed",
                detail='{"error_type": "network"}',
                created_at=now,
            ),
        ]
    )

    assert stats == {
        "generated_sessions": 1,
        "generated_drafts": 4,
        "saved_drafts": 3,
        "failed_generations": 1,
        "warning_count": 1,
        "save_rate": 75.0,
        "latest_event_at": "2026-05-29T00:00:00+00:00",
    }
