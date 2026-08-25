import asyncio

from app.models import load_all_models
from app.services.mobile_special_events import MobileRunEventRecorder, _json_object


load_all_models()


class _EventDB:
    def __init__(self):
        self.added = []
        self.commits = 0

    async def scalar(self, _query):
        return 0

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1


class _ConcurrentCommitDB(_EventDB):
    def __init__(self):
        super().__init__()
        self.active_commits = 0

    async def commit(self):
        if self.active_commits:
            raise AssertionError("commit calls overlapped")
        self.active_commits += 1
        try:
            await asyncio.sleep(0)
            self.commits += 1
        finally:
            self.active_commits -= 1


def test_event_recorder_assigns_sequence_and_bounds_payload():
    db = _EventDB()
    recorder = MobileRunEventRecorder(db, run_id=8, max_events=1)

    first = asyncio.run(
        recorder.record(
            event_type="action",
            parameters={"large": object()},
            result={"ok": True},
        )
    )
    second = asyncio.run(recorder.record(event_type="action"))

    assert first is db.added[0]
    assert first.sequence == 1
    assert first.parameters_json["large"].startswith("<object object at")
    assert second is None
    assert db.commits == 1


def test_event_recorder_serializes_concurrent_monkey_writes():
    db = _ConcurrentCommitDB()
    recorder = MobileRunEventRecorder(db, run_id=9, max_events=100)

    async def write_events(prefix: str):
        for index in range(40):
            await recorder.record(event_type=f"{prefix}_{index}", commit=False)
        await recorder.flush()

    async def run_concurrently():
        await asyncio.gather(write_events("monkey"), write_events("progress"))

    asyncio.run(run_concurrently())

    assert db.commits > 0
    assert len(db.added) == 80
    assert [event.sequence for event in db.added] == list(range(1, 81))


def test_json_object_normalizes_scalar_values():
    assert _json_object(None) == {}
    assert _json_object("ok") == {"value": "ok"}


def test_json_object_redacts_credentials_and_url_secrets():
    payload = _json_object(
        {
            "Authorization": "Bearer top-secret",
            "nested": {"password": "p@ss", "safe": "ok"},
            "url": "https://example.test/api?token=abc123&keep=yes",
        }
    )

    assert payload["Authorization"] == "[REDACTED]"
    assert payload["nested"]["password"] == "[REDACTED]"
    assert "abc123" not in payload["url"]
    assert "keep=yes" in payload["url"]
