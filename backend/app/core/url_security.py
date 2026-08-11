"""服务端主动访问 URL 时使用的基础 SSRF 防护。"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def _assert_public_ip(value: str) -> None:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("不允许访问本机、内网、链路本地或保留地址")


def validate_http_url_syntax(value: str) -> str:
    """校验 HTTP URL 结构，并立即拒绝显式的非公网 IP/localhost。"""
    normalized = value.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("地址必须是 http 或 https URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("地址不能包含用户名或密码")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("不允许访问本机地址")
    _assert_public_ip(hostname)
    return normalized


def validate_public_http_url(value: str) -> str:
    """解析主机的全部地址，任一地址非公网时拒绝请求。"""
    normalized = validate_http_url_syntax(value)
    hostname = urlparse(normalized).hostname
    assert hostname is not None
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValueError("地址域名无法解析") from exc
    if not addresses:
        raise ValueError("地址域名无法解析")
    for address in addresses:
        _assert_public_ip(address)
    return normalized
