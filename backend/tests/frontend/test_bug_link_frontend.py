import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_bug_tracker_api_supports_linking_existing_bugs_and_gitlab():
    content = repo_path("frontend/src/api/index.ts").read_text(encoding="utf-8")

    assert "export type BugTrackerType = 'jira' | 'zentao' | 'github' | 'gitlab'" in content
    assert "linkBug" in content
    assert "/runs/${runId}/link-bug" in content


def test_run_detail_supports_create_or_link_bug_modes():
    content = repo_path("frontend/src/views/run/RunDetail.vue").read_text(encoding="utf-8")

    assert "bugMode" in content
    assert "mode_create" in content
    assert "mode_link" in content
    assert "linkedBugId" in content
    assert "confirmLinkBug" in content
    assert "bugTrackerApi.linkBug" in content
    assert "trackerTypeLabel(t.tracker_type)" in content


def test_bug_tracker_management_exposes_gitlab_config():
    content = repo_path("frontend/src/views/system/BugTrackerList.vue").read_text(encoding="utf-8")

    assert '<a-select-option value="gitlab">GitLab Issues</a-select-option>' in content
    assert "gitlabProjectId" in content
    assert "gitlabBaseUrl" in content
    assert "gitlab_required" in content


def test_backend_can_link_existing_bug_to_run_summary():
    api = repo_path("backend/app/api/v1/bug_trackers.py").read_text(encoding="utf-8")
    schemas = repo_path("backend/app/schemas/bug_tracker.py").read_text(encoding="utf-8")

    assert "class LinkBugRequest" in schemas
    assert '@router.post("/runs/{run_id}/link-bug", response_model=BugStatusOut)' in api
    assert "current_user=Depends(get_current_user)" in api
    assert "assert_project_access(db, current_user, module.project_id, ProjectRole.editor)" in api
    assert '"linked_manually": True' in api
    assert 'summary["bug"]' in api
