import sys
import types
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules["app.core.minio_client"] = types.SimpleNamespace(
    download_file=lambda *args, **kwargs: None,
    upload_file=lambda *args, **kwargs: None,
    presigned_url=lambda *args, **kwargs: "http://example.com/image.png",
)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(publish_run_event=lambda *args, **kwargs: None)

from app.worker.executors import android_executor


def test_check_device_reachable_reports_offline(monkeypatch):
    class _Proc:
        returncode = 0
        stdout = "offline\n"
        stderr = ""

    monkeypatch.setattr(android_executor.subprocess, "run", lambda *args, **kwargs: _Proc())

    ok, message = android_executor._check_device_reachable("192.168.0.10:5555")

    assert ok is False
    assert "offline" in message


def test_check_device_reachable_reports_unauthorized(monkeypatch):
    class _Proc:
        returncode = 0
        stdout = "unauthorized\n"
        stderr = ""

    monkeypatch.setattr(android_executor.subprocess, "run", lambda *args, **kwargs: _Proc())

    ok, message = android_executor._check_device_reachable("ABC123")

    assert ok is False
    assert "未授权" in message
