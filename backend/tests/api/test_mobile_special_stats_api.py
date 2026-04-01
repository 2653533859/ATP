"""Tests for mobile special statistics and export schemas."""
import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_engineer=lambda: None,
)

from app.models.mobile_special import TaskType


class TestStatisticsSchemas:
    def test_mobile_special_overview_schema_fields(self):
        from app.schemas.mobile_special import MobileSpecialOverviewItem

        item = MobileSpecialOverviewItem(
            total_runs=10,
            completed_runs=8,
            failed_runs=2,
            running_runs=0,
            pass_rate=80.0,
            avg_duration_ms=3000.5,
            total_incidents=3,
            recent_runs_7d=5,
        )
        assert item.total_runs == 10
        assert item.completed_runs == 8
        assert item.failed_runs == 2
        assert item.pass_rate == 80.0
        assert item.avg_duration_ms == 3000.5

    def test_mobile_special_trend_item_fields(self):
        from app.schemas.mobile_special import MobileSpecialTrendItem

        item = MobileSpecialTrendItem(
            date="2026-03-30",
            total=15,
            completed=12,
            failed=3,
            pass_rate=80.0,
        )
        assert item.date == "2026-03-30"
        assert item.total == 15
        assert item.completed == 12
        assert item.failed == 3

    def test_mobile_special_task_stat_item_fields(self):
        from app.schemas.mobile_special import MobileSpecialTaskStatItem

        item = MobileSpecialTaskStatItem(
            task_id=1,
            task_name="Performance Test",
            task_type=TaskType.performance,
            total_runs=20,
            completed_runs=18,
            failed_runs=2,
            pass_rate=90.0,
            last_run_at=None,
        )
        assert item.task_id == 1
        assert item.task_name == "Performance Test"
        assert item.task_type == TaskType.performance
        assert item.total_runs == 20
        assert item.completed_runs == 18
        assert item.failed_runs == 2
        assert item.pass_rate == 90.0


class TestStatisticsQueries:
    def test_trend_endpoint_builds_query_with_sqlalchemy_2_case_syntax(self):
        from app.api.v1 import mobile_special

        class FakeResult:
            def all(self):
                return []

        class FakeDB:
            async def execute(self, stmt):
                return FakeResult()

        result = asyncio.run(
            mobile_special.get_mobile_special_trend(
                project_id=None,
                days=14,
                db=FakeDB(),
                _=None,
            )
        )

        assert result == []

    def test_task_stats_endpoint_builds_query_with_sqlalchemy_2_case_syntax(self):
        from app.api.v1 import mobile_special

        class FakeResult:
            def all(self):
                return []

        class FakeDB:
            async def execute(self, stmt):
                return FakeResult()

        result = asyncio.run(
            mobile_special.get_task_statistics(
                project_id=None,
                days=14,
                limit=10,
                db=FakeDB(),
                _=None,
            )
        )

        assert result == []
