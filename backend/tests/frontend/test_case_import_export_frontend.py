import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_case_api_exposes_import_template_and_preview():
    content = repo_path("frontend/src/api/index.ts").read_text(encoding="utf-8")

    assert "downloadImportTemplate" in content
    assert "/cases/batch/import-template" in content
    assert "previewImportZip" in content
    assert "/cases/batch/import-preview" in content


def test_case_list_previews_zip_before_importing():
    content = repo_path("frontend/src/views/case/CaseList.vue").read_text(encoding="utf-8")

    assert "handleDownloadImportTemplate" in content
    assert "case.import_template" in content
    assert "caseApi.previewImportZip(file)" in content
    assert "importPreviewOpen.value = true" in content
    assert "confirmBatchImport" in content
    assert "case.import_preview.errors" in content


def test_case_import_backend_has_template_and_preview_contracts():
    content = repo_path("backend/app/api/v1/cases/batch.py").read_text(encoding="utf-8")
    schemas = repo_path("backend/app/schemas/case.py").read_text(encoding="utf-8")

    assert '@router.get("/cases/batch/import-template")' in content
    assert '@router.post("/cases/batch/import-preview", response_model=CaseBatchImportPreviewOut)' in content
    assert "def _read_cases_from_import_zip" in content
    assert "def _validate_import_cases" in content
    assert "class CaseBatchImportPreviewOut" in schemas
