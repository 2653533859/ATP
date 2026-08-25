from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "validate-release-evidence.py"
MANIFEST = ROOT / "docs" / "release-evidence-index-2026-08-25.json"


def _module():
    spec = importlib.util.spec_from_file_location("validate_release_evidence", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_current_release_evidence_index_is_valid():
    script = _module()

    assert script.validate_manifest(_manifest(), ROOT) == []


def test_unclosed_gate_requires_reason_dependencies_owner_and_recheck():
    script = _module()
    manifest = _manifest()
    gate = next(item for item in manifest["gates"] if item["status"] == "pending")
    gate.pop("blocking_reason")
    gate["dependencies"] = []
    gate["owner"] = ""
    gate["recheck_command"] = "line 1\nline 2"

    errors = script.validate_manifest(manifest, ROOT)

    assert any("blocking_reason is required" in error for error in errors)
    assert any("dependencies must contain" in error for error in errors)
    assert any("owner must be" in error for error in errors)
    assert any("recheck_command must be" in error for error in errors)


def test_manifest_rejects_sensitive_fields_and_paths_outside_repo():
    script = _module()
    manifest = _manifest()
    manifest["release"]["api_key"] = "must-not-be-recorded"
    manifest["gates"][0]["evidence"] = ["../outside.json"]

    errors = script.validate_manifest(manifest, ROOT)

    assert any("sensitive field name" in error for error in errors)
    assert any("must stay inside the repository" in error for error in errors)


def test_release_state_must_match_unclosed_gates():
    script = _module()
    manifest = _manifest()
    manifest["release"]["status"] = "ready"
    manifest["release"]["eligible"] = True

    errors = script.validate_manifest(manifest, ROOT)

    assert "release.status must be blocked while any gate is not passed" in errors
    assert "release.eligible must be false while blocked and true only when all gates pass" in errors


def test_release_candidate_sha_is_required_only_for_explicit_release_validation():
    script = _module()
    current_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    assert script.main(["--candidate-sha", current_sha, "--require-candidate-sha"]) == 0
    assert script.main(["--require-candidate-sha"]) == 1


def test_explicit_candidate_sha_cannot_disagree_with_manifest(tmp_path):
    script = _module()
    manifest = _manifest()
    manifest["release"]["candidate_sha"] = "b" * 40
    manifest_path = tmp_path / "release-evidence-index-test.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    current_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert script.main(["--manifest", str(manifest_path), "--candidate-sha", current_sha]) == 1


def test_non_object_manifest_returns_validation_error_instead_of_crashing(tmp_path):
    script = _module()
    manifest_path = tmp_path / "invalid-release-index.json"
    manifest_path.write_text("[]", encoding="utf-8")
    current_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    assert script.main(["--manifest", str(manifest_path), "--candidate-sha", current_sha]) == 1
