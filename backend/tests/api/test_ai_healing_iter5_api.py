from pathlib import Path


def repo_path(path: str) -> Path:
    return Path(__file__).resolve().parents[2] / path


def test_ai_healing_iter5_router_registered():
    content = repo_path("app/api/v1/router.py").read_text(encoding="utf-8")

    assert "ai_healing_iter5" in content
    assert "router.include_router(ai_healing_iter5.router)" in content


def test_patch_preview_endpoint_is_non_mutating_and_project_scoped():
    content = repo_path("app/api/v1/ai_healing_iter5.py").read_text(encoding="utf-8")

    assert 'APIRouter(prefix="/ai-healing"' in content
    assert '@router.post("/patch-preview"' in content
    assert "validate_lowcode_patch" in content
    assert "assert_project_access" in content
    assert "ProjectRole.engineer" in content
    preview_body = content.split("async def preview_healing_patch", maxsplit=1)[1].split(
        '@router.post("/patch-apply"', maxsplit=1
    )[0]
    assert "await db.commit()" not in preview_body
    assert "await db.delete" not in preview_body


def test_patch_preview_schema_accepts_raw_or_structured_suggestion():
    content = repo_path("app/schemas/ai_healing_iter5.py").read_text(encoding="utf-8")

    assert "raw_suggestion" in content
    assert "StructuredHealingSuggestionIn" in content
    assert "HealingPatchPreviewOut" in content


def test_patch_apply_endpoint_snapshots_audits_and_can_trigger_regression():
    content = repo_path("app/api/v1/ai_healing_iter5.py").read_text(encoding="utf-8")

    assert '@router.post("/patch-apply"' in content
    assert "_build_snapshot" in content
    assert "_replace_case_steps" in content
    assert "ai_healing_patch_apply" in content
    assert "TestRun(" in content
    assert "triggered_by_ai_healing_patch" in content
    assert "run_test_case.delay" in content


def test_patch_apply_schema_tracks_source_and_regression():
    content = repo_path("app/schemas/ai_healing_iter5.py").read_text(encoding="utf-8")

    assert "class HealingPatchApplyRequest" in content
    assert "trigger_regression" in content
    assert "source_run_id" in content
    assert "class HealingPatchApplyOut" in content
    assert "regression_run_id" in content
