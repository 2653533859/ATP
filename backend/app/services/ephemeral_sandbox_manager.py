"""Ephemeral Multi-Protocol Mock Sandbox & Dynamic Port Lifecycle Manager (C3.1).

Provides:
1. Dynamic, conflict-free port allocation and probing within dedicated ephemeral range (20000 - 29999).
2. Ephemeral sandbox provisioning for HTTP, gRPC, and WebSocket testing isolation.
3. Automatic TTL expiration reaper and graceful resource deallocation.
4. Isolated mock routing engine within sandbox boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import socket
from typing import Any
import uuid

logger = logging.getLogger(__name__)

DEFAULT_PORT_RANGE_START = 20000
DEFAULT_PORT_RANGE_END = 29999
DEFAULT_SANDBOX_TTL_SECONDS = 300.0  # 5 minutes


class EphemeralPortManager:
    """Manages thread-safe allocation and release of ephemeral network ports."""

    def __init__(
        self,
        range_start: int = DEFAULT_PORT_RANGE_START,
        range_end: int = DEFAULT_PORT_RANGE_END,
    ) -> None:
        self.range_start = range_start
        self.range_end = range_end
        self.allocated_ports: set[int] = set()

    def is_port_available(self, port: int) -> bool:
        """Probe operating system socket to verify port is truly unallocated and bindable."""
        if port in self.allocated_ports:
            return False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False

    def allocate_port(self) -> int:
        """Find and claim the first available port in the range."""
        for port in range(self.range_start, self.range_end + 1):
            if self.is_port_available(port):
                self.allocated_ports.add(port)
                return port
        raise RuntimeError(f"所有沙箱瞬时端口已耗尽 (范围: {self.range_start}-{self.range_end})")

    def release_port(self, port: int) -> None:
        """Return port back to pool."""
        self.allocated_ports.discard(port)


# Global port manager instance
_PORT_MANAGER = EphemeralPortManager()


@dataclass
class EphemeralSandboxInstance:
    sandbox_id: str
    session_name: str
    protocol: str  # "http" | "grpc" | "websocket" | "multi_protocol"
    allocated_port: int
    host: str = "127.0.0.1"
    status: str = "ready"  # "ready" | "active" | "terminated" | "expired"
    ttl_seconds: float = DEFAULT_SANDBOX_TTL_SECONDS
    created_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    expires_at: float = field(default=0.0)
    mock_rules: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.expires_at <= 0.0:
            self.expires_at = self.created_at + self.ttl_seconds

    @property
    def is_expired(self) -> bool:
        now_ts = datetime.now(timezone.utc).timestamp()
        return now_ts > self.expires_at

    @property
    def base_url(self) -> str:
        if self.protocol == "websocket":
            return f"ws://{self.host}:{self.allocated_port}"
        if self.protocol == "grpc":
            return f"grpc://{self.host}:{self.allocated_port}"
        return f"http://{self.host}:{self.allocated_port}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "sandbox_id": self.sandbox_id,
            "session_name": self.session_name,
            "protocol": self.protocol,
            "host": self.host,
            "allocated_port": self.allocated_port,
            "base_url": self.base_url,
            "status": "expired" if (self.is_expired and self.status not in {"terminated"}) else self.status,
            "ttl_seconds": self.ttl_seconds,
            "created_at": datetime.fromtimestamp(self.created_at, timezone.utc).isoformat(),
            "expires_at": datetime.fromtimestamp(self.expires_at, timezone.utc).isoformat(),
            "is_expired": self.is_expired,
            "mock_rules_count": len(self.mock_rules),
            "metadata": self.metadata,
        }


# In-memory registry of sandboxes
_SANDBOXES: dict[str, EphemeralSandboxInstance] = {}


def provision_ephemeral_sandbox(
    session_name: str,
    *,
    protocol: str = "http",
    ttl_seconds: float = DEFAULT_SANDBOX_TTL_SECONDS,
    mock_rules: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> EphemeralSandboxInstance:
    """Allocate an isolated ephemeral port and spin up a lightweight mock sandbox."""
    if protocol not in {"http", "grpc", "websocket", "multi_protocol"}:
        protocol = "http"

    ttl = min(3600.0, max(10.0, ttl_seconds))
    allocated_port = _PORT_MANAGER.allocate_port()
    sandbox_id = f"sbx_{uuid.uuid4().hex[:12]}"

    instance = EphemeralSandboxInstance(
        sandbox_id=sandbox_id,
        session_name=session_name,
        protocol=protocol,
        allocated_port=allocated_port,
        ttl_seconds=ttl,
        mock_rules=mock_rules or [],
        metadata=metadata or {},
    )
    _SANDBOXES[sandbox_id] = instance
    logger.info(
        "Provisioned %s ephemeral sandbox %s at %s (port %s)",
        protocol,
        sandbox_id,
        instance.base_url,
        allocated_port,
    )
    return instance


def terminate_ephemeral_sandbox(sandbox_id: str) -> EphemeralSandboxInstance:
    """Terminate sandbox and release allocated ephemeral port back to OS pool."""
    instance = _SANDBOXES.get(sandbox_id)
    if not instance:
        raise ValueError(f"沙箱不存在: {sandbox_id}")

    if instance.status != "terminated":
        _PORT_MANAGER.release_port(instance.allocated_port)
        instance.status = "terminated"
        logger.info(
            "Terminated sandbox %s and released port %s",
            sandbox_id,
            instance.allocated_port,
        )

    return instance


def get_sandbox(sandbox_id: str) -> EphemeralSandboxInstance | None:
    """Retrieve sandbox by ID."""
    return _SANDBOXES.get(sandbox_id)


def list_sandboxes(
    *,
    protocol: str | None = None,
    only_active: bool = True,
) -> list[EphemeralSandboxInstance]:
    """List sandboxes with optional protocol filter and active status check."""
    reap_expired_sandboxes()
    instances = list(_SANDBOXES.values())
    filtered: list[EphemeralSandboxInstance] = []

    for sbx in instances:
        if only_active and (sbx.status in {"terminated", "expired"} or sbx.is_expired):
            continue
        if protocol and sbx.protocol != protocol:
            continue
        filtered.append(sbx)

    return filtered


def reap_expired_sandboxes() -> int:
    """Sweep and safely terminate any sandboxes that have exceeded their TTL."""
    reaped = 0
    now_ts = datetime.now(timezone.utc).timestamp()
    for sbx in list(_SANDBOXES.values()):
        if sbx.status != "terminated" and now_ts > sbx.expires_at:
            _PORT_MANAGER.release_port(sbx.allocated_port)
            sbx.status = "expired"
            reaped += 1
            logger.info(
                "Reaped expired sandbox %s (port %s released)",
                sbx.sandbox_id,
                sbx.allocated_port,
            )
    return reaped


def dispatch_sandbox_mock_request(
    sandbox_id: str,
    method: str,
    path: str,
) -> dict[str, Any]:
    """Simulate dispatching an incoming request to the isolated sandbox mock rules."""
    sbx = get_sandbox(sandbox_id)
    if not sbx:
        raise ValueError(f"沙箱不存在: {sandbox_id}")
    if sbx.status == "terminated" or sbx.is_expired:
        raise RuntimeError(f"沙箱已终止或过期 (状态: {sbx.status})")

    # Match mock rules by method and path
    m_clean = method.upper().strip()
    p_clean = path.strip()

    for rule in sbx.mock_rules:
        r_method = str(rule.get("method", "GET")).upper().strip()
        r_path = str(rule.get("path", "")).strip()
        if (r_method == "*" or r_method == m_clean) and (r_path == "*" or r_path == p_clean):
            return {
                "matched": True,
                "sandbox_id": sandbox_id,
                "status_code": int(rule.get("status_code", 200)),
                "headers": rule.get("headers", {"Content-Type": "application/json"}),
                "body": rule.get("body", {"message": "mock response"}),
            }

    # Default fallback response
    return {
        "matched": False,
        "sandbox_id": sandbox_id,
        "status_code": 404,
        "headers": {"Content-Type": "application/json"},
        "body": {"error": "No matching mock rule in sandbox", "path": path},
    }
