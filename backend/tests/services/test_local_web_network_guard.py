"""Local Web runs may target loopback while server SSRF policy stays strict."""

from types import SimpleNamespace

import pytest

from app.services import web_network_guard


def test_local_profile_allows_loopback(monkeypatch) -> None:
    monkeypatch.setattr(web_network_guard, "settings", SimpleNamespace(ATP_LOCAL_MODE=True))
    assert web_network_guard.validate_browser_request_url("http://127.0.0.1:8001/health")
    assert web_network_guard.validate_browser_request_url("http://localhost:8001/health")


def test_server_profile_still_rejects_loopback(monkeypatch) -> None:
    monkeypatch.setattr(web_network_guard, "settings", SimpleNamespace(ATP_LOCAL_MODE=False))
    with pytest.raises(ValueError):
        web_network_guard.validate_browser_request_url("http://127.0.0.1:8001/health")
