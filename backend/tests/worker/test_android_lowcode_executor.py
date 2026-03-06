import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.minio_client"] = types.SimpleNamespace(
    ensure_bucket=lambda: None,
    upload_bytes=lambda *args, **kwargs: None,
    upload_file=lambda *args, **kwargs: None,
    presigned_url=lambda *args, **kwargs: "",
    delete_file=lambda *args, **kwargs: None,
)
sys.modules.setdefault(
    "app.core.redis_client",
    types.SimpleNamespace(publish_run_event=lambda *args, **kwargs: None),
)

from app.worker.executors import android_lowcode_executor as executor


def test_input_clear_sends_repeated_delete_keyevents(monkeypatch):
    calls: list[tuple] = []

    def fake_adb_cmd(serial: str, *args: str, timeout: int = 15):
        calls.append((serial, args, timeout))
        return True, ""

    monkeypatch.setattr(executor, "_adb_cmd", fake_adb_cmd)

    result = executor._execute_step_sync(
        "serial-1",
        "input",
        {"text": "hello", "clear": True},
    )

    assert result["success"] is True

    delete_calls = [
        args for serial, args, _ in calls
        if args[:4] == ("shell", "input", "keyevent", "67")
    ]
    assert len(delete_calls) == 50
    assert all(args[3] == "67" for args in delete_calls)
    assert all("--longpress" not in args for _, args, _ in calls)
