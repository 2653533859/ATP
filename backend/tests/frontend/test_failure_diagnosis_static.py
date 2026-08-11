import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_failure_diagnosis_service_uses_llm_with_rule_fallback():
    content = repo_path("backend/app/services/failure_diagnosis.py").read_text(encoding="utf-8")

    assert "build_failure_diagnosis_prompt" in content
    assert "build_rule_diagnosis" in content
    assert "call_llm" in content
    assert "request_or_action" in content
    assert "response_or_assertion" in content
    assert "screenshot_url" in content
    assert '"failure_diagnosis": payload' in content
    assert "rule_fallback" in content


def test_failure_diagnosis_builds_structured_repair_suggestions():
    content = repo_path("backend/app/services/failure_diagnosis.py").read_text(encoding="utf-8")
    schema = repo_path("backend/app/schemas/case.py").read_text(encoding="utf-8")

    assert "def build_repair_suggestions(" in content
    assert '"suggestion_type": suggestion_type' in content
    assert "update_assertion" in content
    assert "update_request" in content
    assert "investigate_environment" in content
    assert '"repair_suggestions": build_repair_suggestions(failed_steps)' in content
    assert "repair_suggestions: list[dict] = Field(default_factory=list)" in schema


def test_failure_diagnosis_endpoint_is_available_on_run_detail_api():
    content = repo_path("backend/app/api/v1/cases/runs.py").read_text(encoding="utf-8")
    schema = repo_path("backend/app/schemas/case.py").read_text(encoding="utf-8")

    assert '@router.post("/runs/{run_id}/failure-diagnosis", response_model=FailureDiagnosisOut)' in content
    assert "generate_failure_diagnosis(db, run_id)" in content
    assert "await _get_run_with_access(db, current_user, run_id)" in content
    assert "class FailureDiagnosisOut" in schema
    assert 'source: Literal["llm", "rule", "rule_fallback"]' in schema


def test_run_detail_frontend_exposes_failure_diagnosis_action():
    content = repo_path("frontend/src/views/run/RunDetail.vue").read_text(encoding="utf-8")
    api = repo_path("frontend/src/api/index.ts").read_text(encoding="utf-8")
    zh = repo_path("frontend/src/locales/zh-CN.ts").read_text(encoding="utf-8")
    en = repo_path("frontend/src/locales/en-US.ts").read_text(encoding="utf-8")

    assert "generateFailureDiagnosis" in api
    assert "FailureDiagnosisResult" in api
    assert "failureDiagnosisLoading" in content
    assert "handleGenerateFailureDiagnosis" in content
    assert "failure-diagnosis-card" in content
    assert "repair-suggestion-list" in content
    assert "repair_suggestions" in api
    assert "repair_type_update_assertion" in zh
    assert "repair_type_update_request" in zh
    assert "failure_diagnosis_source_llm" in zh
    assert "failure_diagnosis_source_rule_fallback" in zh
    assert "failure_diagnosis_source_llm" in en
    assert "repair_type_update_assertion" in en


def test_s5_01_is_marked_complete_in_roadmap():
    roadmap = repo_path("docs/optimization-roadmap-2026.md").read_text(encoding="utf-8")

    assert "| S5-01 | 失败原因总结 | P1 | [x] 已完成 |" in roadmap


def test_s5_03_is_marked_complete_in_roadmap():
    roadmap = repo_path("docs/optimization-roadmap-2026.md").read_text(encoding="utf-8")

    assert "| S5-03 | 用例修复建议 | P2 | [x] 已完成 |" in roadmap
