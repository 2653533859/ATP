"""Cross-Protocol Data Propagation & Session-Level Context Bus Service (C3.2).

Provides:
1. Unified session-level state bus bridging HTTP, gRPC, and WebSocket executions.
2. Cross-protocol credential & context propagation (HTTP Auth -> gRPC Metadata & WebSocket Handshake).
3. Asynchronous WebSocket event payload extraction into shared session variables.
4. Universal dynamic template interpolation ({{variable}}) across all protocol payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any
import uuid

logger = logging.getLogger(__name__)

VAR_REGEX = re.compile(r"\{\{([a-zA-Z0-9_\.\-]+)\}\}")


@dataclass
class ProtocolEvent:
    event_id: str
    source_protocol: str  # "http" | "grpc" | "websocket"
    event_type: str
    payload: Any
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_protocol": self.source_protocol,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


@dataclass
class SessionBusContext:
    bus_id: str
    variables: dict[str, Any] = field(default_factory=dict)
    http_context: dict[str, Any] = field(
        default_factory=lambda: {
            "headers": {},
            "cookies": {},
            "base_url": "",
            "last_status": None,
        }
    )
    grpc_context: dict[str, Any] = field(
        default_factory=lambda: {
            "metadata": {},
            "channel_state": "idle",
        }
    )
    websocket_context: dict[str, Any] = field(
        default_factory=lambda: {
            "headers": {},
            "query_params": {},
            "active_channels": [],
            "buffered_messages": [],
        }
    )
    event_stream: list[ProtocolEvent] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def set_variable(self, key: str, value: Any) -> None:
        """Store a variable accessible across all protocols."""
        self.variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def record_event(
        self,
        source_protocol: str,
        event_type: str,
        payload: Any,
    ) -> ProtocolEvent:
        evt = ProtocolEvent(
            event_id=f"evt_{uuid.uuid4().hex[:10]}",
            source_protocol=source_protocol,
            event_type=event_type,
            payload=payload,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.event_stream.append(evt)
        return evt

    def propagate_http_to_grpc(self) -> dict[str, Any]:
        """Propagate HTTP Authorization/Token into gRPC metadata."""
        auth_header = self.http_context.get("headers", {}).get("Authorization")
        if not auth_header and "token" in self.variables:
            auth_header = f"Bearer {self.variables['token']}"

        if auth_header:
            self.grpc_context["metadata"]["authorization"] = str(auth_header)

        # Propagate request tracing IDs
        trace_id = self.http_context.get("headers", {}).get("x-trace-id") or self.variables.get("trace_id")
        if trace_id:
            self.grpc_context["metadata"]["x-trace-id"] = str(trace_id)

        self.record_event(
            source_protocol="http",
            event_type="propagate_to_grpc",
            payload=dict(self.grpc_context["metadata"]),
        )
        return dict(self.grpc_context["metadata"])

    def propagate_http_to_websocket(self) -> dict[str, Any]:
        """Propagate HTTP tokens into WebSocket handshake query and headers."""
        auth_header = self.http_context.get("headers", {}).get("Authorization")
        token = self.variables.get("token")

        if auth_header:
            self.websocket_context["headers"]["Authorization"] = str(auth_header)
        if token:
            self.websocket_context["query_params"]["token"] = str(token)

        self.record_event(
            source_protocol="http",
            event_type="propagate_to_websocket",
            payload={
                "headers": dict(self.websocket_context["headers"]),
                "query_params": dict(self.websocket_context["query_params"]),
            },
        )
        return {
            "headers": dict(self.websocket_context["headers"]),
            "query_params": dict(self.websocket_context["query_params"]),
        }

    def ingest_websocket_message(self, message: dict[str, Any] | str) -> dict[str, Any]:
        """Ingest incoming WebSocket frame and extract top-level keys into session variables."""
        msg_obj: dict[str, Any] = {}
        if isinstance(message, str):
            try:
                msg_obj = json.loads(message)
            except Exception:
                msg_obj = {"raw_text": message}
        elif isinstance(message, dict):
            msg_obj = message

        self.websocket_context["buffered_messages"].append(msg_obj)

        extracted_keys: list[str] = []
        if isinstance(msg_obj, dict):
            for k, v in msg_obj.items():
                if isinstance(v, (str, int, float, bool)):
                    self.set_variable(k, v)
                    extracted_keys.append(k)

        self.record_event(
            source_protocol="websocket",
            event_type="message_ingested",
            payload={"extracted_keys": extracted_keys},
        )
        return {"extracted_keys": extracted_keys, "current_variables": dict(self.variables)}

    def render_template(self, template_target: Any) -> Any:
        """Recursively interpolate {{variable}} in string, list, or dictionary."""
        if isinstance(template_target, str):

            def _repl(match: re.Match) -> str:
                var_key = match.group(1).strip()
                val = self.variables.get(var_key)
                if val is not None:
                    return str(val)
                return match.group(0)

            return VAR_REGEX.sub(_repl, template_target)

        if isinstance(template_target, list):
            return [self.render_template(item) for item in template_target]

        if isinstance(template_target, dict):
            rendered_dict: dict[str, Any] = {}
            for k, v in template_target.items():
                new_key = self.render_template(k)
                rendered_dict[new_key] = self.render_template(v)
            return rendered_dict

        return template_target

    def to_dict(self) -> dict[str, Any]:
        return {
            "bus_id": self.bus_id,
            "created_at": self.created_at,
            "variables": self.variables,
            "http_context": self.http_context,
            "grpc_context": self.grpc_context,
            "websocket_context": self.websocket_context,
            "total_events_count": len(self.event_stream),
            "recent_events": [e.to_dict() for e in self.event_stream[-10:]],
        }


# In-memory registry of active session buses
_BUS_REGISTRY: dict[str, SessionBusContext] = {}


def get_or_create_session_bus(bus_id: str | None = None) -> SessionBusContext:
    """Retrieve existing session bus or initialize a new one."""
    effective_id = bus_id.strip() if bus_id and bus_id.strip() else f"bus_{uuid.uuid4().hex[:12]}"
    if effective_id not in _BUS_REGISTRY:
        _BUS_REGISTRY[effective_id] = SessionBusContext(bus_id=effective_id)
    return _BUS_REGISTRY[effective_id]


def get_session_bus(bus_id: str) -> SessionBusContext | None:
    return _BUS_REGISTRY.get(bus_id)
