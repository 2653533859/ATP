"""Template snapshot, impact analysis, and conflict-aware batch sync for API scenarios."""

from __future__ import annotations

import copy
from typing import Any, Literal

from app.models.case import TestCase
from app.services.spec_sync import case_request_fingerprint

SYNCABLE_FIELDS: tuple[str, ...] = (
    "method",
    "url",
    "headers",
    "params",
    "cookies",
    "body_type",
    "body",
    "assertions",
)

SyncChoice = Literal["keep_local", "use_latest"]


def extract_case_request_snapshot(case: TestCase) -> dict[str, Any]:
    """Build a normalized template snapshot from a single API TestCase."""
    cfg = case.config or {}
    steps = cfg.get("steps")
    first = steps[0] if isinstance(steps, list) and steps and isinstance(steps[0], dict) else {}

    def _pick(key: str, default: Any) -> Any:
        if key in first and first[key] is not None:
            return copy.deepcopy(first[key])
        if key in cfg and cfg[key] is not None:
            return copy.deepcopy(cfg[key])
        return copy.deepcopy(default)

    url = first.get("url") or cfg.get("url") or first.get("endpoint") or cfg.get("endpoint") or ""
    return {
        "method": str(_pick("method", "GET")).upper(),
        "url": str(url),
        "headers": _pick("headers", {}) if isinstance(_pick("headers", {}), dict) else {},
        "params": _pick("params", {}) if isinstance(_pick("params", {}), dict) else {},
        "cookies": _pick("cookies", {}) if isinstance(_pick("cookies", {}), dict) else {},
        "body_type": str(_pick("body_type", "none")),
        "body": _pick("body", ""),
        "assertions": _pick("assertions", []) if isinstance(_pick("assertions", []), list) else [],
    }


def extract_step_request_fields(step: dict[str, Any]) -> dict[str, Any]:
    """Normalize syncable fields from a scenario step."""
    return {
        "method": str(step.get("method") or "GET").upper(),
        "url": str(step.get("url") or ""),
        "headers": copy.deepcopy(step.get("headers") if isinstance(step.get("headers"), dict) else {}),
        "params": copy.deepcopy(step.get("params") if isinstance(step.get("params"), dict) else {}),
        "cookies": copy.deepcopy(step.get("cookies") if isinstance(step.get("cookies"), dict) else {}),
        "body_type": str(step.get("body_type") or "none"),
        "body": copy.deepcopy(step.get("body") if step.get("body") is not None else ""),
        "assertions": copy.deepcopy(step.get("assertions") if isinstance(step.get("assertions"), list) else []),
    }


def compute_overridden_fields(step: dict[str, Any], snapshot: dict[str, Any] | None) -> list[str]:
    if not isinstance(snapshot, dict):
        return []
    current = extract_step_request_fields(step)
    return [field for field in SYNCABLE_FIELDS if current.get(field) != snapshot.get(field)]


def compute_step_sync_diff(
    step: dict[str, Any],
    latest_snapshot: dict[str, Any],
    latest_fingerprint: str,
) -> dict[str, Any]:
    """Compare scenario step against its frozen sourceSnapshot and the latest source case.

    Shallow field-level comparison: ``body`` is compared as a whole value (never deep-merged)
    so keys explicitly removed in a local step override are never resurrected on sync.
    """
    current = extract_step_request_fields(step)
    base_snapshot = step.get("sourceSnapshot") if isinstance(step.get("sourceSnapshot"), dict) else None
    stored_fp = step.get("sourceCaseFingerprint")

    # Already aligned on fingerprint AND snapshot (or no upstream diff)
    if base_snapshot is not None:
        auto_updates: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        overridden_fields: list[str] = []

        for field in SYNCABLE_FIELDS:
            base_val = base_snapshot.get(field)
            local_val = current.get(field)
            latest_val = latest_snapshot.get(field)
            local_changed = local_val != base_val
            upstream_changed = latest_val != base_val

            if local_changed:
                overridden_fields.append(field)

            if not upstream_changed:
                continue
            if local_val == latest_val:
                continue
            if local_changed:
                conflicts.append(
                    {
                        "field": field,
                        "base": base_val,
                        "local": local_val,
                        "latest": latest_val,
                    }
                )
            else:
                auto_updates.append(
                    {
                        "field": field,
                        "base": base_val,
                        "latest": latest_val,
                    }
                )

        if conflicts:
            sync_status = "conflict"
        elif auto_updates or stored_fp != latest_fingerprint:
            sync_status = "stale_auto_syncable"
        else:
            sync_status = "up_to_date"

        return {
            "sync_status": sync_status,
            "auto_updates": auto_updates,
            "conflicts": conflicts,
            "overridden_fields": overridden_fields,
        }

    # Legacy step without sourceSnapshot: fall back to fingerprint comparison
    if stored_fp == latest_fingerprint:
        return {
            "sync_status": "up_to_date",
            "auto_updates": [],
            "conflicts": [],
            "overridden_fields": [],
        }

    # Conservatively treat differing fields as conflicts when no base snapshot exists
    conflicts = [
        {
            "field": field,
            "base": None,
            "local": current.get(field),
            "latest": latest_snapshot.get(field),
        }
        for field in SYNCABLE_FIELDS
        if current.get(field) != latest_snapshot.get(field)
    ]
    return {
        "sync_status": "conflict" if conflicts else "stale_auto_syncable",
        "auto_updates": [],
        "conflicts": conflicts,
        "overridden_fields": [c["field"] for c in conflicts],
    }


def apply_step_sync(
    step: dict[str, Any],
    latest_snapshot: dict[str, Any],
    latest_fingerprint: str,
    choices: dict[str, SyncChoice] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply template sync to a scenario step.

    Returns ``(updated_step, unresolved_conflicts)``. If any conflict field lacks an explicit
    choice in ``choices``, the step is returned untouched alongside the unresolved conflicts.
    """
    diff = compute_step_sync_diff(step, latest_snapshot, latest_fingerprint)
    choice_map = choices or {}
    unresolved = [c for c in diff["conflicts"] if choice_map.get(c["field"]) not in {"keep_local", "use_latest"}]
    if unresolved:
        return step, unresolved

    updated = copy.deepcopy(step)
    for item in diff["auto_updates"]:
        updated[item["field"]] = copy.deepcopy(item["latest"])
    for item in diff["conflicts"]:
        if choice_map.get(item["field"]) == "use_latest":
            updated[item["field"]] = copy.deepcopy(item["latest"])

    updated["sourceSnapshot"] = copy.deepcopy(latest_snapshot)
    updated["sourceCaseFingerprint"] = latest_fingerprint
    updated["overriddenFields"] = compute_overridden_fields(updated, latest_snapshot)
    return updated, []


def build_case_sync_metadata(case: TestCase) -> tuple[dict[str, Any], str]:
    """Return ``(latest_snapshot, latest_fingerprint)`` for a source API TestCase."""
    return extract_case_request_snapshot(case), case_request_fingerprint(case)
