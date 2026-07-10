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
