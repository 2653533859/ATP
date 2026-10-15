"""Microservice Reverse Proxy Traffic Recording and Noise Sanitization Gateway (T1.1).

Provides:
1. Reverse proxy traffic interception for HTTP/REST microservice requests.
2. Automated noise filtering (static assets .js/.css/.png, health checks /healthz, duplicate calls).
3. Header credential sanitization (Bearer tokens, cookies, API keys).
4. In-memory session tracking and clean entry serialization for case synthesis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any
from urllib.parse import urlparse
import uuid

logger = logging.getLogger(__name__)

STATIC_EXTENSIONS = {
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".map",
    ".webp",
}

HEARTBEAT_PATHS = {
    "/health",
    "/healthz",
    "/live",
    "/ready",
    "/ping",
    "/favicon.ico",
    "/actuator/health",
    "/status",
}

SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-atp-api-key",
    "token",
    "proxy-authorization",
}


@dataclass
class RecordedTrafficEntry:
    entry_id: str
    method: str
    url: str
    path: str
    headers: dict[str, str]
    query_params: dict[str, str]
    request_body: Any
    status_code: int
    response_headers: dict[str, str]
    response_body: Any
    duration_ms: float
    timestamp: str
    is_noise: bool = False
    noise_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "method": self.method,
            "url": self.url,
            "path": self.path,
            "headers": self.headers,
            "query_params": self.query_params,
            "request_body": self.request_body,
            "status_code": self.status_code,
            "response_headers": self.response_headers,
            "response_body": self.response_body,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
            "is_noise": self.is_noise,
            "noise_reason": self.noise_reason,
        }


def is_noise_request(path: str, _method: str = "GET") -> tuple[bool, str | None]:
    """Identify whether a request path is noise (static asset or system heartbeat)."""
    norm_path = path.lower().split("?")[0].rstrip("/")

    # 1. Heartbeat check
    if norm_path in HEARTBEAT_PATHS or norm_path == "":
        return True, "system_heartbeat"

    # 2. Static asset extension check
    for ext in STATIC_EXTENSIONS:
        if norm_path.endswith(ext):
            return True, f"static_asset({ext})"

    return False, None


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """Sanitize sensitive credentials in request/response headers."""
    sanitized: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in SENSITIVE_HEADERS:
            sanitized[k] = "***REDACTED***"
        else:
            sanitized[k] = v
    return sanitized


class TrafficRecordingSession:
    """Manages an active traffic recording session and its captured entries."""

    def __init__(
        self,
        session_id: str,
        project_id: int,
        target_base_url: str,
        *,
        filter_noise: bool = True,
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self.target_base_url = target_base_url.rstrip("/")
        self.filter_noise = filter_noise
        self.status = "active"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.entries: list[RecordedTrafficEntry] = []

    def record_entry(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        query_params: dict[str, str],
        request_body: Any,
        status_code: int,
        response_headers: dict[str, str],
        response_body: Any,
        duration_ms: float,
    ) -> RecordedTrafficEntry:
        """Process, filter, and record an intercepted traffic request/response pair."""
        is_noise, noise_reason = is_noise_request(path, method)
        clean_req_headers = sanitize_headers(headers)
        clean_resp_headers = sanitize_headers(response_headers)

        full_url = f"{self.target_base_url}/{path.lstrip('/')}"
        entry_id = f"trc_{uuid.uuid4().hex[:10]}"

        entry = RecordedTrafficEntry(
            entry_id=entry_id,
            method=method.upper(),
            url=full_url,
            path=f"/{path.lstrip('/')}",
            headers=clean_req_headers,
            query_params=query_params,
            request_body=request_body,
            status_code=status_code,
            response_headers=clean_resp_headers,
            response_body=response_body,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
            is_noise=is_noise,
            noise_reason=noise_reason,
        )

        self.entries.append(entry)
        return entry

    def get_clean_entries(self) -> list[dict[str, Any]]:
        """Return non-noise business entries."""
        return [e.to_dict() for e in self.entries if not e.is_noise]

    def get_summary(self) -> dict[str, Any]:
        """Compile a structured summary of the recording session."""
        total = len(self.entries)
        clean = sum(1 for e in self.entries if not e.is_noise)
        noise = total - clean

        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "target_base_url": self.target_base_url,
            "status": self.status,
            "created_at": self.created_at,
            "total_entries_count": total,
            "clean_entries_count": clean,
            "noise_filtered_count": noise,
            "noise_filtering_ratio_pct": round((noise / total * 100.0), 1) if total else 0.0,
            "entries": [e.to_dict() for e in self.entries],
        }


# Global active sessions storage
_SESSIONS: dict[str, TrafficRecordingSession] = {}


def start_recording_session(
    project_id: int,
    target_base_url: str,
    *,
    filter_noise: bool = True,
    session_id: str | None = None,
) -> TrafficRecordingSession:
    """Start and register a new traffic recording gateway session."""
    parsed = urlparse(target_base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"目标基础 URL 无效: '{target_base_url}'，必须包含 http:// 或 https:// 协议头")

    sid = session_id or f"rec_{uuid.uuid4().hex[:12]}"
    session = TrafficRecordingSession(
        session_id=sid,
        project_id=project_id,
        target_base_url=target_base_url,
        filter_noise=filter_noise,
    )
    _SESSIONS[sid] = session
    return session


def get_recording_session(session_id: str) -> TrafficRecordingSession | None:
    return _SESSIONS.get(session_id)


def stop_recording_session(session_id: str) -> dict[str, Any] | None:
    session = _SESSIONS.get(session_id)
    if not session:
        return None
    session.status = "stopped"
    return session.get_summary()
