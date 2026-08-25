"""Validate the machine-readable release gate evidence index.

The index is a rolling, redacted status document.  It deliberately does not
store a release SHA because the SHA is only known at the time a candidate is
validated.  Pass ``--candidate-sha`` in the release job to bind that run to a
specific commit without mutating the tracked index.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "docs" / "release-evidence-index-2026-08-25.json"
ALLOWED_GATE_STATUSES = {"passed", "pending", "blocked"}
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:api[_-]?key|authorization|password|private[_-]?key|secret|token)",
    re.IGNORECASE,
)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _resolve_repo_file(raw_path: Any, field: str, repo_root: Path, errors: list[str]) -> Path | None:
    if not _is_non_empty_string(raw_path):
        errors.append(f"{field} must be a non-empty relative path")
        return None
    candidate = Path(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        errors.append(f"{field} must stay inside the repository: {raw_path!r}")
        return None
    resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        errors.append(f"{field} resolves outside the repository: {raw_path!r}")
        return None
    if not resolved.is_file():
        errors.append(f"{field} does not exist: {raw_path!r}")
        return None
    return resolved


def _validate_repo_path(raw_path: Any, field: str, repo_root: Path, errors: list[str]) -> None:
    _resolve_repo_file(raw_path, field, repo_root, errors)


def _scan_sensitive_keys(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if SENSITIVE_KEY_PATTERN.search(key_text):
                errors.append(f"manifest contains a sensitive field name at {path}.{key_text}")
            _scan_sensitive_keys(child, f"{path}.{key_text}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_sensitive_keys(child, f"{path}[{index}]", errors)


def validate_manifest(manifest: Any, repo_root: Path = REPO_ROOT) -> list[str]:
    """Return all validation errors instead of stopping at the first one."""

    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest root must be a JSON object"]

    _scan_sensitive_keys(manifest, "$", errors)
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not _is_non_empty_string(manifest.get("generated_at")):
        errors.append("generated_at must be a non-empty string")
    if not _is_non_empty_string(manifest.get("scope")):
        errors.append("scope must be a non-empty string")

    release = manifest.get("release")
    if not isinstance(release, dict):
        errors.append("release must be an object")
        release = {}
    release_status = release.get("status")
    if release_status not in {"ready", "blocked"}:
        errors.append("release.status must be ready or blocked")
    if not isinstance(release.get("eligible"), bool):
        errors.append("release.eligible must be boolean")
    candidate_sha = release.get("candidate_sha")
    if candidate_sha is not None and (not isinstance(candidate_sha, str) or not SHA_PATTERN.fullmatch(candidate_sha)):
        errors.append("release.candidate_sha must be null or a 40-character lowercase commit SHA")

    gates = manifest.get("gates")
    if not isinstance(gates, list) or not gates:
        errors.append("gates must be a non-empty array")
        gates = []

    gate_ids: list[str] = []
    non_passed_ids: list[str] = []
    for index, gate in enumerate(gates):
        prefix = f"gates[{index}]"
        if not isinstance(gate, dict):
            errors.append(f"{prefix} must be an object")
            continue
        gate_id = gate.get("id")
        status = gate.get("status")
        if not _is_non_empty_string(gate_id):
            errors.append(f"{prefix}.id must be a non-empty string")
        else:
            gate_ids.append(gate_id)
            if gate_id in gate_ids[:-1]:
                errors.append(f"duplicate gate id: {gate_id}")
        if status not in ALLOWED_GATE_STATUSES:
            errors.append(f"{prefix}.status must be one of {sorted(ALLOWED_GATE_STATUSES)}")
        elif status != "passed" and _is_non_empty_string(gate_id):
            non_passed_ids.append(gate_id)

        if not _is_non_empty_string(gate.get("owner")):
            errors.append(f"{prefix}.owner must be a non-empty string")
        recheck_command = gate.get("recheck_command")
        if not _is_non_empty_string(recheck_command) or "\n" in recheck_command or "\r" in recheck_command:
            errors.append(f"{prefix}.recheck_command must be one non-empty line")

        evidence = gate.get("evidence")
        if not isinstance(evidence, list):
            errors.append(f"{prefix}.evidence must be an array")
        else:
            for evidence_index, evidence_path in enumerate(evidence):
                _validate_repo_path(evidence_path, f"{prefix}.evidence[{evidence_index}]", repo_root, errors)

        if status != "passed":
            if not _is_non_empty_string(gate.get("blocking_reason")):
                errors.append(f"{prefix}.blocking_reason is required for an unclosed gate")
            dependencies = gate.get("dependencies")
            if (
                not isinstance(dependencies, list)
                or not dependencies
                or not all(_is_non_empty_string(item) for item in dependencies)
            ):
                errors.append(f"{prefix}.dependencies must contain at least one non-empty item for an unclosed gate")
        elif gate.get("blocking_reason") is not None:
            errors.append(f"{prefix}.blocking_reason must be null for a passed gate")

    blocking_gates = release.get("blocking_gates")
    if not isinstance(blocking_gates, list) or not all(_is_non_empty_string(item) for item in blocking_gates):
        errors.append("release.blocking_gates must be an array of non-empty strings")
        blocking_gates = []
    if blocking_gates != non_passed_ids:
        errors.append(
            "release.blocking_gates must exactly match gates whose status is not passed "
            f"(expected {non_passed_ids!r})"
        )

    has_blocking_gate = bool(non_passed_ids)
    if has_blocking_gate and release_status != "blocked":
        errors.append("release.status must be blocked while any gate is not passed")
    if not has_blocking_gate and release_status != "ready":
        errors.append("release.status must be ready when all gates are passed")
    if release.get("eligible") != (not has_blocking_gate):
        errors.append("release.eligible must be false while blocked and true only when all gates pass")

    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        errors.append("documents must be a non-empty array")
        documents = []
    for index, document in enumerate(documents):
        prefix = f"documents[{index}]"
        if not isinstance(document, dict):
            errors.append(f"{prefix} must be an object")
            continue
        document_path = document.get("path")
        resolved = _resolve_repo_file(document_path, f"{prefix}.path", repo_root, errors)
        markers = document.get("markers")
        if not isinstance(markers, list) or not markers or not all(_is_non_empty_string(item) for item in markers):
            errors.append(f"{prefix}.markers must contain at least one non-empty string")
            continue
        if resolved is None:
            continue
        try:
            content = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{prefix}.path cannot be read as UTF-8 text: {exc}")
            continue
        for marker in markers:
            if marker not in content:
                errors.append(f"{prefix}.markers is missing from {document_path!r}: {marker!r}")

    return errors


def _load_manifest(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest is not valid JSON: {exc}") from exc


def _git_head_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value if SHA_PATTERN.fullmatch(value) else None


def _git_worktree_dirty() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return bool(result.stdout.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-sha", help="bind this validation run to a 40-character commit SHA")
    parser.add_argument(
        "--require-candidate-sha",
        action="store_true",
        help="fail unless --candidate-sha is supplied; use this in a release job",
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="fail unless the checked-out worktree is clean; use this for release builds",
    )
    args = parser.parse_args(argv)

    errors: list[str] = []
    if args.candidate_sha is not None and not SHA_PATTERN.fullmatch(args.candidate_sha):
        errors.append("--candidate-sha must be a 40-character lowercase commit SHA")
    if args.require_candidate_sha and args.candidate_sha is None:
        errors.append("--require-candidate-sha requires --candidate-sha")
    if args.candidate_sha is not None:
        current_sha = _git_head_sha()
        if current_sha is None:
            errors.append("unable to read the current git HEAD for candidate SHA binding")
        elif args.candidate_sha != current_sha:
            errors.append(f"--candidate-sha does not match the checked-out HEAD ({current_sha})")
    if args.require_clean:
        dirty = _git_worktree_dirty()
        if dirty is None:
            errors.append("unable to determine whether the git worktree is clean")
        elif dirty:
            errors.append("git worktree is not clean; commit or discard changes before release validation")

    try:
        manifest = _load_manifest(args.manifest)
    except ValueError as exc:
        errors.append(str(exc))
        manifest = None

    if manifest is not None:
        errors.extend(validate_manifest(manifest, REPO_ROOT))
        if isinstance(manifest, dict):
            release_value = manifest.get("release")
            manifest_sha = release_value.get("candidate_sha") if isinstance(release_value, dict) else None
            if args.candidate_sha is not None and manifest_sha is not None and manifest_sha != args.candidate_sha:
                errors.append("--candidate-sha does not match release.candidate_sha in the manifest")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    release = manifest["release"]
    gate_count = len(manifest["gates"])
    blocking_count = len(release["blocking_gates"])
    candidate = args.candidate_sha or release.get("candidate_sha") or "unbound"
    print(f"release evidence valid: gates={gate_count}, blocking={blocking_count}, candidate_sha={candidate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
