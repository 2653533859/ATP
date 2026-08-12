import asyncio
from types import SimpleNamespace

import pytest

from app.services.web_network_guard import (
    guard_browser_request,
    sanitize_network_url,
    validate_browser_request_url,
)


class _Route:
    def __init__(self, url: str, resource_type: str = "document"):
        self.request = SimpleNamespace(url=url, resource_type=resource_type)
        self.aborted_with = None
        self.continued = False

    async def abort(self, error_code):
        self.aborted_with = error_code

    async def continue_(self):
        self.continued = True


def test_browser_request_allows_local_browser_schemes():
    assert validate_browser_request_url("about:blank") == "about:blank"
    assert validate_browser_request_url("data:text/plain,hello") == "data:text/plain,hello"
    assert validate_browser_request_url("blob:https://example.com/id") == "blob:https://example.com/id"


@pytest.mark.parametrize("url", ["file:///tmp/page.html", "ftp://example.com/file", "/relative/path"])
def test_browser_request_rejects_non_network_or_relative_urls(url):
    with pytest.raises(ValueError, match="协议"):
        validate_browser_request_url(url)


def test_browser_request_validates_websocket_with_http_policy(monkeypatch):
    checked = []
    monkeypatch.setattr(
        "app.services.web_network_guard.validate_public_http_url",
        lambda url: checked.append(url) or url,
    )

    assert validate_browser_request_url("wss://api.example.com/socket?token=secret") == (
        "wss://api.example.com/socket?token=secret"
    )
    assert checked == ["https://api.example.com/socket?token=secret"]


def test_guard_aborts_private_request_and_records_redacted_evidence():
    route = _Route("http://127.0.0.1:8000/metrics?token=secret", "xhr")
    blocked = []

    allowed = asyncio.run(guard_browser_request(route, blocked))

    assert allowed is False
    assert route.aborted_with == "blockedbyclient"
    assert route.continued is False
    assert blocked == [
        {
            "url": "http://127.0.0.1:8000/metrics?token=%2A%2A%2A",
            "resource_type": "xhr",
            "reason": "不允许访问本机、内网、链路本地或保留地址",
        }
    ]


def test_guard_continues_public_request_and_redacts_sensitive_values(monkeypatch):
    monkeypatch.setattr(
        "app.services.web_network_guard.validate_public_http_url",
        lambda url: url,
    )
    route = _Route("https://example.com/api?api_key=secret&scene=smoke")
    blocked = []

    allowed = asyncio.run(guard_browser_request(route, blocked))

    assert allowed is True
    assert route.continued is True
    assert blocked == []
    assert sanitize_network_url(route.request.url) == "https://example.com/api?api_key=%2A%2A%2A&scene=smoke"


def test_guard_rechecks_dns_for_each_request(monkeypatch):
    from app.core import url_security

    addresses = iter(["93.184.216.34", "192.168.1.20"])
    monkeypatch.setattr(
        url_security.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, (next(addresses), 0))],
    )
    first_route = _Route("https://example.com")
    second_route = _Route("https://example.com/app.js", "script")
    first_blocked = []
    second_blocked = []

    assert asyncio.run(guard_browser_request(first_route, first_blocked)) is True
    assert asyncio.run(guard_browser_request(second_route, second_blocked)) is False
    assert first_route.continued is True
    assert second_route.aborted_with == "blockedbyclient"
