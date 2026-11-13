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


def test_runtime_capabilities_exposes_android_agent_flag(monkeypatch):
    monkeypatch.setattr(
        runtime,
        "settings",
        SimpleNamespace(ATP_LOCAL_MODE=False, ANDROID_AGENT_ENABLED=True),
    )
    caps_enabled = runtime.get_runtime_capabilities()
    assert caps_enabled["android_agent"] is True
    assert "android_agent" in caps_enabled["features"]

    monkeypatch.setattr(
        runtime,
        "settings",
        SimpleNamespace(ATP_LOCAL_MODE=True, ANDROID_AGENT_ENABLED=False),
    )
    caps_disabled = runtime.get_runtime_capabilities()
    assert caps_disabled["android_agent"] is False
    assert "android_agent" not in caps_disabled["features"]
