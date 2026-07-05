import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_notification_form_exposes_strategy_filters():
    content = repo_path("frontend/src/views/system/NotificationList.vue").read_text(encoding="utf-8")

    assert "notificationScope" in content
    assert "selectedSuiteIds" in content
    assert "selectedPlanIds" in content
    assert "statusFilters" in content
    assert "suiteApi.list({ project_id: projectId.value })" in content
    assert "planApi.list({ project_id: projectId.value })" in content
    assert "scope: notificationScope.value" in content
    assert "status_filters: statusFilters.value" in content


def test_notification_strategy_i18n_keys_exist():
    zh = repo_path("frontend/src/locales/zh-CN.ts").read_text(encoding="utf-8")
    en = repo_path("frontend/src/locales/en-US.ts").read_text(encoding="utf-8")

    for content in (zh, en):
        assert "strategy" in content
        assert "target_suites" in content
        assert "target_plans" in content
        assert "status_filters" in content
        assert "select_status" in content
