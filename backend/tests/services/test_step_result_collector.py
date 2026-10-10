import asyncio
import pytest
from app.services.step_result_collector import StepResultBatchCollector


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commit_count = 0

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commit_count += 1


class _FakeStepResult:
    def __init__(self, step_index: int, name: str):
        self.step_index = step_index
        self.name = name


def test_batch_collector_flushes_at_batch_size_threshold():
    db = _FakeDB()

    async def _run():
        async with StepResultBatchCollector(db, batch_size=3, flush_interval=10.0) as collector:
            await collector.add(_FakeStepResult(0, "Step 1"))
            assert db.commit_count == 0
            assert len(db.added) == 1

            await collector.add(_FakeStepResult(1, "Step 2"))
            assert db.commit_count == 0
            assert len(db.added) == 2

            await collector.add(_FakeStepResult(2, "Step 3"))
            assert db.commit_count == 1
            assert len(db.added) == 3

            await collector.add(_FakeStepResult(3, "Step 4"))
            assert db.commit_count == 1

    asyncio.run(_run())
    # Upon exit, remaining step 4 should be flushed
    assert db.commit_count == 2
    assert len(db.added) == 4


def test_batch_collector_flushes_on_explicit_flush():
    db = _FakeDB()

    async def _run():
        async with StepResultBatchCollector(db, batch_size=10, flush_interval=10.0) as collector:
            await collector.add(_FakeStepResult(0, "Step 1"), flush=True)
            assert db.commit_count == 1

            await collector.add(_FakeStepResult(1, "Step 2"))
            assert db.commit_count == 1

            await collector.flush()
            assert db.commit_count == 2

    asyncio.run(_run())
    assert db.commit_count == 2


def test_batch_collector_flushes_remaining_on_exception_exit():
    db = _FakeDB()

    async def _run():
        with pytest.raises(RuntimeError, match="step error"):
            async with StepResultBatchCollector(db, batch_size=10, flush_interval=10.0) as collector:
                await collector.add(_FakeStepResult(0, "Step 1"))
                await collector.add(_FakeStepResult(1, "Step 2"))
                assert db.commit_count == 0
                raise RuntimeError("step error")

    asyncio.run(_run())
    # Even though exception occurred, buffered steps must be committed
    assert db.commit_count == 1
    assert len(db.added) == 2
