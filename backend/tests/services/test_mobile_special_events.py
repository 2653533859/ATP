import asyncio

from app.services.mobile_special_events import MobileRunEventRecorder, _json_object


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


def test_json_object_normalizes_scalar_values():
    assert _json_object(None) == {}
    assert _json_object("ok") == {"value": "ok"}
