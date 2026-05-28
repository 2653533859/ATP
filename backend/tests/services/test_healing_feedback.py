from datetime import datetime, timezone
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.bootstrap import load_all_models
from app.models.healing_feedback import HealingFeedbackAggregate
from app.services.healing_feedback import (
    FeedbackRow,
    aggregate_healing_feedback,
    build_error_fingerprint,
    summarize_feedback_rows,
    upsert_feedback_summaries,
)

load_all_models()


def test_build_error_fingerprint_is_stable_and_bounded():
    a = build_error_fingerprint(
        case_type="api",
        step_name="login",
        error_message="401",
        response_status_code=401,
    )
    b = build_error_fingerprint(
        case_type="api",
        step_name="login",
        error_message="401",
        response_status_code=401,
    )
    c = build_error_fingerprint(
        case_type="web",
        step_name="login",
        error_message="401",
        response_status_code=401,
    )

    assert a == b
    assert a != c
    assert len(a) == 32


def test_summarize_feedback_rows_groups_by_fingerprint_and_case_type():
    rows = [
        FeedbackRow("api", "login", "401", 401, "adopted"),
        FeedbackRow("api", "login", "401", 401, "adopted"),
        FeedbackRow("api", "login", "401", 401, "rejected"),
        FeedbackRow("api", "query", "timeout", None, "ignored"),
        FeedbackRow("web", "login", "401", 401, "rejected"),
    ]

    summaries = sorted(
        summarize_feedback_rows(rows),
        key=lambda item: item.case_type,
    )

    assert len(summaries) == 2
    assert summaries[0].case_type == "api"
    assert summaries[0].total_count == 3
    assert summaries[0].adopted_count == 2
    assert summaries[0].rejected_count == 1
    assert summaries[0].adopted_rate == 2 / 3
    assert summaries[1].case_type == "web"
    assert summaries[1].total_count == 1
    assert summaries[1].adopted_rate == 0


class _FakeResult:
    def __init__(self, aggregate):
        self.aggregate = aggregate

    def scalar_one_or_none(self):
        return self.aggregate


class _FakeDb:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.commits = 0

    async def execute(self, _stmt):
        return _FakeResult(self.existing)

    def add(self, obj):
        self.added.append(obj)
        self.existing = obj

    async def commit(self):
        self.commits += 1


def test_upsert_feedback_summaries_updates_existing():
    from app.services.healing_feedback import FeedbackSummary

    existing = HealingFeedbackAggregate(
        error_fingerprint="abc",
        case_type="api",
        total_count=1,
        adopted_count=0,
        rejected_count=1,
        adopted_rate=0,
        last_aggregated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    db = _FakeDb(existing)
    aggregated_at = datetime(2026, 5, 28, tzinfo=timezone.utc)

    changed = asyncio.run(
        upsert_feedback_summaries(
            db,
            [
                FeedbackSummary(
                    error_fingerprint="abc",
                    case_type="api",
                    total_count=4,
                    adopted_count=3,
                    rejected_count=1,
                    adopted_rate=0.75,
                )
            ],
            aggregated_at=aggregated_at,
        )
    )

    assert changed == 1
    assert db.added == []
    assert db.commits == 1
    assert existing.total_count == 4
    assert existing.adopted_rate == 0.75
    assert existing.last_aggregated_at == aggregated_at


def test_upsert_feedback_summaries_creates_missing():
    from app.services.healing_feedback import FeedbackSummary

    db = _FakeDb()
    aggregated_at = datetime(2026, 5, 28, tzinfo=timezone.utc)

    changed = asyncio.run(
        upsert_feedback_summaries(
            db,
            [
                FeedbackSummary(
                    error_fingerprint="new",
                    case_type="android",
                    total_count=2,
                    adopted_count=1,
                    rejected_count=1,
                    adopted_rate=0.5,
                )
            ],
            aggregated_at=aggregated_at,
        )
    )

    assert changed == 1
    assert len(db.added) == 1
    assert db.commits == 1
    assert db.added[0].error_fingerprint == "new"
    assert db.added[0].case_type == "android"


def test_aggregate_healing_feedback_empty_data(monkeypatch):
    from app.services import healing_feedback as service

    async def fake_collect(_db, *, since):
        return []

    async def fake_upsert(_db, summaries, *, aggregated_at):
        assert summaries == []
        return 0

    monkeypatch.setattr(service, "collect_feedback_rows", fake_collect)
    monkeypatch.setattr(service, "upsert_feedback_summaries", fake_upsert)

    result = asyncio.run(
        aggregate_healing_feedback(
            object(),
            now=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
    )

    assert result["input_count"] == 0
    assert result["aggregate_count"] == 0
    assert result["upserted"] == 0
