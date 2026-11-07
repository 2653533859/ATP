"""Bounded UIAutomator parsing for M0; screenshots are not redacted here."""

from __future__ import annotations

from dataclasses import dataclass
import re
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

MAX_XML_BYTES = 1024 * 1024
MAX_NODES = 2000
MAX_DEPTH = 64
_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


class ObservationRejected(ValueError):
    pass


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
