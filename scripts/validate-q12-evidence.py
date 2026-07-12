#!/usr/bin/env python3
"""Validate Q12 external evidence documents before Q14-00 acceptance."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PLACEHOLDER_PATTERNS = (
    r"<[^>\n]+>",
    r"\bYYYY-MM-DD\b",
    r"\byes/no\b",
    r"\bpending / complete\b",
    r"\baccepted / accepted with follow-ups / not accepted\b",
    r"\bkeep / tighten / loosen\b",
    r"\benabled / deferred\b",
    r"\bdirect device TCP / shared host ADB server\b",
    r"\bcompleted / failed\b",
    r"\bmanual / schedule / API\b",
    r"\bP0/P1/P2\b",
)

SLO_REQUIRED_MARKERS = (
    "# SLO History Evidence",
    "## Preconditions",
    "## Scrape Health",
    "## API Availability",
    "## API P95 Latency",
    "## Run Success Rate",
    "## Breaches",
    "## Attached Artifacts",
    "## Final Calibration Decision",
    "API availability",
    "API P95 latency",
    "Run success rate",
    "Alert enablement:",
    "Release-blocking gate:",
)

ANDROID_REQUIRED_MARKERS = (
    "# Android Device Rehearsal Evidence",
    "## Device",
    "## Topology And Environment",
    "## Network Doctor",
    "## Data Plane",
    "## End-To-End Special Task",
    "## Result Verification",
    "## Anomalies",
    "## Pass Criteria",
    "ADB_SERVER_SOCKET",
    "ADB_SKIP_SERVER_RESTART",
    "ADB_SKIP_CONNECT",
    "adb -s",
    "dumpsys meminfo",
    "CSV report",
    "JSON report",
)

ACCEPTANCE_REQUIRED_MARKERS = (
    "# Q12 Acceptance Summary",
    "## Scope",
    "## Evidence Links",
    "## SLO Decision",
    "## Android Rehearsal Decision",
    "## Follow-Ups",
    "## Acceptance Statement",
    "API availability",
    "API P95 latency",
    "Run success rate",
    "Alert enablement:",
    "Release-blocking gate:",
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{path}: cannot read file: {exc}") from exc


def _require_filename(path: Path, pattern: str, label: str) -> list[str]:
    if re.fullmatch(pattern, path.name):
        return []
    return [f"{label}: filename must match {pattern!r}, got {path.name!r}"]


def _missing_markers(content: str, markers: tuple[str, ...], label: str) -> list[str]:
    lower_content = content.lower()
    return [f"{label}: missing marker {marker!r}" for marker in markers if marker.lower() not in lower_content]


def _unfilled_placeholders(content: str, label: str) -> list[str]:
    errors: list[str] = []
    for pattern in PLACEHOLDER_PATTERNS:
        match = re.search(pattern, content)
        if match:
            errors.append(f"{label}: unfilled placeholder {match.group(0)!r}")
    return errors


def _unchecked_boxes(content: str, label: str) -> list[str]:
    if "- [ ]" in content:
        return [f"{label}: contains unchecked checklist items"]
    return []


def _require_links(content: str, required_paths: tuple[str, ...], label: str) -> list[str]:
    return [f"{label}: missing link/path {path!r}" for path in required_paths if path not in content]


def validate_slo_history(path: Path) -> list[str]:
    content = _read(path)
    errors: list[str] = []
    errors += _require_filename(path, r"slo-history-\d{4}-\d{2}-\d{2}-\d{4}-\d{2}-\d{2}\.md", "SLO")
    errors += _missing_markers(content, SLO_REQUIRED_MARKERS, "SLO")
    errors += _unfilled_placeholders(content, "SLO")
    errors += _unchecked_boxes(content, "SLO")
    return errors


def validate_android_rehearsal(path: Path) -> list[str]:
    content = _read(path)
    errors: list[str] = []
    errors += _require_filename(path, r"android-device-rehearsal-\d{4}-\d{2}-\d{2}\.md", "Android")
    errors += _missing_markers(content, ANDROID_REQUIRED_MARKERS, "Android")
    errors += _unfilled_placeholders(content, "Android")
    errors += _unchecked_boxes(content, "Android")
    if "Final status | completed" not in content and "Final status | `completed`" not in content:
        errors.append("Android: final status must record completed")
    return errors


def validate_acceptance_summary(path: Path, slo_path: Path, android_path: Path) -> list[str]:
    content = _read(path)
    errors: list[str] = []
    errors += _require_filename(path, r"q12-acceptance-summary\.md", "Acceptance")
    errors += _missing_markers(content, ACCEPTANCE_REQUIRED_MARKERS, "Acceptance")
    errors += _unfilled_placeholders(content, "Acceptance")
    errors += _unchecked_boxes(content, "Acceptance")
    errors += _require_links(content, (f"docs/{slo_path.name}", f"docs/{android_path.name}"), "Acceptance")
    if "> Status: not accepted" in content:
        errors.append("Acceptance: status still says not accepted")
    return errors


def validate_all(slo_path: Path, android_path: Path, acceptance_path: Path) -> list[str]:
    return [
        *validate_slo_history(slo_path),
        *validate_android_rehearsal(android_path),
        *validate_acceptance_summary(acceptance_path, slo_path, android_path),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slo", required=True, type=Path, help="docs/slo-history-<start>-<end>.md")
    parser.add_argument("--android", required=True, type=Path, help="docs/android-device-rehearsal-<date>.md")
    parser.add_argument("--acceptance", required=True, type=Path, help="docs/q12-acceptance-summary.md")
    args = parser.parse_args(argv)

    errors = validate_all(args.slo, args.android, args.acceptance)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Q12 external evidence is structurally complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
