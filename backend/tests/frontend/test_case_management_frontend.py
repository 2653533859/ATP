import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_case_list_shows_active_filter_tags():
    content = repo_path("frontend/src/views/case/CaseList.vue").read_text(encoding="utf-8")

    assert "activeFilterTags.length" in content
    assert "clearFilter(tag.key)" in content
    assert "case.active_filters" in content
    assert "case.clear_filters" in content


def test_case_list_exposes_review_workflow_in_status_column():
    content = repo_path("frontend/src/views/case/CaseList.vue").read_text(encoding="utf-8")

    assert "record.review_status === 'pending'" in content
    assert "handleWorkflow(asCase(record), 'approve')" in content
    assert "handleWorkflow(asCase(record), 'reject')" in content
    assert "pendingReviewCount" in content


def test_case_list_batch_move_no_longer_requires_current_module():
    content = repo_path("frontend/src/views/case/CaseList.vue").read_text(encoding="utf-8")

    assert '<a-button size="small" :disabled="!canModifyCases" @click="openBatchMove">' in content
    assert 'openBatchMove" :disabled="!selectedModuleId"' not in content


def test_web_and_android_use_specialized_case_drawers_without_generic_placeholder():
    case_list = repo_path("frontend/src/views/case/CaseList.vue").read_text(encoding="utf-8")
    generic_drawer = repo_path("frontend/src/components/common/CaseFormDrawer.vue").read_text(encoding="utf-8")
    zh_locale = repo_path("frontend/src/locales/zh-CN.ts").read_text(encoding="utf-8")
    en_locale = repo_path("frontend/src/locales/en-US.ts").read_text(encoding="utf-8")

    assert "<WebCaseDrawer" in case_list
    assert "<AndroidCaseDrawer" in case_list
    assert '<a-select-option value="web">' not in generic_drawer
    assert '<a-select-option value="android">' not in generic_drawer
    assert "placeholder_alert" not in generic_drawer
    assert "placeholder_alert" not in zh_locale
    assert "placeholder_alert" not in en_locale


def test_generic_case_drawer_can_pin_dataset_version():
    generic_drawer = repo_path("frontend/src/components/common/CaseFormDrawer.vue").read_text(encoding="utf-8")

    assert "dataset_version_label" in generic_drawer
    assert "datasetApi.listVersions" in generic_drawer
    assert "dataset_version: form.dataset_version" in generic_drawer
    assert '@change="handleDatasetChange"' in generic_drawer


def test_generic_case_drawer_drops_dataset_execution_config_when_unbound():
    generic_drawer = repo_path("frontend/src/components/common/CaseFormDrawer.vue").read_text(encoding="utf-8")

    assert "if (form.dataset_id == null) return config" in generic_drawer
    assert "dataset_prepare_actions" in generic_drawer
