import socket

import pytest

from app.core.url_security import validate_public_http_url


def test_public_url_rejects_hostname_resolving_to_private_address(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 0))],
    )

    with pytest.raises(ValueError, match="内网"):
        validate_public_http_url("https://internal.example.test/path")


def test_public_url_accepts_globally_routable_address(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )

    assert validate_public_http_url("https://example.com/path") == "https://example.com/path"
