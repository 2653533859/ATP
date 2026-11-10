"""Bounded UIAutomator parsing, multimodal observation models and validation for Android Agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import re
from typing import Any
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

MAX_XML_BYTES = 1024 * 1024
MAX_NODES = 2000
MAX_DEPTH = 64
_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


class ObservationRejected(ValueError):
    """Stable error codes: capture_skew_too_high, unexpected_package, sensitive_page, etc."""


@dataclass(frozen=True)
class ScreenMetrics:
    width: int
    height: int
    rotation: int = 0  # 0, 90, 180, 270

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ObservationRejected("invalid_screen_size")
        if self.rotation not in (0, 90, 180, 270):
            raise ObservationRejected("invalid_screen_rotation")


@dataclass(frozen=True)
class UiNode:
    node_id: str
    parent_id: str | None
    resource_id: str
    text: str
    content_desc: str
    class_name: str
    bounds: tuple[int, int, int, int] | None
    enabled: bool
    clickable: bool
    redacted: bool
    text_truncated: bool = False


@dataclass(frozen=True)
class Observation:
    observation_id: str
    session_id: int
    captured_at: datetime
    package_name: str
    activity: str | None
    screen: ScreenMetrics
    screenshot_path: str
    screenshot_hash: str
    nodes: list[UiNode]
    capture_skew_ms: int = 0
    is_secure_window: bool = False


def validate_observation_skew(skew_ms: int, max_skew_ms: int = 2000) -> None:
    """Ensure the screenshot and UI tree capture timing did not drift across view updates."""
    if skew_ms < 0 or skew_ms > max_skew_ms:
        raise ObservationRejected("capture_skew_too_high")


def check_page_consistency(before_pkg: str, after_pkg: str, expected_pkg: str) -> None:
    """Ensure the target package remained foreground during the entire capture window."""
    if before_pkg != expected_pkg or after_pkg != expected_pkg:
        raise ObservationRejected("unexpected_package")


def compute_bytes_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_secure_window(screenshot_bytes: bytes) -> bool:
    """Detect potential FLAG_SECURE window (all black or empty payload)."""
    if not screenshot_bytes or len(screenshot_bytes) < 32:
        return True
    # Fast heuristic: if all non-header bytes are 0x00, screencap was blanked
    sample = screenshot_bytes[32:4096]
    return all(b == 0 for b in sample) if sample else True


def build_model_observation(obs: Observation, allowed_value_refs: list[str]) -> dict[str, Any]:
    """Serialize sanitized observation for LLM context, omitting raw internal references."""
    return {
        "observation_id": obs.observation_id,
        "package_name": obs.package_name,
        "activity": obs.activity,
        "screen": {
            "width": obs.screen.width,
            "height": obs.screen.height,
            "rotation": obs.screen.rotation,
        },
        "allowed_value_refs": sorted(allowed_value_refs),
        "is_secure_window": obs.is_secure_window,
        "nodes": [
            {k: v for k, v in asdict(node).items() if k not in {"parent_id", "redacted"}}
            for node in obs.nodes
            if not node.redacted
        ],
    }


def parse_dump_output(stdout: bytes, *, returncode: int, width: int, height: int) -> list[UiNode]:
    """UIAutomator can exit zero on an error; never treat that as a valid tree."""
    if returncode != 0:
        raise ObservationRejected("adb_capture_failed")
    if len(stdout) > MAX_XML_BYTES:
        raise ObservationRejected("ui_tree_too_large")
    if b"ERROR: could not get idle state." in stdout:
        raise ObservationRejected("ui_idle_timeout")
    if b"ERROR: null root node" in stdout:
        raise ObservationRejected("ui_root_unavailable")
    end = stdout.rfind(b"</hierarchy>")
    if end < 0:
        raise ObservationRejected("invalid_ui_tree")
    end += len(b"</hierarchy>")
    trailer = stdout[end:].strip()
    if trailer not in (b"", b"UI hierchary dumped to: /dev/tty", b"UI hierarchy dumped to: /dev/tty"):
        raise ObservationRejected("invalid_ui_dump_envelope")
    return parse_hierarchy(stdout[:end].strip(), width=width, height=height)


def parse_hierarchy(xml: bytes, *, width: int, height: int) -> list[UiNode]:
    """Parse exact XML; do not guess around truncated output or shell banners.

    Password nodes and descendants have text/description removed. This is not
    general PII redaction and must not be used as permission to send to a model.
    """
    if width <= 0 or height <= 0:
        raise ObservationRejected("invalid_screen_size")
    if len(xml) > MAX_XML_BYTES:
        raise ObservationRejected("ui_tree_too_large")
    try:
        root = ElementTree.fromstring(xml, forbid_dtd=True)
    except (ElementTree.ParseError, DefusedXmlException, RecursionError):
        raise ObservationRejected("invalid_ui_tree") from None
    if root.tag != "hierarchy":
        raise ObservationRejected("invalid_ui_tree_root")
    nodes: list[UiNode] = []
    stack: list[tuple[Element, str | None, int, bool]] = [(child, None, 1, False) for child in reversed(list(root))]
    while stack:
        element, parent, depth, inherited_sensitive = stack.pop()
        if depth > MAX_DEPTH or len(nodes) >= MAX_NODES:
            raise ObservationRejected("ui_tree_complexity_limit")
        if element.tag != "node":
            raise ObservationRejected("invalid_ui_node")
        node_id = f"n{len(nodes) + 1}"
        attrs = element.attrib
        sensitive = inherited_sensitive or attrs.get("password") == "true"
        bounds = None
        raw_bounds = attrs.get("bounds", "")
        match = _BOUNDS.fullmatch(raw_bounds) if len(raw_bounds) <= 64 else None
        if match:
            left, top, right, bottom = map(int, match.groups())
            if 0 <= left < right <= width and 0 <= top < bottom <= height:
                bounds = (left, top, right, bottom)
        nodes.append(
            UiNode(
                node_id=node_id,
                parent_id=parent,
                resource_id=attrs.get("resource-id", "")[:512],
                text="" if sensitive else attrs.get("text", "")[:512],
                content_desc="" if sensitive else attrs.get("content-desc", "")[:512],
                class_name=attrs.get("class", "")[:256],
                bounds=bounds,
                enabled=attrs.get("enabled") == "true",
                clickable=attrs.get("clickable") == "true",
                redacted=sensitive,
                text_truncated=len(attrs.get("text", "")) > 512,
            )
        )
        stack.extend((child, node_id, depth + 1, sensitive) for child in reversed(list(element)))
    return nodes
