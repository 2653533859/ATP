import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services import adb_service


def test_scan_devices_returns_none_when_adb_command_failed(monkeypatch):
    monkeypatch.setattr(adb_service, "_run_adb", lambda *args, **kwargs: None)

    scanned = adb_service.scan_devices()

    assert scanned is None
