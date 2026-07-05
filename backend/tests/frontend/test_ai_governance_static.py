import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_ai_governance_helper_defines_prompt_limit_fallback_controls():
    content = repo_path("backend/app/services/ai_governance.py").read_text(encoding="utf-8")

    assert "def resolve_system_prompt(" in content
    assert "prompt_templates" in content
    assert "def resolve_daily_limit(" in content
    assert "daily_limits" in content
    assert "async def check_and_incr_daily_limit(" in content
    assert "def fallback_enabled(" in content
    assert "def llm_extra_params(" in content
    assert "_ALLOWED_LLM_EXTRA_PARAMS" in content


def test_ai_case_generation_uses_governance_controls():
    content = repo_path("backend/app/services/ai_case/generator.py").read_text(encoding="utf-8")

    assert "check_and_incr_daily_limit" in content
    assert 'capability="ai_case_generation"' in content
    assert "resolve_system_prompt(config, \"ai_case_generation\", SYSTEM_PROMPT)" in content
    assert "extra_params=llm_extra_params(config)" in content


def test_failure_diagnosis_uses_governance_and_fallback_controls():
    content = repo_path("backend/app/services/failure_diagnosis.py").read_text(encoding="utf-8")

    assert "check_and_incr_daily_limit" in content
    assert 'capability="failure_diagnosis"' in content
    assert "resolve_system_prompt(" in content
    assert "extra_params=llm_extra_params(config)" in content
    assert "fallback_enabled(config)" in content


def test_ai_governance_documentation_covers_s5_05_requirements():
    content = repo_path("docs/ai-governance.md").read_text(encoding="utf-8")

    assert "Project-Level Model Selection" in content
    assert "prompt_templates" in content
    assert "daily_limits" in content
    assert "fallback_enabled" in content
    assert "Error Degradation" in content
    assert "Reserved ATP governance keys are filtered out" in content


def test_s5_05_is_marked_complete_in_roadmap():
    roadmap = repo_path("docs/optimization-roadmap-2026.md").read_text(encoding="utf-8")

    assert "| S5-05 | Prompt 与模型配置治理 | P2 | [x] 已完成 |" in roadmap
