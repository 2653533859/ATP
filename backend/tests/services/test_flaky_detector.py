import asyncio
from app.models.case import RunStatus
from app.services import flaky_detector


class _FakeDB:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.execute_count = 0

    async def execute(self, _query):
        self.execute_count += 1
        return _FakeResult(self.rows)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Row:
    def __init__(self, case_id: int, status: object):
        self.case_id = case_id
        self.status = status


class _FakeCase:
    def __init__(self, case_id: int):
        self.id = case_id
        self.flaky_stats = None


def test_get_flaky_stats_empty_case_ids():
    db = _FakeDB()
    stats = asyncio.run(flaky_detector.get_flaky_stats_for_cases(db, []))
    assert stats == {}
    assert db.execute_count == 0


def test_get_flaky_stats_computes_and_caches():
    flaky_detector.clear_memory_cache()
    # 4 runs: 2 passed, 1 failed, 1 error -> meets MIN_RUNS=4 and flaky conditions
    rows = [
        _Row(101, RunStatus.passed),
        _Row(101, RunStatus.passed),
        _Row(101, RunStatus.failed),
        _Row(101, RunStatus.error),
    ]
    db = _FakeDB(rows)

    stats = asyncio.run(flaky_detector.get_flaky_stats_for_cases(db, [101]))
    assert db.execute_count == 1
    assert 101 in stats
    s101 = stats[101]
    assert s101["total_runs"] == 4
    assert s101["passed_runs"] == 2
    assert s101["failed_runs"] == 1
    assert s101["error_runs"] == 1
    assert s101["failure_rate"] == 50.0
    assert s101["is_flaky"] is True

    # Second call should hit memory cache without querying db
    stats2 = asyncio.run(flaky_detector.get_flaky_stats_for_cases(db, [101]))
    assert db.execute_count == 1  # No additional DB execute!
    assert stats2[101]["is_flaky"] is True

    # Invalidate cache
    asyncio.run(flaky_detector.invalidate_case_flaky_cache(101))

    # Third call queries db again
    stats3 = asyncio.run(flaky_detector.get_flaky_stats_for_cases(db, [101]))
    assert db.execute_count == 2
    assert stats3[101]["is_flaky"] is True


def test_attach_flaky_stats_to_cases():
    flaky_detector.clear_memory_cache()
    rows = [
        _Row(102, RunStatus.passed),
        _Row(102, RunStatus.passed),
        _Row(102, RunStatus.passed),
    ]
    db = _FakeDB(rows)
    cases = [_FakeCase(102)]

    asyncio.run(flaky_detector.attach_flaky_stats(db, cases))
    assert cases[0].flaky_stats is not None
    assert cases[0].flaky_stats["total_runs"] == 3
    assert cases[0].flaky_stats["is_flaky"] is False
