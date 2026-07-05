import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_dataset_impact_modal_shows_reference_summary_and_actions():
    content = repo_path("frontend/src/views/system/DatasetLibrary.vue").read_text(encoding="utf-8")

    assert "impact_title_with_name" in content
    assert "impact_total" in content
    assert "impactRows('case', impact.cases)" in content
    assert "impactRows('suite', impact.suites)" in content
    assert "impactRows('plan', impact.plans)" in content
    assert "record.reasonLabels" in content
    assert "openImpactTarget(record)" in content


def test_dataset_impact_targets_link_to_case_suite_and_plan_pages():
    content = repo_path("frontend/src/views/system/DatasetLibrary.vue").read_text(encoding="utf-8")

    assert "router.push({ name: 'case-detail'" in content
    assert "router.push({ name: 'suites' })" in content
    assert "router.push({ name: 'plans' })" in content
    assert "activeImpactDataset.value = record" in content


def test_dataset_impact_i18n_covers_reason_labels():
    zh = repo_path("frontend/src/locales/zh-CN.ts").read_text(encoding="utf-8")
    en = repo_path("frontend/src/locales/en-US.ts").read_text(encoding="utf-8")

    for content in (zh, en):
        assert "impact_reasons" in content
        assert "case_dataset_binding" in content
        assert "contains_dataset_cases" in content
        assert "suite_parameterization" in content
        assert "contains_dataset_suites" in content
        assert "impact_no_cases" in content
        assert "impact_no_suites" in content
        assert "impact_no_plans" in content
