import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_ai_case_schema_supports_openapi_samples_and_natural_language():
    schema = repo_path("backend/app/schemas/ai_case.py").read_text(encoding="utf-8")
    parser = repo_path("backend/app/services/ai_case/parsers.py").read_text(encoding="utf-8")
    prompt = repo_path("backend/app/services/ai_case/prompts.py").read_text(encoding="utf-8")

    assert 'SchemaSourceType = Literal["openapi", "postman", "curl", "sample"]' in schema
    assert "def parse_sample(" in parser
    assert 'if source_type == "sample":' in parser
    assert "request_body_example" in parser
    assert "response_example" in parser
    assert "response_status" in schema
    assert "OpenAPI、接口样例和自然语言需求" in prompt
    assert "如果只提供自然语言需求" in prompt
    assert "如果提供请求/响应样例" in prompt


def test_ai_case_drawer_exposes_sample_and_natural_language_modes():
    drawer = repo_path("frontend/src/views/case/AIGenerateDrawer.vue").read_text(encoding="utf-8")
    api = repo_path("frontend/src/api/index.ts").read_text(encoding="utf-8")
    zh = repo_path("frontend/src/locales/zh-CN.ts").read_text(encoding="utf-8")
    en = repo_path("frontend/src/locales/en-US.ts").read_text(encoding="utf-8")

    assert "export type SchemaSourceType = 'openapi' | 'postman' | 'curl' | 'sample'" in api
    assert "type GenerationSourceType = SchemaSourceType | 'natural'" in drawer
    assert '<a-radio value="sample">' in drawer
    assert '<a-radio value="natural">' in drawer
    assert "sourceType !== 'natural'" in drawer
    assert "natural_hint" in zh
    assert "interface_sample" in zh
    assert "natural_hint" in en
    assert "interface_sample" in en
    assert "externalRefPolicy" in drawer
    assert "external_ref_policy" in drawer
    assert "external_ref_policy" in api
    assert "response_status" in api
    assert "external_ref_policy_label" in zh
    assert "external_ref_policy_label" in en


def test_s5_02_is_marked_complete_in_roadmap():
    roadmap = repo_path("docs/optimization-roadmap-2026.md").read_text(encoding="utf-8")

    assert "| S5-02 | AI 用例草稿生成增强 | P1 | [x] 已完成 |" in roadmap
