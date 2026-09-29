"""Clients can identify the API mode before opening a workspace."""

from types import SimpleNamespace

from app.api.v1 import runtime


def test_runtime_identity_reports_both_profiles(monkeypatch):
    monkeypatch.setattr(runtime, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    assert runtime.get_runtime_identity().model_dump() == {
        "mode": "local",
        "database": "sqlite",
        "storage": "filesystem",
        "execution": "local",
    }
    monkeypatch.setattr(runtime, "settings", SimpleNamespace(ATP_LOCAL_MODE=False))
    assert runtime.get_runtime_identity().model_dump() == {
        "mode": "server",
        "database": "postgresql",
        "storage": "minio",
        "execution": "celery",
    }
